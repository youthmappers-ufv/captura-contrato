"""Contrato do plano de captura (projeto P13, Programa Youthmappers UFV).

Duas versões convivem aqui e não devem ser confundidas:

- `VERSAO_FORMATO` é a versão do formato do plano (campo `versao_formato`
  dos arquivos). É ela que o esquema aceita e que os consumidores leem.
- `__version__` é a versão deste pacote. Uma correção de empacotamento ou de
  documentação muda o pacote sem mudar o formato.

Uso típico:

    from captura_contrato import validar, carregar_exemplo
    assert validar(carregar_exemplo()) == []
"""
from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files

from .motor_interface import (
    PARAMETROS_DE_COBERTURA,
    PARAMETROS_DE_ROTA,
    VERSAO_FORMATO,
    AreaGrandeDemais,
    AreaInvalida,
    ErroMotor,
    Motor,
    MotorDeExemplo,
    ParametrosInvalidos,
    PlanejamentoCancelado,
    ProvedorIndisponivel,
    conferir_entradas_de_planejar,
)
from .validar_plano import validar

try:
    __version__ = version("captura-contrato")
except PackageNotFoundError:  # rodando direto do código-fonte, sem instalar
    __version__ = "0.0.0+fonte"


def carregar_exemplo() -> dict:
    """Devolve uma cópia nova do plano de exemplo oficial (dados fictícios)."""
    texto = (files("captura_contrato") / "exemplo-plano.geojson").read_text(encoding="utf-8")
    return json.loads(texto)


def carregar_esquema() -> dict:
    """Devolve o esquema JSON do plano de captura."""
    texto = (files("captura_contrato") / "plano-captura.schema.json").read_text(encoding="utf-8")
    return json.loads(texto)


__all__ = [
    "PARAMETROS_DE_COBERTURA", "PARAMETROS_DE_ROTA", "VERSAO_FORMATO", "__version__",
    "AreaGrandeDemais", "AreaInvalida", "ErroMotor", "Motor", "MotorDeExemplo", "ParametrosInvalidos",
    "PlanejamentoCancelado", "ProvedorIndisponivel",
    "carregar_esquema", "carregar_exemplo", "conferir_entradas_de_planejar", "validar",
]
