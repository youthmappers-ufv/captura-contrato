# captura-contrato

Contrato do **plano de captura** do projeto P13 — Planejador de captura de imagens de rua, do Programa Youthmappers UFV.

O plano de captura é o formato que o motor de planejamento ([`captura-motor`](../captura-motor), pesquisa de iniciação científica) produz e que a aplicação ([`captura-app`](../captura-app), TCC 1 e TCC 2) exibe, exporta e leva a campo. Este repositório é o acordo entre as três partes: o que cada uma pode esperar das outras, verificado por testes.

**Versão:** 0.1.0 (proposta; pode mudar sem compatibilidade até a 1.0.0).

## Arquivos

| Arquivo | Para que serve |
|---|---|
| [`contrato-plano-captura.md`](contrato-plano-captura.md) | Documento do contrato: significado de cada campo, regras R1 a R15, decisões e questões em aberto. **Comece por aqui.** |
| [`plano-captura.schema.json`](plano-captura.schema.json) | Esquema JSON (Draft 2020-12): estrutura, tipos e valores permitidos. |
| [`validar_plano.py`](validar_plano.py) | Validador: confere o esquema e as regras de consistência. |
| [`exemplo-plano.geojson`](exemplo-plano.geojson) | Plano de exemplo válido, com dados fictícios. |
| [`motor_interface.py`](motor_interface.py) | Interface Python do motor, erros previstos e um motor falso (`MotorDeExemplo`). |
| [`test_contrato.py`](test_contrato.py) | Testes: o exemplo é válido e cada regra recusa um plano com defeito. |

## Uso

Requer Python 3.11 ou mais novo.

```bash
pip install pytest "jsonschema[format]"
pytest -q
python validar_plano.py meu-plano.geojson
```

Nos testes de outro repositório:

```python
from validar_plano import validar
assert validar(plano) == []
```

Os repositórios `captura-motor` e `captura-app` usam este contrato **sempre numa versão fixa** (etiqueta Git, por exemplo `v0.1.0`).

## Como mudar o contrato

Ninguém muda o contrato sozinho. O processo está na seção 13 do documento: *issue*, registro de decisão, *pull request* que muda juntos o esquema, o documento, o exemplo, o validador e os testes, aprovação do orientador e nova etiqueta.
