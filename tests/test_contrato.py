"""Testes de contrato do plano de captura.

Rodar com:  pip install pytest "jsonschema[format]"  &&  pytest -q

Há três tipos de teste:
- o exemplo oficial precisa ser válido;
- cada regra precisa ser capaz de recusar um plano errado. Para isso,
  partimos do exemplo, introduzimos um único defeito e conferimos que o
  validador acusa exatamente a regra esperada. Se alguém enfraquecer o
  validador sem querer, estes testes falham;
- a linha de comando precisa responder com mensagem, e não com erro do
  Python, quando o arquivo falta, está malformado ou a saída é redirecionada.

Nos repositórios do motor (IC) e da aplicação (TCCs), o mesmo padrão se
aplica aos planos que cada um produz ou consome.
"""
import copy
import json
import os
import subprocess
import sys

import pytest

from captura_contrato import carregar_exemplo, validar

EXEMPLO = carregar_exemplo()


def feature(plano, tipo, id_):
    return next(f for f in plano["features"]
                if f["properties"]["tipo"] == tipo and f["properties"].get("id") == id_)


def test_exemplo_e_valido():
    assert validar(EXEMPLO) == []


def test_recursos_do_pacote():
    # esquema e exemplo vão dentro do pacote instalado, e o exemplo segue o formato atual
    from captura_contrato import VERSAO_FORMATO, carregar_esquema
    assert carregar_esquema()["$id"].endswith("plano-captura.schema.json")
    assert EXEMPLO["versao_formato"] == VERSAO_FORMATO
    assert carregar_exemplo() is not carregar_exemplo()  # cópia nova a cada chamada


def test_comando_validar_plano_instalado(tmp_path):
    import shutil
    comando = shutil.which("validar-plano")
    if comando is None:
        pytest.skip("pacote não instalado com o comando validar-plano")
    arquivo = tmp_path / "p.geojson"
    arquivo.write_text(json.dumps(EXEMPLO), encoding="utf-8")
    assert subprocess.run([comando, str(arquivo)], capture_output=True).returncode == 0


# --- estrutura e referências -------------------------------------------------
def _defeito_campo_desconhecido(p):
    p["plano"]["parametros"]["camerra"] = "frontal"  # erro de digitação


def _defeito_anel_degenerado(p):
    feature(p, "area", None)["geometry"]["coordinates"] = [[[-46.2485, -19.1845]] * 4]


def _defeito_ponto_duplicado(p):
    partida = next(f for f in p["features"] if f["properties"].get("papel") == "partida")
    p["features"].append(copy.deepcopy(partida))


def _defeito_ordem_com_falha(p):
    feature(p, "sessao", "ses2")["properties"]["ordem"] = 3


def _defeito_segmento_inexistente(p):
    feature(p, "sessao", "ses1")["properties"]["passagens"][0]["segmento"] = "s99"


def _defeito_coordenada_invertida(p):
    # lat/lon trocados: -46 não é latitude válida
    feature(p, "segmento", "s1")["geometry"]["coordinates"][0] = [-19.1850, -46.2480]


# --- contramão ---------------------------------------------------------------
def _defeito_mao_unica_inverso(p):
    feature(p, "sessao", "ses2")["properties"]["passagens"][0]["sentido"] = "inverso"


def _defeito_contramao_sem_captura(p):
    # s4 passa a ser mão única de C para F; a sessão 2 a percorre de F para C, sem captura
    s4 = feature(p, "segmento", "s4")
    s4["properties"]["mao_unica"] = True
    s4["geometry"]["coordinates"].reverse()


# --- exigência e atendimento -------------------------------------------------
def _defeito_exigencia_incoerente(p):
    feature(p, "segmento", "s4")["properties"]["exigencia"] = "qualquer_sentido"


def _defeito_obrigatorio_esquecido(p):
    ses = feature(p, "sessao", "ses1")["properties"]
    ses["passagens"] = [x for x in ses["passagens"] if x["segmento"] != "s3"]


def _defeito_nao_atendido_que_nao_e_alvo(p):
    p["plano"]["segmentos_nao_atendidos"].append({"segmento": "s4", "motivo": "outro"})


def _defeito_nao_atendido_que_foi_atendido(p):
    p["plano"]["segmentos_nao_atendidos"].append({"segmento": "s1", "motivo": "inalcancavel"})


# --- referência linear -------------------------------------------------------
def _defeito_passagem_no_trecho_errado(p):
    # s7 declarado sobre os primeiros metros da sessão 2, que na verdade são o s4
    feature(p, "sessao", "ses2")["properties"]["passagens"][0].update(inicio_m=0.0, fim_m=111.2)


def _defeito_sentido_declarado_falso(p):
    # a sessão 2 percorre o s6 de A para D (inverso); declarar "direto" é falso
    feature(p, "sessao", "ses2")["properties"]["passagens"][1]["sentido"] = "direto"


# --- totais, limites e resumo ------------------------------------------------
def _defeito_duracao_de_sessao_nula(p):
    feature(p, "sessao", "ses1")["properties"]["duracao_estimada_min"] = 0.0


def _defeito_sessao_estoura_limite(p):
    p["plano"]["parametros"]["limite_sessao"]["duracao_max_min"] = 1


def _defeito_sessao_estoura_distancia(p):
    p["plano"]["parametros"]["limite_sessao"]["distancia_max_km"] = 0.4


def _defeito_resumo_errado(p):
    p["plano"]["resumo"]["n_sessoes"] = 3


def _defeito_km_alvo_errado(p):
    p["plano"]["resumo"]["km_alvo"] = 9.0


def _defeito_razao_errada(p):
    p["plano"]["resumo"]["razao_deslocamento"] = 5.0


def _defeito_duracao_do_resumo_errada(p):
    p["plano"]["resumo"]["duracao_estimada_min"] = 999


# --- segmento coerente -------------------------------------------------------
def _defeito_comprimento_de_segmento_falso(p):
    feature(p, "segmento", "s5")["properties"]["comprimento_m"] = 30.0
    p["plano"]["resumo"]["km_rede_modo"] = 0.679  # resumo coerente com o valor falso


def _defeito_segmento_maior_que_o_maximo(p):
    p["plano"]["parametros"]["segmento_max_m"] = 50


def _defeito_atual_com_imagem_antiga(p):
    feature(p, "segmento", "s4")["properties"]["ultima_imagem"] = "2010-01-01"


def _defeito_desatualizado_sem_data(p):
    s2 = feature(p, "segmento", "s2")["properties"]
    s2["ultima_imagem"] = None
    s2["provedor_ultima_imagem"] = None


def _defeito_provedor_sem_imagem(p):
    feature(p, "segmento", "s1")["properties"]["provedor_ultima_imagem"] = "mapillary"


@pytest.mark.parametrize("defeito, regra", [
    (_defeito_campo_desconhecido, "[esquema]"),
    (_defeito_anel_degenerado, "[R1]"),
    (_defeito_ponto_duplicado, "[R2]"),
    (_defeito_ordem_com_falha, "[R3]"),
    (_defeito_segmento_inexistente, "[R4]"),
    (_defeito_mao_unica_inverso, "[R5]"),
    (_defeito_contramao_sem_captura, "[R5]"),
    (_defeito_exigencia_incoerente, "[R6]"),
    (_defeito_passagem_no_trecho_errado, "[R7]"),
    (_defeito_sentido_declarado_falso, "[R7]"),
    (_defeito_duracao_de_sessao_nula, "[R8]"),
    (_defeito_obrigatorio_esquecido, "[R9]"),
    (_defeito_nao_atendido_que_nao_e_alvo, "[R9]"),
    (_defeito_nao_atendido_que_foi_atendido, "[R9]"),
    (_defeito_resumo_errado, "[R10]"),
    (_defeito_km_alvo_errado, "[R10]"),
    (_defeito_razao_errada, "[R10]"),
    (_defeito_duracao_do_resumo_errada, "[R10]"),
    (_defeito_coordenada_invertida, "[R11]"),
    (_defeito_sessao_estoura_limite, "[R12]"),
    (_defeito_sessao_estoura_distancia, "[R12]"),
    (_defeito_comprimento_de_segmento_falso, "[R13]"),
    (_defeito_segmento_maior_que_o_maximo, "[R13]"),
    (_defeito_atual_com_imagem_antiga, "[R13]"),
    (_defeito_desatualizado_sem_data, "[R13]"),
    (_defeito_provedor_sem_imagem, "[R13]"),
])
def test_validador_recusa_defeito(defeito, regra):
    plano = copy.deepcopy(EXEMPLO)
    defeito(plano)
    erros = validar(plano)
    assert erros, "o validador deveria ter recusado o plano"
    assert any(e.startswith(regra) for e in erros), erros


def _defeito_km_exigido_errado(p):
    p["plano"]["resumo"]["km_exigido"] = 1.0


def _defeito_atendido_inclui_nao_atendido(p):
    # s3 vira não atendido, mas o resumo continua contando-o como atendido
    p.update(_com_s3_nao_atendido(p))
    p["plano"]["resumo"]["km_exigido_atendido"] = 0.544
    p["plano"]["resumo"]["razao_deslocamento"] = 1.386


def _defeito_razao_pelo_alvo_antigo(p):
    # a razão calculada pela definição antiga (km_total ÷ km_alvo) deixa de valer
    p.update(_com_s3_nao_atendido(p))
    p["plano"]["resumo"]["razao_deslocamento"] = 1.386


@pytest.mark.parametrize("defeito", [_defeito_km_exigido_errado, _defeito_atendido_inclui_nao_atendido,
                                     _defeito_razao_pelo_alvo_antigo])
def test_validador_recusa_resumo_incoerente(defeito):
    plano = copy.deepcopy(EXEMPLO)
    defeito(plano)
    assert any(e.startswith("[R10]") for e in validar(plano)), validar(plano)


# --- razão de deslocamento ---------------------------------------------------
def _com_s3_nao_atendido(p):
    """O s3 é percorrido sem captura e declarado não atendido; os totais acompanham."""
    p = copy.deepcopy(p)
    ses1 = feature(p, "sessao", "ses1")["properties"]
    ses1["passagens"] = [x for x in ses1["passagens"] if x["segmento"] != "s3"]
    ses1.update(km_captura=0.21, km_sem_captura=0.111)
    p["plano"]["segmentos_nao_atendidos"] = [{"segmento": "s3", "motivo": "outro", "detalhe": "teste"}]
    p["plano"]["resumo"].update(km_sem_captura=0.321, km_exigido_atendido=0.4324,
                                razao_deslocamento=round(0.754 / 0.4324, 3))
    return p


def test_razao_ignora_segmentos_nao_atendidos():
    # Pela definição antiga a razão cairia para 0,754 ÷ 0,544; agora sobe, porque menos foi capturado
    plano = _com_s3_nao_atendido(EXEMPLO)
    assert validar(plano) == []
    r = plano["plano"]["resumo"]
    assert r["razao_deslocamento"] > 1
    assert r["km_exigido_atendido"] / r["km_exigido"] < 1  # fração atendida


def test_camera_frontal_conta_os_dois_sentidos():
    # Com câmera frontal, s1, s2 e s6 (mão dupla) exigem duas passadas; o exemplo só faz uma
    plano = copy.deepcopy(EXEMPLO)
    plano["plano"]["parametros"]["camera"] = "frontal"
    for sid in ("s1", "s2", "s6"):
        feature(plano, "segmento", sid)["properties"]["exigencia"] = "dois_sentidos"
    plano["plano"]["segmentos_nao_atendidos"] = [
        {"segmento": sid, "motivo": "outro", "detalhe": "falta o sentido inverso"} for sid in ("s1", "s2", "s6")]
    km_exigido = (2 * (105 + 105 + 111.2) + 111.2 + 111.2) / 1000   # 0,8648
    km_atendido = (111.2 + 111.2) / 1000                            # s3 e s7
    plano["plano"]["resumo"].update(km_exigido=round(km_exigido, 4), km_exigido_atendido=km_atendido,
                                    razao_deslocamento=round(0.754 / km_atendido, 3))
    assert validar(plano) == []
    plano["plano"]["resumo"]["km_exigido"] = 0.544   # contar uma vez só é recusado
    assert any(e.startswith("[R10] resumo.km_exigido=") for e in validar(plano))


def test_motor_de_exemplo_produz_planos_validos():
    # Modelo do teste que o TCC 1 roda contra qualquer motor (de exemplo ou real)
    from captura_contrato import MotorDeExemplo
    motor = MotorDeExemplo()
    cobertura = motor.analisar_cobertura({}, {})
    assert validar(cobertura) == []
    assert validar(motor.planejar(cobertura, ajustes={"s5": "excluido"}, parametros={"camera": "frontal"})) == []


@pytest.mark.parametrize("entrada", [
    {"ajustes": {"s99": "excluido"}},              # segmento inexistente
    {"ajustes": {"s1": "talvez"}},                 # valor inválido
    {"parametros": {"idade_maxima_dias": 30}},     # parâmetro de cobertura não muda em planejar()
])
def test_planejar_recusa_entradas_invalidas(entrada):
    from captura_contrato import MotorDeExemplo, ParametrosInvalidos
    motor = MotorDeExemplo()
    with pytest.raises(ParametrosInvalidos):
        motor.planejar(motor.analisar_cobertura({}, {}), **entrada)


def test_planejar_recusa_plano_que_nao_e_de_cobertura():
    from captura_contrato import MotorDeExemplo, ParametrosInvalidos
    with pytest.raises(ParametrosInvalidos):
        MotorDeExemplo().planejar(copy.deepcopy(EXEMPLO))


# --- cobertura parcial, segmentos fora da área, velocidades e base ------------
def _segmento_de_deslocamento():
    """Segmento fora da área, só para deslocamento: não é alvo nem entra no resumo."""
    return {"type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[-46.248, -19.186], [-46.249, -19.186]]},
            "properties": {"tipo": "segmento", "id": "x1", "osm_way_id": 1000009, "nome": None,
                           "classe_via": "residential", "comprimento_m": 105.0, "mao_unica": False,
                           "na_area": False, "estado": None, "fracao_com_imagem": None, "fracao_atual": None,
                           "ultima_imagem": None, "provedor_ultima_imagem": None,
                           "exigencia": "nenhuma", "ajuste": None}}


def test_segmento_fora_da_area_e_aceito_e_fica_fora_do_resumo():
    plano = copy.deepcopy(EXEMPLO)
    plano["features"].append(_segmento_de_deslocamento())
    assert validar(plano) == []


def test_sem_imagem_com_cobertura_parcial_e_aceito():
    # metade do segmento tem imagem recente: abaixo de fracao_min (0,8), continua sem_imagem e alvo
    plano = copy.deepcopy(EXEMPLO)
    feature(plano, "segmento", "s1")["properties"].update(
        fracao_com_imagem=0.5, fracao_atual=0.5, ultima_imagem="2026-09-01", provedor_ultima_imagem="panoramax")
    assert validar(plano) == []


def _defeito_estado_contradiz_fracoes(p):
    feature(p, "segmento", "s2")["properties"]["estado"] = "sem_imagem"  # 0,9 com imagem ≥ 0,8 → desatualizado


def _defeito_fracao_atual_maior(p):
    feature(p, "segmento", "s4")["properties"]["fracao_com_imagem"] = 0.85


def _defeito_desatualizado_com_imagem_recente(p):
    feature(p, "segmento", "s2")["properties"]["ultima_imagem"] = "2026-09-01"


def _defeito_ajuste_fora_da_area(p):
    seg = _segmento_de_deslocamento()
    seg["properties"]["ajuste"] = "incluido"
    p["features"].append(seg)


def _defeito_fora_da_area_como_alvo(p):
    seg = _segmento_de_deslocamento()
    seg["properties"]["exigencia"] = "qualquer_sentido"
    p["features"].append(seg)


def _defeito_resumo_conta_fora_da_area(p):
    p["features"].append(_segmento_de_deslocamento())
    p["plano"]["resumo"].update(n_segmentos=8, km_rede_modo=0.859)


def _defeito_duracao_abaixo_do_movimento(p):
    feature(p, "sessao", "ses2")["properties"]["duracao_estimada_min"] = 1.0  # mínimo: 0,888 + 0,63 min


def _defeito_vertice_fora_da_rede(p):
    # vértice no meio de s1, sem mudar o comprimento: o trecho não coincide com nenhum segmento
    feature(p, "sessao", "ses1")["geometry"]["coordinates"].insert(1, [-46.2475, -19.185])


def _defeito_sessoes_desencadeadas(p):
    feature(p, "sessao", "ses2")["geometry"]["coordinates"].pop(0)  # começa em C, não em F


def _defeito_base_exige_partida_em_toda_sessao(p):
    p["plano"]["parametros"]["sessoes_partem_da_base"] = True


def _defeito_partida_sem_ponto(p):
    p["features"] = [f for f in p["features"] if f["properties"].get("papel") != "partida"]


def _defeito_base_sem_partida(p):
    p["plano"]["parametros"].update(sessoes_partem_da_base=True, partida=None)
    p["features"] = [f for f in p["features"] if f["properties"].get("papel") != "partida"]


def _defeito_ponto_de_sessao_fora_da_linha(p):
    p["features"].append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [-46.247, -19.185]},
                          "properties": {"tipo": "ponto", "papel": "partida", "sessao": "ses2"}})


@pytest.mark.parametrize("defeito, regra", [
    (_defeito_estado_contradiz_fracoes, "[R13]"),
    (_defeito_fracao_atual_maior, "[R13]"),
    (_defeito_desatualizado_com_imagem_recente, "[R13]"),
    (_defeito_ajuste_fora_da_area, "[R6]"),
    (_defeito_fora_da_area_como_alvo, "[R6]"),
    (_defeito_resumo_conta_fora_da_area, "[R10]"),
    (_defeito_duracao_abaixo_do_movimento, "[R8]"),
    (_defeito_vertice_fora_da_rede, "[R15]"),
    (_defeito_sessoes_desencadeadas, "[R14]"),
    (_defeito_base_exige_partida_em_toda_sessao, "[R14]"),
    (_defeito_partida_sem_ponto, "[R14]"),
    (_defeito_base_sem_partida, "[R14]"),
    (_defeito_ponto_de_sessao_fora_da_linha, "[R14]"),
])
def test_validador_recusa_defeito_de_modelagem(defeito, regra):
    plano = copy.deepcopy(EXEMPLO)
    defeito(plano)
    erros = validar(plano)
    assert any(e.startswith(regra) for e in erros), erros


# --- linha de comando --------------------------------------------------------
def _cli(*argumentos, codificacao="utf-8"):
    ambiente = {**os.environ, "PYTHONIOENCODING": codificacao}
    ambiente.pop("PYTHONUTF8", None)
    r = subprocess.run([sys.executable, "-m", "captura_contrato.validar_plano", *map(str, argumentos)],
                       capture_output=True, env=ambiente)
    return r.returncode, r.stdout.decode(codificacao, errors="replace"), r.stderr.decode(errors="replace")


@pytest.fixture
def arquivo_exemplo(tmp_path):
    caminho = tmp_path / "exemplo-plano.geojson"
    caminho.write_text(json.dumps(EXEMPLO, ensure_ascii=False), encoding="utf-8")
    return caminho


def test_cli_aceita_o_exemplo(arquivo_exemplo):
    codigo, saida, _ = _cli(arquivo_exemplo)
    assert codigo == 0 and "plano válido" in saida


def test_cli_funciona_com_saida_em_cp1252(arquivo_exemplo):
    # No Windows, a saída redirecionada usa cp1252, que não tem os símbolos ✓ e ✗
    codigo, saida, erro = _cli(arquivo_exemplo, codificacao="cp1252")
    assert codigo == 0, erro
    assert saida.startswith("OK ") and "plano válido" in saida


def test_cli_arquivo_inexistente(tmp_path):
    codigo, saida, erro = _cli(tmp_path / "nao-existe.geojson")
    assert codigo == 1 and "[arquivo]" in saida and "Traceback" not in erro


def test_cli_json_malformado(tmp_path):
    ruim = tmp_path / "ruim.geojson"
    ruim.write_text("{", encoding="utf-8")
    codigo, saida, erro = _cli(ruim)
    assert codigo == 1 and "[arquivo]" in saida and "Traceback" not in erro


def test_cli_continua_apos_arquivo_ruim(tmp_path, arquivo_exemplo):
    codigo, saida, _ = _cli(tmp_path / "nao-existe.geojson", arquivo_exemplo)
    assert codigo == 1 and "plano válido" in saida
