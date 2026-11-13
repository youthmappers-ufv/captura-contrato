"""Interface do motor de planejamento (contrato entre a pesquisa P13 e o TCC 1).

Este arquivo define O QUE o motor oferece, não COMO ele funciona.
- A pesquisa (IC) implementa uma classe que segue o protocolo `Motor`.
- A API do TCC 1 chama apenas os métodos abaixo, sem conhecer o algoritmo.
- `MotorDeExemplo` devolve sempre o plano de exemplo: permite ao TCC 1
  começar antes de o motor real existir.

Convenções:
- `area` é uma geometria GeoJSON (Polygon ou MultiPolygon), em [lon, lat].
- `parametros` é um dicionário com o formato de `plano.parametros`
  (ver plano-captura.schema.json).
- `planejar()` parte do plano de cobertura devolvido por
  `analisar_cobertura()`, e não da área: a cobertura não é consultada de
  novo, os segmentos e seus ids são os mesmos, e o plano é reprodutível.
- O retorno é sempre um plano no formato do contrato, que deve passar em
  `validar_plano.validar()`.
"""
from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Optional, Protocol

VERSAO_FORMATO = "0.1.0"

PARAMETROS_DE_COBERTURA = ("modo", "idade_maxima_dias", "provedores", "segmento_max_m", "cobertura")
"""Definem a rede e a classificação dos segmentos; ficam fixados pelo plano de cobertura."""
PARAMETROS_DE_ROTA = ("camera", "velocidade_captura_kmh", "velocidade_deslocamento_kmh", "limite_sessao",
                      "partida", "chegada", "sessoes_partem_da_base", "preferencias")
"""Podem mudar entre analisar_cobertura() e planejar()."""

Ajuste = Literal["incluido", "excluido"]
Progresso = Callable[[float, str], None]
"""Recebe (fração concluída de 0 a 1, mensagem curta). Ex.: (0.4, "Consultando o Panoramax")."""
Cancelado = Callable[[], bool]
"""Devolve True quando o usuário pediu para cancelar; o motor deve parar e levantar PlanejamentoCancelado."""


# ---------------------------------------------------------------------------
# Erros que o motor pode levantar. A API do TCC 1 traduz cada um em uma
# resposta HTTP e em uma mensagem para o usuário.
# ---------------------------------------------------------------------------
class ErroMotor(Exception):
    """Base de todos os erros previstos do motor."""


class AreaInvalida(ErroMotor):
    """Geometria inválida (anel aberto, autointerseção, vazia). HTTP 422."""


class AreaGrandeDemais(ErroMotor):
    """A área excede o limite configurado. HTTP 413. O limite vem em `limite_km2`."""

    def __init__(self, mensagem: str, limite_km2: float):
        super().__init__(mensagem)
        self.limite_km2 = limite_km2


class ParametrosInvalidos(ErroMotor):
    """Combinação de parâmetros sem sentido (ex.: nenhum provedor). HTTP 422."""


class ProvedorIndisponivel(ErroMotor):
    """Mapillary ou Panoramax não responderam. HTTP 503; pode-se tentar de novo."""

    def __init__(self, mensagem: str, provedor: str):
        super().__init__(mensagem)
        self.provedor = provedor


class PlanejamentoCancelado(ErroMotor):
    """O usuário cancelou (ver `Cancelado`)."""


# ---------------------------------------------------------------------------
# O protocolo
# ---------------------------------------------------------------------------
class Motor(Protocol):
    """O que qualquer implementação do motor precisa oferecer."""

    nome: str
    versao: str

    def analisar_cobertura(
        self,
        area: Mapping[str, Any],
        parametros: Mapping[str, Any],
        *,
        progresso: Optional[Progresso] = None,
        cancelado: Optional[Cancelado] = None,
    ) -> dict[str, Any]:
        """Classifica os segmentos da área, sem gerar rotas.

        Devolve um plano com `estado = "cobertura"`: área + segmentos, sem
        sessões, com os campos de sessão do resumo iguais a null.
        É a primeira etapa da tela de planejamento (mapa colorido da cobertura).
        """
        ...

    def planejar(
        self,
        cobertura: Mapping[str, Any],
        *,
        ajustes: Optional[Mapping[str, Ajuste]] = None,
        parametros: Optional[Mapping[str, Any]] = None,
        progresso: Optional[Progresso] = None,
        cancelado: Optional[Cancelado] = None,
    ) -> dict[str, Any]:
        """Gera o plano completo (`estado = "completo"`) a partir de um plano de cobertura.

        `cobertura` é um plano válido com `estado = "cobertura"`, devolvido
        por `analisar_cobertura`. O motor não consulta a cobertura de novo e
        DEVE preservar os segmentos dele (ids, geometria, estado e frações),
        mudando só `ajuste`, `exigencia` e acrescentando segmentos fora da
        área para deslocamento, se precisar.

        `ajustes` mapeia id de segmento → "incluido" ou "excluido" e
        representa as decisões manuais do usuário.

        `parametros`, se informado, substitui os parâmetros de rota
        (`PARAMETROS_DE_ROTA`); os de cobertura vêm do plano de cobertura.

        Levanta `ParametrosInvalidos` se `cobertura` não estiver no estado
        "cobertura", se um ajuste citar segmento inexistente ou fora da área,
        ou se `parametros` tentar mudar um parâmetro de cobertura.
        """
        ...


def conferir_entradas_de_planejar(cobertura: Mapping[str, Any], ajustes: Optional[Mapping[str, Any]] = None,
                                  parametros: Optional[Mapping[str, Any]] = None) -> None:
    """Conferências que todo motor faz em `planejar()`; reutilizável pelo motor real."""
    if cobertura.get("plano", {}).get("estado") != "cobertura":
        raise ParametrosInvalidos("planejar() recebe um plano em estado 'cobertura'")
    segmentos = {f["properties"]["id"]: f["properties"] for f in cobertura.get("features", [])
                 if f["properties"]["tipo"] == "segmento"}
    for sid, valor in (ajustes or {}).items():
        if sid not in segmentos:
            raise ParametrosInvalidos(f"ajuste cita o segmento '{sid}', que não existe no plano de cobertura")
        if not segmentos[sid]["na_area"]:
            raise ParametrosInvalidos(f"o segmento '{sid}' está fora da área e não aceita ajuste")
        if valor not in ("incluido", "excluido"):
            raise ParametrosInvalidos(f"ajuste '{valor}' inválido para o segmento '{sid}'")
    proibidos = sorted(set(parametros or {}) - set(PARAMETROS_DE_ROTA))
    if proibidos:
        raise ParametrosInvalidos(f"parâmetros fixados pelo plano de cobertura: {proibidos}")


# ---------------------------------------------------------------------------
# Implementação falsa, para desenvolvimento e testes do TCC 1
# ---------------------------------------------------------------------------
class MotorDeExemplo:
    """Ignora a área e devolve sempre o plano de exemplo, com id e data novos."""

    nome = "motor-de-exemplo"
    versao = VERSAO_FORMATO

    def __init__(self, caminho: Path | None = None):
        recurso = caminho or files("captura_contrato") / "exemplo-plano.geojson"
        self._exemplo: dict[str, Any] = json.loads(recurso.read_text(encoding="utf-8"))

    def _novo(self) -> dict[str, Any]:
        plano: dict[str, Any] = copy.deepcopy(self._exemplo)
        plano["plano"]["id"] = str(uuid.uuid4())
        plano["plano"]["criado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        plano["plano"]["gerado_por"] = {"software": self.nome, "versao": self.versao,
                                        "algoritmo": "exemplo", "semente": None}
        return plano

    def analisar_cobertura(self, area: Mapping[str, Any], parametros: Mapping[str, Any], *,
                           progresso: Optional[Progresso] = None,
                           cancelado: Optional[Cancelado] = None) -> dict[str, Any]:
        plano = self._novo()
        plano["plano"]["estado"] = "cobertura"
        plano["features"] = [f for f in plano["features"]
                             if f["properties"]["tipo"] in ("area", "segmento")]
        r = plano["plano"]["resumo"]
        r.update(n_sessoes=0, km_total=None, km_sem_captura=None, km_exigido_atendido=None,
                 razao_deslocamento=None, duracao_estimada_min=None)
        if progresso:
            progresso(1.0, "Cobertura analisada")
        return plano

    def planejar(self, cobertura: Mapping[str, Any], *, ajustes: Optional[Mapping[str, Ajuste]] = None,
                 parametros: Optional[Mapping[str, Any]] = None, progresso: Optional[Progresso] = None,
                 cancelado: Optional[Cancelado] = None) -> dict[str, Any]:
        """Confere as entradas como o motor real faria, mas devolve sempre o plano de exemplo.

        Não aplica ajustes nem parâmetros de rota: serve para construir a API e
        as telas, não para testar o efeito de um ajuste.
        """
        conferir_entradas_de_planejar(cobertura, ajustes, parametros)
        if cancelado and cancelado():
            raise PlanejamentoCancelado("cancelado pelo usuário")
        if progresso:
            progresso(1.0, "Plano gerado")
        return self._novo()
