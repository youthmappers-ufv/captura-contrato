#!/usr/bin/env python3
"""Valida um plano de captura em duas etapas.

1. Estrutura: confere o arquivo contra o esquema JSON
   (plano-captura.schema.json), isto é, campos, tipos e valores permitidos.
2. Consistência: confere as regras que um esquema JSON não consegue
   exprimir (R1 a R15 em contrato-plano-captura.md), como "toda passagem
   aponta para um segmento existente".

Uso:
    pip install "jsonschema[format]"
    python validar_plano.py plano.geojson [outro.geojson ...]

Saída: 0 se todos os planos forem válidos; 1 caso contrário.
Também pode ser importado nos testes: `erros = validar(plano)`.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ESQUEMA = Path(__file__).with_name("plano-captura.schema.json")
TOLERANCIA_M = 1.0      # folga para comparar posições ao longo da linha
TOLERANCIA_REL = 0.01   # 1% de folga para somas de distâncias
TOLERANCIA_PASSAGEM = 0.05  # 5% do comprimento do segmento, para extensão e posição da passagem
MARGEM_GRAUS = 0.02     # ~2 km: sessões podem sair um pouco da área para conectar trechos
CASAS_VERTICE = 7       # casas decimais para considerar dois vértices iguais (~1 cm)


def comprimento_m(coords: list[list[float]]) -> float:
    """Comprimento de uma LineString em metros (fórmula de haversine)."""
    r = 6_371_008.8
    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:]):
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp, dl = p2 - p1, math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        total += 2 * r * math.asin(math.sqrt(a))
    return total


def ponto_na_linha(coords: list[list[float]], posicao_m: float) -> list[float]:
    """Ponto a `posicao_m` metros do início da linha (referência linear)."""
    percorrido = 0.0
    for a, b in zip(coords, coords[1:]):
        trecho = comprimento_m([a, b])
        if trecho > 0 and percorrido + trecho >= posicao_m:
            t = max(0.0, min(1.0, (posicao_m - percorrido) / trecho))
            return [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]
        percorrido += trecho
    return list(coords[-1])


def vertice(c: list[float]) -> tuple[float, float]:
    return (round(c[0], CASAS_VERTICE), round(c[1], CASAS_VERTICE))


def exigencia_esperada(seg: dict, camera: str) -> str:
    """Regra R6: a exigência decorre da área, do estado, do ajuste, da câmera e do sentido."""
    if not seg["na_area"] or seg["ajuste"] == "excluido":
        return "nenhuma"
    if seg["ajuste"] != "incluido" and seg["estado"] == "atual":
        return "nenhuma"
    if seg["mao_unica"]:
        return "sentido_da_geometria"
    return "qualquer_sentido" if camera == "panoramica_360" else "dois_sentidos"


def estado_esperado(fracao_com_imagem: float, fracao_atual: float, fracao_min: float) -> str:
    """Regra provisória de cobertura parcial (seção 6.8), até a calibração da pesquisa (QP3)."""
    if fracao_atual >= fracao_min:
        return "atual"
    if fracao_com_imagem >= fracao_min:
        return "desatualizado"
    return "sem_imagem"


def perto(a: float, b: float) -> bool:
    return abs(a - b) <= max(TOLERANCIA_REL * max(abs(a), abs(b)), 0.01)


@lru_cache(maxsize=1)
def _validador_do_esquema() -> Draft202012Validator:
    esquema = json.loads(ESQUEMA.read_text(encoding="utf-8"))
    return Draft202012Validator(esquema, format_checker=FormatChecker())


def _data_de_referencia(meta: dict) -> date | None:
    """Data da consulta de cobertura mais recente; base para a idade das imagens."""
    try:
        return max(datetime.fromisoformat(c["consultado_em"]).date()
                   for c in meta["fontes"]["cobertura"])
    except ValueError:  # sem o extra [format] do jsonschema, datas ruins passam no esquema
        return None


def _cobertura_incoerente(sp: dict, par: dict, referencia: date | None) -> list[str]:
    """R13: estado, frações e data da última imagem de um segmento contam a mesma história."""
    msgs = []
    com, atual = sp["fracao_com_imagem"], sp["fracao_atual"]
    if sp["estado"] is None:
        if sp["na_area"]:
            msgs.append("segmento na área precisa de estado")
        if com is not None or atual is not None:
            msgs.append("segmento sem estado não leva frações de cobertura")
    elif com is None or atual is None:
        msgs.append(f"estado '{sp['estado']}' exige fracao_com_imagem e fracao_atual")
    else:
        if atual > com:
            msgs.append(f"fracao_atual={atual} maior que fracao_com_imagem={com}")
        esperado = estado_esperado(com, atual, par["cobertura"]["fracao_min"])
        if sp["estado"] != esperado:
            msgs.append(f"estado '{sp['estado']}', mas as frações ({com} com imagem, {atual} atual; "
                        f"mínimo {par['cobertura']['fracao_min']}) indicam '{esperado}'")
        if (com > 0) != (sp["ultima_imagem"] is not None):
            msgs.append("ultima_imagem deve existir se, e somente se, fracao_com_imagem > 0")
    if (sp["ultima_imagem"] is None) != (sp.get("provedor_ultima_imagem") is None):
        msgs.append("ultima_imagem e provedor_ultima_imagem vêm juntos")
    if sp["ultima_imagem"] is not None and atual is not None and referencia is not None:
        try:
            idade = (referencia - date.fromisoformat(sp["ultima_imagem"])).days
        except ValueError:
            idade = None
        limite = par["idade_maxima_dias"]
        if idade is not None and atual > 0 and idade > limite + 1:
            msgs.append(f"fracao_atual={atual}, mas a última imagem tem {idade} dias (máximo: {limite})")
        if idade is not None and atual == 0 and idade < limite - 1:
            msgs.append(f"fracao_atual=0, mas a última imagem tem só {idade} dias (máximo: {limite})")
    return msgs


def _inicios_e_fins(sessoes: list[dict], pontos: list[dict], par: dict, estado: str) -> list[str]:
    """R14: onde cada sessão começa e termina, conforme a partida, a chegada e sessoes_partem_da_base."""
    erros = []
    do_plano = {pt["properties"]["papel"]: vertice(pt["geometry"]["coordinates"])
                for pt in pontos if pt["properties"]["sessao"] is None}
    for papel in ("partida", "chegada"):
        # no plano de cobertura o ponto ajustado à rede é opcional; no completo, obrigatório
        falta_ponto = par[papel] is not None and papel not in do_plano and estado == "completo"
        if falta_ponto or (par[papel] is None and papel in do_plano):
            erros.append(f"[R14] parametros.{papel} e o ponto de {papel} do plano devem existir juntos")
    if par["sessoes_partem_da_base"] and par["partida"] is None:
        erros.append("[R14] sessoes_partem_da_base exige partida")
    ordenadas = sorted(sessoes, key=lambda s: s["properties"]["ordem"])
    pontas = {s["properties"]["id"]: (vertice(s["geometry"]["coordinates"][0]), vertice(s["geometry"]["coordinates"][-1]))
              for s in ordenadas}
    partida, chegada = do_plano.get("partida"), do_plano.get("chegada")
    for k, s in enumerate(ordenadas):
        sid = s["properties"]["id"]
        inicio, fim = pontas[sid]
        if par["sessoes_partem_da_base"]:
            esperado_inicio = partida
            esperado_fim = chegada or partida
        else:
            esperado_inicio = partida if k == 0 else pontas[ordenadas[k - 1]["properties"]["id"]][1]
            esperado_fim = chegada if k == len(ordenadas) - 1 else None
        if esperado_inicio is not None and inicio != esperado_inicio:
            onde = "na partida" if par["sessoes_partem_da_base"] or k == 0 else "onde a sessão anterior terminou"
            erros.append(f"[R14] sessão {sid} deveria começar {onde}")
        if esperado_fim is not None and fim != esperado_fim:
            erros.append(f"[R14] sessão {sid} deveria terminar {'na chegada' if chegada else 'na partida'}")
    for pt in pontos:
        sid = pt["properties"]["sessao"]
        if sid in pontas:
            i = 0 if pt["properties"]["papel"] == "partida" else 1
            if vertice(pt["geometry"]["coordinates"]) != pontas[sid][i]:
                erros.append(f"[R14] ponto de {pt['properties']['papel']} da sessão {sid} não coincide com a linha da sessão")
    return erros


def validar(plano: dict) -> list[str]:
    """Devolve a lista de erros encontrados (vazia se o plano for válido)."""
    erros = [
        f"[esquema] {'/'.join(map(str, e.absolute_path)) or '(raiz)'}: {e.message}"
        for e in sorted(_validador_do_esquema().iter_errors(plano), key=lambda e: list(e.absolute_path))
    ]
    if erros:  # sem estrutura válida, as regras abaixo não fazem sentido
        return erros

    meta = plano["plano"]
    par = meta["parametros"]
    por_tipo: dict[str, list[dict]] = {"area": [], "segmento": [], "sessao": [], "ponto": []}
    for f in plano["features"]:
        por_tipo[f["properties"]["tipo"]].append(f)
    areas, segs, sessoes, pontos = (por_tipo[k] for k in ("area", "segmento", "sessao", "ponto"))

    # R1 — exatamente uma área, com anéis fechados e não degenerados
    if len(areas) != 1:
        erros.append(f"[R1] deve haver exatamente 1 área; há {len(areas)}")
    for a in areas:
        g = a["geometry"]
        poligonos = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poligono in poligonos:
            for anel in poligono:
                if anel[0] != anel[-1]:
                    erros.append("[R1] anel da área não está fechado (1º ponto ≠ último)")
                elif len({vertice(c) for c in anel}) < 3:
                    erros.append("[R1] anel da área tem menos de 3 pontos distintos")

    # R2 — identificadores únicos; no máximo um ponto de cada papel por plano e por sessão
    ids_seg = [s["properties"]["id"] for s in segs]
    ids_ses = [s["properties"]["id"] for s in sessoes]
    for nome, ids in (("segmento", ids_seg), ("sessão", ids_ses)):
        repetidos = {i for i in ids if ids.count(i) > 1}
        if repetidos:
            erros.append(f"[R2] ids de {nome} repetidos: {sorted(repetidos)}")
    segmentos = {s["properties"]["id"]: s for s in segs}
    papeis = [(pt["properties"]["sessao"], pt["properties"]["papel"]) for pt in pontos]
    for sessao, papel in sorted({x for x in papeis if papeis.count(x) > 1}, key=str):
        onde = "do plano" if sessao is None else f"da sessão {sessao}"
        erros.append(f"[R2] mais de um ponto de {papel} {onde}")

    # R3 — estado do plano × presença de sessões
    if meta["estado"] == "cobertura" and sessoes:
        erros.append("[R3] plano em estado 'cobertura' não pode ter sessões")
    if meta["estado"] == "completo" and not sessoes:
        erros.append("[R3] plano em estado 'completo' precisa de ao menos 1 sessão")
    ordens = sorted(s["properties"]["ordem"] for s in sessoes)
    if ordens != list(range(1, len(sessoes) + 1)):
        erros.append(f"[R3] ordens das sessões devem ser 1..n sem falhas; encontrado {ordens}")

    # Trechos orientados da rede, para conferir a contramão também fora das passagens (R5).
    # permitidos: (a, b) que se pode percorrer; contramao: (a, b) → id do segmento de mão única.
    permitidos: set[tuple] = set()
    contramao: dict[tuple, str] = {}
    for s in segs:
        vs = [vertice(c) for c in s["geometry"]["coordinates"]]
        for a, b in zip(vs, vs[1:]):
            permitidos.add((a, b))
            if s["properties"]["mao_unica"]:
                contramao[(b, a)] = s["properties"]["id"]
            else:
                permitidos.add((b, a))

    # R4, R5, R7, R8, R12 — sessões e suas passagens
    cobertos: dict[str, set[str]] = {}
    for ses in sessoes:
        p = ses["properties"]
        linha = ses["geometry"]["coordinates"]
        compr = comprimento_m(linha)
        anterior_fim = 0.0
        for i, pas in enumerate(p["passagens"]):
            rotulo = f"sessão {p['id']}, passagem {i}"
            seg = segmentos.get(pas["segmento"])
            if seg is None:
                erros.append(f"[R4] {rotulo}: segmento '{pas['segmento']}' não existe")
                continue
            if seg["properties"]["mao_unica"] and pas["sentido"] == "inverso":
                erros.append(f"[R5] {rotulo}: segmento de mão única percorrido no sentido inverso")
            # R7 — referência linear coerente
            posicoes_ok = pas["inicio_m"] < pas["fim_m"] <= compr + TOLERANCIA_M
            if not posicoes_ok:
                erros.append(f"[R7] {rotulo}: posições inválidas ({pas['inicio_m']}–{pas['fim_m']} m; linha tem {compr:.1f} m)")
            if pas["inicio_m"] + TOLERANCIA_M < anterior_fim:
                erros.append(f"[R7] {rotulo}: passagens fora de ordem ao longo da linha")
            esperado = seg["properties"]["comprimento_m"]
            folga = max(TOLERANCIA_M, TOLERANCIA_PASSAGEM * esperado)
            if abs((pas["fim_m"] - pas["inicio_m"]) - esperado) > folga:
                erros.append(f"[R7] {rotulo}: extensão ({pas['fim_m'] - pas['inicio_m']:.1f} m) difere do segmento ({esperado:.1f} m)")
            elif posicoes_ok:
                # a passagem precisa estar sobre o segmento, no sentido declarado
                pontas = [seg["geometry"]["coordinates"][0], seg["geometry"]["coordinates"][-1]]
                if pas["sentido"] == "inverso":
                    pontas.reverse()
                desvio = max(
                    comprimento_m([ponto_na_linha(linha, pas["inicio_m"]), pontas[0]]),
                    comprimento_m([ponto_na_linha(linha, pas["fim_m"]), pontas[1]]),
                )
                if desvio > folga:
                    erros.append(f"[R7] {rotulo}: o trecho {pas['inicio_m']}–{pas['fim_m']} m da linha não coincide com o segmento "
                                 f"'{pas['segmento']}' no sentido {pas['sentido']} (desvio de {desvio:.1f} m)")
            anterior_fim = pas["fim_m"]
            cobertos.setdefault(pas["segmento"], set()).add(pas["sentido"])
        # R5 — contramão em qualquer trecho da linha, com ou sem captura;
        # R15 — a linha só passa por segmentos do plano
        vs = [vertice(c) for c in linha]
        trechos = [t for t in zip(vs, vs[1:]) if t[0] != t[1]]
        na_contramao = {contramao[t] for t in trechos if t in contramao and t not in permitidos}
        for sid in sorted(na_contramao):
            erros.append(f"[R5] sessão {p['id']}: a linha percorre o segmento de mão única '{sid}' na contramão")
        fora = [t for t in trechos if t not in permitidos and t not in contramao]
        if fora:
            erros.append(f"[R15] sessão {p['id']}: {len(fora)} trecho(s) da linha não coincidem com nenhum segmento do plano "
                         f"(primeiro: {list(fora[0][0])} → {list(fora[0][1])})")
        # R8 — totais da sessão
        if not perto(p["distancia_km"], compr / 1000):
            erros.append(f"[R8] sessão {p['id']}: distancia_km={p['distancia_km']} mas a linha mede {compr / 1000:.3f} km")
        km_cap = sum(pas["fim_m"] - pas["inicio_m"] for pas in p["passagens"]) / 1000
        if not perto(p["km_captura"], km_cap):
            erros.append(f"[R8] sessão {p['id']}: km_captura={p['km_captura']} mas as passagens somam {km_cap:.3f} km")
        if not perto(p["km_captura"] + p["km_sem_captura"], p["distancia_km"]):
            erros.append(f"[R8] sessão {p['id']}: km_captura + km_sem_captura ≠ distancia_km")
        # a duração não pode ser menor que o tempo de movimento; penalidades (retornos, conversões) só acrescentam
        minimo = 60 * (p["km_captura"] / par["velocidade_captura_kmh"]
                       + p["km_sem_captura"] / par["velocidade_deslocamento_kmh"])
        if p["duracao_estimada_min"] < minimo * (1 - TOLERANCIA_REL) - 0.01:
            erros.append(f"[R8] sessão {p['id']}: duracao_estimada_min={p['duracao_estimada_min']} é menor que o tempo "
                         f"de movimento pelas velocidades do plano ({minimo:.2f} min)")
        for ins in p.get("instrucoes", []):
            if ins["posicao_m"] > compr + TOLERANCIA_M:
                erros.append(f"[R7] sessão {p['id']}: instrução além do fim da linha")
        # R12 — limites da sessão
        for campo, limite, unidade in (("duracao_estimada_min", par["limite_sessao"]["duracao_max_min"], "min"),
                                       ("distancia_km", par["limite_sessao"]["distancia_max_km"], "km")):
            if limite is not None and p[campo] > limite * (1 + TOLERANCIA_REL):
                erros.append(f"[R12] sessão {p['id']}: {campo}={p[campo]} excede o limite de {limite} {unidade}")

    # R6 — exigência coerente; R9 — obrigatórios atendidos ou justificados; R13 — segmento coerente
    camera = par["camera"]
    referencia = _data_de_referencia(meta)
    atendidos: set[str] = set()
    citados = [n["segmento"] for n in meta["segmentos_nao_atendidos"]]
    nao_atendidos = set(citados)
    for sid in sorted({c for c in citados if citados.count(c) > 1}):
        erros.append(f"[R9] segmentos_nao_atendidos cita '{sid}' mais de uma vez")
    for sid, seg in segmentos.items():
        sp = seg["properties"]
        esperada = exigencia_esperada(sp, camera)
        if sp["exigencia"] != esperada:
            erros.append(f"[R6] segmento {sid}: exigencia='{sp['exigencia']}', esperado '{esperada}'")
        if par["modo"] == "a_pe" and sp["mao_unica"]:
            erros.append(f"[R6] segmento {sid}: no modo a pé não há mão única")
        if not sp["na_area"] and sp["ajuste"] is not None:
            erros.append(f"[R6] segmento {sid}: fora da área, não aceita ajuste manual")

        medido = comprimento_m(seg["geometry"]["coordinates"])
        if abs(sp["comprimento_m"] - medido) > max(TOLERANCIA_M, TOLERANCIA_REL * medido):
            erros.append(f"[R13] segmento {sid}: comprimento_m={sp['comprimento_m']} mas a geometria mede {medido:.1f} m")
        if sp["comprimento_m"] > par["segmento_max_m"] * (1 + TOLERANCIA_REL):
            erros.append(f"[R13] segmento {sid}: comprimento_m={sp['comprimento_m']} excede segmento_max_m={par['segmento_max_m']}")
        erros.extend(f"[R13] segmento {sid}: {msg}" for msg in _cobertura_incoerente(sp, par, referencia))

        if sid in nao_atendidos and sp["exigencia"] == "nenhuma":
            erros.append(f"[R9] segmentos_nao_atendidos cita '{sid}', que não é alvo")
        if meta["estado"] != "completo" or sp["exigencia"] == "nenhuma":
            continue
        feitos = cobertos.get(sid, set())
        atendido = {
            "qualquer_sentido": bool(feitos),
            "sentido_da_geometria": "direto" in feitos,
            "dois_sentidos": feitos >= {"direto", "inverso"},
        }[sp["exigencia"]]
        if atendido:
            atendidos.add(sid)
        if not atendido and sid not in nao_atendidos:
            erros.append(f"[R9] segmento obrigatório {sid} ({sp['exigencia']}) não foi atendido nem justificado")
        if atendido and sid in nao_atendidos:
            erros.append(f"[R9] segmentos_nao_atendidos cita '{sid}', que foi atendido pelas passagens")
    for sid in sorted(nao_atendidos - segmentos.keys()):
        erros.append(f"[R9] segmentos_nao_atendidos cita '{sid}', que não existe")

    # R10 — resumo coerente com as features
    r = meta["resumo"]
    na_area = [s for s in segs if s["properties"]["na_area"]]  # segmentos fora da área são só deslocamento
    alvo = [s for s in segs if s["properties"]["exigencia"] != "nenhuma"]
    if r["n_segmentos"] != len(na_area):
        erros.append(f"[R10] resumo.n_segmentos={r['n_segmentos']}, há {len(na_area)} na área")
    if r["n_segmentos_alvo"] != len(alvo):
        erros.append(f"[R10] resumo.n_segmentos_alvo={r['n_segmentos_alvo']}, há {len(alvo)}")
    if r["n_sessoes"] != len(sessoes):
        erros.append(f"[R10] resumo.n_sessoes={r['n_sessoes']}, há {len(sessoes)}")
    km_rede = sum(s["properties"]["comprimento_m"] for s in na_area) / 1000
    if not perto(r["km_rede_modo"], km_rede):
        erros.append(f"[R10] resumo.km_rede_modo={r['km_rede_modo']}, soma dos segmentos na área={km_rede:.3f}")
    km_alvo = sum(s["properties"]["comprimento_m"] for s in alvo) / 1000
    if not perto(r["km_alvo"], km_alvo):
        erros.append(f"[R10] resumo.km_alvo={r['km_alvo']}, soma dos segmentos-alvo={km_alvo:.3f}")
    def exigido_km(lista) -> float:
        """Captura mínima exigida: 'dois_sentidos' conta duas passadas."""
        return sum(s["properties"]["comprimento_m"] * (2 if s["properties"]["exigencia"] == "dois_sentidos" else 1)
                   for s in lista) / 1000
    km_exigido = exigido_km(alvo)
    if not perto(r["km_exigido"], km_exigido):
        erros.append(f"[R10] resumo.km_exigido={r['km_exigido']}, captura exigida pelos segmentos-alvo={km_exigido:.3f}")
    if meta["estado"] == "completo":
        km_total = sum(s["properties"]["distancia_km"] for s in sessoes)
        km_vazio = sum(s["properties"]["km_sem_captura"] for s in sessoes)
        duracao = sum(s["properties"]["duracao_estimada_min"] for s in sessoes)
        km_atendido = exigido_km([segmentos[sid] for sid in atendidos])
        for campo, valor, origem in (("km_total", km_total, "soma das sessões"),
                                     ("km_sem_captura", km_vazio, "soma das sessões"),
                                     ("duracao_estimada_min", duracao, "soma das sessões"),
                                     ("km_exigido_atendido", km_atendido, "captura exigida dos segmentos atendidos")):
            if r[campo] is None or not perto(r[campo], valor):
                erros.append(f"[R10] resumo.{campo}={r[campo]}, {origem}={valor:.3f}")
        if km_atendido > 0:
            razao = km_total / km_atendido
            if r["razao_deslocamento"] is None or not perto(r["razao_deslocamento"], razao):
                erros.append(f"[R10] resumo.razao_deslocamento={r['razao_deslocamento']}, km_total ÷ km_exigido_atendido={razao:.3f}")
        elif r["razao_deslocamento"] is not None:
            erros.append("[R10] resumo.razao_deslocamento deve ser null quando nenhum segmento-alvo foi atendido")
    else:
        for campo in ("km_total", "km_sem_captura", "km_exigido_atendido", "razao_deslocamento", "duracao_estimada_min"):
            if r[campo] is not None:
                erros.append(f"[R10] resumo.{campo} deve ser null em plano de cobertura")

    # R11 — geometrias perto da área (pega, por exemplo, latitude e longitude trocadas)
    if len(areas) == 1:
        g = areas[0]["geometry"]
        poligonos = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        pts = [pt for pol in poligonos for anel in pol for pt in anel]
        lon_min = min(p[0] for p in pts) - MARGEM_GRAUS
        lon_max = max(p[0] for p in pts) + MARGEM_GRAUS
        lat_min = min(p[1] for p in pts) - MARGEM_GRAUS
        lat_max = max(p[1] for p in pts) + MARGEM_GRAUS
        for f in segs + sessoes + pontos:
            coords = f["geometry"]["coordinates"]
            coords = [coords] if f["geometry"]["type"] == "Point" else coords
            fora = [c for c in coords if not (lon_min <= c[0] <= lon_max and lat_min <= c[1] <= lat_max)]
            if fora:
                quem = f["properties"].get("id", f["properties"]["tipo"])
                erros.append(f"[R11] {quem}: {len(fora)} coordenada(s) longe da área (ordem [lon, lat] trocada?)")

    # Pontos: a sessão citada precisa existir
    for pt in pontos:
        s = pt["properties"]["sessao"]
        if s is not None and s not in ids_ses:
            erros.append(f"[R4] ponto cita sessão '{s}', que não existe")

    # R14 — início e fim das sessões
    erros.extend(_inicios_e_fins(sessoes, pontos, par, meta["estado"]))
    return erros


def _marcas() -> tuple[str, str]:
    """✓ e ✗ quando o terminal aceita; texto simples quando não (ex.: saída redirecionada em cp1252)."""
    try:
        "✓✗".encode(sys.stdout.encoding or "ascii")
        return "✓", "✗"
    except (UnicodeError, LookupError):
        return "OK", "ERRO"


def main(caminhos: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if not caminhos:
        print(__doc__)
        return 1
    certo, errado = _marcas()
    ok = True
    for caminho in caminhos:
        try:
            plano = json.loads(Path(caminho).read_text(encoding="utf-8"))
        except OSError as e:
            erros = [f"[arquivo] não foi possível ler: {e.strerror or e}"]
        except ValueError as e:  # JSON malformado ou arquivo que não está em UTF-8
            erros = [f"[arquivo] não é um JSON válido em UTF-8: {e}"]
        else:
            erros = validar(plano)
        if erros:
            ok = False
            print(f"{errado} {caminho}: {len(erros)} erro(s)")
            for e in erros:
                print(f"   {e}")
        else:
            print(f"{certo} {caminho}: plano válido")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
