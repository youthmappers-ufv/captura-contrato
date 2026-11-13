# captura-contrato

Contrato do **plano de captura** do projeto P13 — Planejador de captura de imagens de rua, do Programa Youthmappers UFV.

O plano de captura é o formato que o motor de planejamento (`captura-motor`, pesquisa de iniciação científica) produz e que a aplicação (`captura-app`, TCC 1 e TCC 2) exibe, exporta e leva a campo. Este repositório é o acordo entre as três partes: o que cada uma pode esperar das outras, verificado por testes.

**Formato:** 0.1.0 · **Pacote:** 0.1.2 · proposta, pode mudar sem compatibilidade até a 1.0.0. A diferença entre as duas versões está na seção 3 do documento.

## Arquivos

| Arquivo | Para que serve |
|---|---|
| [`contrato-plano-captura.md`](contrato-plano-captura.md) | Documento do contrato: significado de cada campo, regras R1 a R15, decisões e questões em aberto. **Comece por aqui.** |
| [`src/captura_contrato/plano-captura.schema.json`](src/captura_contrato/plano-captura.schema.json) | Esquema JSON (Draft 2020-12): estrutura, tipos e valores permitidos. |
| [`src/captura_contrato/validar_plano.py`](src/captura_contrato/validar_plano.py) | Validador: confere o esquema e as regras de consistência. |
| [`src/captura_contrato/exemplo-plano.geojson`](src/captura_contrato/exemplo-plano.geojson) | Plano de exemplo válido, com dados fictícios. |
| [`src/captura_contrato/motor_interface.py`](src/captura_contrato/motor_interface.py) | Interface Python do motor, erros previstos e um motor falso (`MotorDeExemplo`). |
| [`tests/test_contrato.py`](tests/test_contrato.py) | Testes: o exemplo é válido e cada regra recusa um plano com defeito. |

## Instalação

Requer Python 3.11 ou mais novo. Em outro repositório, sempre numa etiqueta fixa:

```bash
pip install "captura-contrato @ git+https://github.com/youthmappers-ufv/captura-contrato@v0.1.2"
```

Para trabalhar neste repositório:

```bash
pip install -e ".[dev]"
pytest -q
mypy
```

## Uso

```bash
validar-plano meu-plano.geojson
```

```python
from captura_contrato import MotorDeExemplo, carregar_exemplo, validar

assert validar(carregar_exemplo()) == []

motor = MotorDeExemplo()
cobertura = motor.analisar_cobertura(area, parametros)
plano = motor.planejar(cobertura, ajustes={"s5": "excluido"})
```

## Como mudar o contrato

Ninguém muda o contrato sozinho. O processo está na seção 13 do documento: *issue*, registro de decisão, *pull request* que muda juntos o esquema, o documento, o exemplo, o validador e os testes, aprovação do orientador e nova etiqueta. Etiquetas publicadas nunca são movidas nem apagadas.
