# Contrato do plano de captura — formato 0.1.0 (pacote 0.1.2)

Projeto P13 — Planejador de captura de imagens de rua · Programa Youthmappers UFV
Estado: **proposta** (versão 0.x, sujeita a mudanças sem compatibilidade até a 1.0.0) · Outubro de 2026
Texto sob [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pt-br); esquema, validador e exemplo sob [MIT](LICENSE).

---

## Sumário

1. [O que é um contrato e por que precisamos de um](#1-o-que-é-um-contrato-e-por-que-precisamos-de-um)
2. [Quem produz e quem consome](#2-quem-produz-e-quem-consome)
3. [Os arquivos deste contrato](#3-os-arquivos-deste-contrato)
4. [Convenções](#4-convenções)
5. [Visão geral do plano](#5-visão-geral-do-plano)
6. [Os campos, um a um](#6-os-campos-um-a-um)
7. [Regras de consistência (R1 a R15)](#7-regras-de-consistência-r1-a-r15)
8. [Exemplo comentado](#8-exemplo-comentado)
9. [Interface do motor (Python)](#9-interface-do-motor-python)
10. [O mínimo que a API HTTP precisa garantir](#10-o-mínimo-que-a-api-http-precisa-garantir)
11. [Correspondência com GPX e KML (informativo)](#11-correspondência-com-gpx-e-kml-informativo)
12. [Como validar um plano](#12-como-validar-um-plano)
13. [Versionamento e processo de mudança](#13-versionamento-e-processo-de-mudança)
14. [Decisões de projeto e alternativas descartadas](#14-decisões-de-projeto-e-alternativas-descartadas)
15. [Questões em aberto](#15-questões-em-aberto)
16. [Glossário](#16-glossário)

---

## 1. O que é um contrato e por que precisamos de um

Pense numa tomada elétrica. O fabricante da geladeira e a construtora da casa nunca conversaram, mas a geladeira funciona na casa porque os dois seguem a mesma norma de plugue e tensão. A norma é o **contrato**: diz o que cada lado pode esperar do outro, sem que um precise saber como o outro foi feito.

No P13 temos três equipes que trabalham em momentos diferentes e talvez nunca se encontrem:

- a **pesquisa (IC)**, que escreve o motor de planejamento;
- o **TCC 1**, que escreve a aplicação web de planejamento e a API;
- o **TCC 2**, que escreve o modo campo (PWA).

O risco, sem contrato, é cada um modelar "rota", "sessão" e "segmento" do seu jeito e a integração virar um projeto à parte que ninguém tem tempo de fazer. Este documento evita isso de três formas:

1. **Define um formato de arquivo** (o *plano de captura*) que o motor produz, a aplicação exibe e exporta, e o modo campo carrega.
2. **Define a interface do motor**: quais funções a API chama e o que elas devolvem.
3. **Define as regras de mudança**: ninguém altera o formato sozinho; toda mudança passa por um processo e por testes automáticos.

Um contrato bom tem duas partes. A **parte que a máquina confere** é o esquema JSON e o validador: se um arquivo não seguir o contrato, o teste falha antes de chegar a outro aluno. A **parte que as pessoas leem** é este documento, que explica o significado de cada campo e o porquê de cada decisão. As duas precisam andar juntas: um campo novo no esquema sem explicação aqui é um contrato pela metade.

### Como ler os termos normativos

Seguindo a convenção das especificações técnicas (RFC 2119), algumas palavras têm sentido preciso:

| Termo | Significado |
|---|---|
| **DEVE** / **NÃO DEVE** | Obrigatório. Um plano que viola isso é inválido. |
| **DEVERIA** | Recomendado. Só se descumpre com um bom motivo, registrado. |
| **PODE** | Opcional. |

---

## 2. Quem produz e quem consome

```
          ┌──────────────────────┐
          │  Motor (pesquisa IC) │  produz o plano
          └──────────┬───────────┘
                     │ chamada Python: analisar_cobertura() / planejar()
          ┌──────────▼───────────┐
          │  API + aplicação web │  guarda, exibe, permite ajustes,
          │       (TCC 1)        │  exporta GPX/KML/GeoJSON
          └──────────┬───────────┘
                     │ HTTP: GET /api/v1/planos/{id}  ou arquivo .geojson
          ┌──────────▼───────────┐
          │  Modo campo / PWA    │  carrega o plano, guia a coleta,
          │       (TCC 2)        │  marca o progresso
          └──────────────────────┘
```

| Parte | Papel no contrato | O que precisa cumprir |
|---|---|---|
| Motor (IC) | Produtor | Todo plano gerado DEVE passar no validador. |
| API e aplicação (TCC 1) | Consumidor e repassador | DEVE aceitar qualquer plano válido; NÃO DEVE alterar o plano ao repassá-lo, exceto nos campos de ajuste e nome. |
| Modo campo (TCC 2) | Consumidor | DEVE aceitar qualquer plano válido; DEVE ignorar campos que não conhece (ver seção 13). |
| Orientador | Dono do contrato | Aprova mudanças, mantém este documento e a versão. |

---

## 3. Os arquivos deste contrato

| Arquivo | Para que serve |
|---|---|
| `contrato-plano-captura.md` | Este documento: significado, regras e decisões. |
| `src/captura_contrato/plano-captura.schema.json` | Esquema JSON (padrão *Draft 2020-12*): estrutura, tipos e valores permitidos. |
| `src/captura_contrato/validar_plano.py` | Validador: confere o esquema e as regras R1 a R15. Usável na linha de comando (`validar-plano`) e nos testes. |
| `src/captura_contrato/exemplo-plano.geojson` | Plano de exemplo, **com dados fictícios**, válido. É a referência comum dos testes. |
| `src/captura_contrato/motor_interface.py` | Interface Python do motor, erros previstos e um motor falso (`MotorDeExemplo`). |
| `tests/test_contrato.py` | Testes automáticos: o exemplo é válido, e cada regra recusa um plano com defeito. |

Os arquivos ficam no repositório próprio `captura-contrato`, separado do motor (`captura-motor`) e da aplicação (`captura-app`): a aplicação depende do contrato, mas não do motor. O repositório é um pacote Python instalável (`captura_contrato`), com o esquema e o exemplo dentro do pacote; os outros repositórios o instalam sempre numa etiqueta Git fixa, por exemplo:

```toml
dependencies = ["captura-contrato @ git+https://github.com/youthmappers-ufv/captura-contrato@v0.1.2"]
```

**Duas versões.** A versão do **formato** (`versao_formato` nos arquivos e `VERSAO_FORMATO` no pacote) muda só quando o formato muda. A versão do **pacote** (`captura_contrato.__version__` e a etiqueta Git) muda também com correções de documentação, validador ou empacotamento. Assim, o pacote 0.1.2 ainda descreve o formato 0.1.0.

---

## 4. Convenções

**Formato base.** O plano é um **GeoJSON** (RFC 7946) do tipo `FeatureCollection`. Isso significa que ele abre diretamente no QGIS, no geojson.io e no MapLibre, o que facilita muito a depuração: se um plano parece errado, basta arrastá-lo para o QGIS.

**Coordenadas.** Sempre `[longitude, latitude]`, nesta ordem, em WGS 84 (EPSG:4326). É a ordem exigida pelo GeoJSON e a fonte mais comum de erro, porque muita gente pensa em "lat, lon". Em Rio Paranaíba, a longitude fica perto de -46,2 e a latitude perto de -19,2. Recomenda-se no máximo 6 casas decimais (cerca de 10 cm), para não inflar o arquivo.

**Unidades.** Comprimentos de segmento e posições em **metros** (`_m`); distâncias de sessão e de resumo em **quilômetros** (`_km`); tempos em **minutos** (`_min`); idades em **dias**; velocidades em **km/h**. O sufixo do nome do campo sempre indica a unidade.

**Datas.** ISO 8601. Data e hora com fuso (`2026-10-14T13:00:00Z`) para registros; só data (`2026-03-02`) para a data de uma imagem.

**Nomes de campos.** Português, minúsculas, sem acento, com `_` (snake_case). Valores enumerados seguem o mesmo padrão (`sem_imagem`, `a_pe`).

**Identificadores.** O plano tem um `id` global (UUID). Segmentos e sessões têm ids locais, únicos dentro do plano (`s1`, `ses2`). Ids locais NÃO DEVEM ser usados fora do plano.

**Ausência de valor.** Campo obrigatório sem valor recebe `null`; campo opcional ausente simplesmente não aparece. A diferença importa: `"ultima_imagem": null` diz "procuramos e não há imagem", enquanto a ausência diria "não sabemos".

**Campos desconhecidos.** O esquema é **estrito**: um campo que não está nele invalida o arquivo. Isso pega erros de digitação (`camerra`) no produtor. Campos experimentais vão em `plano.extensoes`.

---

## 5. Visão geral do plano

O plano tem um cabeçalho e uma lista de *features* (feições geográficas) de quatro tipos, distinguidas por `properties.tipo`:

```
FeatureCollection
├── formato: "plano-captura"            ← "que arquivo é este?"
├── versao_formato: "0.1.0"             ← "em que versão do contrato?"
├── plano                               ← metadados (não geográficos)
│   ├── id, nome, estado, criado_em, expira_em, idioma
│   ├── gerado_por   (qual motor, versão, algoritmo, semente)
│   ├── fontes       (retrato do OSM, consultas de cobertura)
│   ├── parametros   (modo, câmera, idade máxima, limites...)
│   ├── resumo       (km, número de segmentos e sessões...)
│   ├── segmentos_nao_atendidos
│   └── extensoes    (livre)
└── features
    ├── 1 × area      Polygon/MultiPolygon  — a região escolhida
    ├── n × segmento  LineString            — trechos de via (unidade de cobertura)
    ├── k × sessao    LineString            — o caminho a percorrer, em ordem
    └── 0..j × ponto  Point                 — partida e chegada
```

### Os dois estados do plano

| `estado` | Quando | Tem sessões? | Uso |
|---|---|---|---|
| `cobertura` | Após `analisar_cobertura()` | Não | Mapa colorido "onde falta imagem"; o usuário ajusta segmentos. |
| `completo` | Após `planejar()` | Sim | Rotas para exportar e levar a campo. |

O fluxo típico na aplicação: o usuário escolhe a área → a API devolve um plano `cobertura` → o usuário vê o mapa, inclui ou exclui trechos → a API pede `planejar()` com os ajustes → devolve um plano `completo`.

### Segmento × sessão: a ideia central

É importante entender a diferença:

- O **segmento** é um pedaço de rua. Diz *o que* precisa ser fotografado e em que estado está.
- A **sessão** é o caminho que a pessoa percorre. Diz *por onde* passar e *em que ordem*.

Uma sessão passa por segmentos que precisam de imagem (trechos de **captura**) e por outros apenas para chegar ao próximo (trechos **sem captura**, o "deslocamento em vazio"). As **passagens** ligam os dois mundos: cada passagem diz "entre o metro 105 e o metro 210 desta sessão, você está capturando o segmento `s2`, no sentido direto".

Esse recurso de localizar trechos por "metros desde o início da linha" chama-se **referência linear**. Ele permite que o modo campo calcule o progresso apenas projetando a posição do GPS na linha da sessão, sem fazer cálculos de grafo no celular.

---

## 6. Os campos, um a um

Legenda da coluna "Obr.": **S** = obrigatório (pode ser `null` se o tipo permitir); **N** = opcional.

### 6.1 Raiz

| Campo | Tipo | Obr. | Significado |
|---|---|---|---|
| `type` | `"FeatureCollection"` | S | Exigência do GeoJSON. |
| `formato` | `"plano-captura"` | S | Identifica o tipo de arquivo. O modo campo usa isso para recusar um GeoJSON qualquer. |
| `versao_formato` | texto SemVer | S | Versão do contrato seguida pelo arquivo. |
| `plano` | objeto | S | Metadados (6.2). |
| `features` | lista | S | Área, segmentos, sessões e pontos (6.7 a 6.10). |

### 6.2 `plano`

| Campo | Tipo | Obr. | Significado |
|---|---|---|---|
| `id` | UUID | S | Identificador global. Usado no link compartilhável e na API. |
| `nome` | texto ou null | N | Nome dado pelo usuário ("Centro — sábado de manhã"). |
| `estado` | `cobertura` \| `completo` | S | Ver seção 5. |
| `criado_em` | data-hora | S | Quando o plano foi gerado. |
| `expira_em` | data-hora ou null | N | Quando o servidor apaga o plano. `null` = não expira. |
| `idioma` | ex.: `pt-BR` | S | Idioma dos textos (nomes, instruções). |
| `gerado_por` | objeto | S | `software`, `versao`, `algoritmo` (ex.: `B1`, `H1`) e `semente`. Permite saber exatamente o que produziu o plano. Essencial para a pesquisa comparar algoritmos. |
| `fontes` | objeto | S | `osm.data_retrato` e `osm.origem` (de quando e de onde veio a rede viária); `cobertura[]` com `provedor`, `consultado_em` e `instancia`. Sem isso, o plano não é reprodutível: a mesma área, um mês depois, dá outro resultado. |
| `parametros` | objeto | S | Ver 6.3. |
| `resumo` | objeto | S | Ver 6.4. |
| `segmentos_nao_atendidos` | lista | S | Ver 6.5. Lista vazia quando tudo foi atendido. |
| `extensoes` | objeto | N | Campos experimentais (6.6). |

### 6.3 `plano.parametros`

Guardar os parâmetros dentro do plano permite refazê-lo e explicar o resultado ("por que esta rua não entrou?" → porque a imagem dela tem menos de 730 dias).

| Campo | Tipo | Significado e exemplo |
|---|---|---|
| `modo` | `carro` \| `moto` \| `bicicleta` \| `a_pe` | Define que vias são trafegáveis e se a mão de direção vale. |
| `camera` | `panoramica_360` \| `frontal` | Define se uma via de mão dupla precisa de uma ou de duas passadas (ver 6.8). |
| `idade_maxima_dias` | inteiro ≥ 0 | Imagens mais antigas contam como desatualizadas. Ex.: 730 = dois anos. |
| `provedores` | lista de `mapillary`, `panoramax` | Serviços cuja cobertura foi considerada. |
| `segmento_max_m` | número > 0 | Tamanho máximo de um segmento. Ruas longas são divididas (regra em 6.8), para que uma imagem numa ponta não "cubra" a rua inteira. Ex.: 50. |
| `cobertura.distancia_max_m` | número > 0 | Distância máxima entre a imagem e a via para associá-las. Ex.: 10. |
| `cobertura.fracao_min` | 0 a 1 | Fração mínima do segmento com imagem para classificá-lo (regra provisória em 6.8). Ex.: 0,8. |
| `velocidade_captura_kmh` | número > 0 | Velocidade nos trechos com captura. |
| `velocidade_deslocamento_kmh` | número > 0 | Velocidade nos trechos sem captura (deslocamento em vazio), em geral maior. |
| `limite_sessao.duracao_max_min` | número ou null | Limite de cada sessão em minutos (bateria, cartão, cansaço). |
| `limite_sessao.distancia_max_km` | número ou null | Limite alternativo por distância. |
| `partida`, `chegada` | `[lon, lat]` ou null | Pontos escolhidos pelo usuário. O motor os ajusta à rede (6.10). **Atenção à privacidade** (seção 10). |
| `sessoes_partem_da_base` | booleano | `true`: toda sessão começa na partida e termina na chegada, ou na partida se não houver chegada (exige `partida`). `false`: as sessões se encadeiam; a primeira começa na partida, se houver, cada uma começa onde a anterior terminou e a última termina na chegada, se houver. |
| `preferencias` | 3 booleanos | `evitar_retornos`, `evitar_vias_rapidas`, `evitar_sem_pavimento`. |

Os parâmetros `distancia_max_m` e `fracao_min` são justamente o que a pesquisa calibra na sua questão QP3. Por isso eles ficam explícitos no plano, e não escondidos dentro do motor.

**Parâmetros de cobertura e de rota.** `modo`, `idade_maxima_dias`, `provedores`, `segmento_max_m` e `cobertura` definem a rede e a classificação dos segmentos; ficam fixados pelo plano de cobertura. Os demais são parâmetros de rota e podem mudar entre `analisar_cobertura()` e `planejar()` (seção 9).

**Sessões e base.** Com `sessoes_partem_da_base = true`, cada saída de campo começa e termina no mesmo lugar (a casa, a universidade), e o caminho de ida e volta entra em `km_total`. É o modelo usado nas instâncias da pesquisa. Com `false`, o plano é um percurso contínuo dividido em trechos, adequado a quem faz várias sessões seguidas.

### 6.4 `plano.resumo`

| Campo | Significado | Em plano `cobertura` |
|---|---|---|
| `n_segmentos` | Total de segmentos na área (`na_area = true`). | preenchido |
| `n_segmentos_alvo` | Segmentos com `exigencia ≠ nenhuma`. | preenchido |
| `km_rede_modo` | Soma dos comprimentos dos segmentos na área. | preenchido |
| `km_alvo` | Soma dos comprimentos dos segmentos-alvo, cada um contado uma vez. É o número do mapa: "quanto de rua falta". | preenchido |
| `km_exigido` | Captura mínima exigida: como `km_alvo`, mas os segmentos `dois_sentidos` contam duas vezes. | preenchido |
| `n_sessoes` | Número de sessões. | 0 |
| `km_total` | Soma das distâncias das sessões. | `null` |
| `km_sem_captura` | Parte de `km_total` sem captura. | `null` |
| `km_exigido_atendido` | Parte de `km_exigido` cujos segmentos foram atendidos pelas passagens (fora os de `segmentos_nao_atendidos`). | `null` |
| `razao_deslocamento` | `km_total ÷ km_exigido_atendido` (≥ 1). Quanto mais perto de 1, melhor. É a métrica principal da pesquisa. `null` se nada foi atendido. | `null` |
| `duracao_estimada_min` | Soma das durações das sessões. | `null` |

**Como ler a razão de deslocamento.** Ela diz quantos quilômetros a pessoa percorre para cada quilômetro de captura que o plano exige e atende. No exemplo, `km_exigido_atendido = 0,544` e `km_total = 0,754` dão 1,39: para cada quilômetro fotografado, 0,39 km é deslocamento sem captura. O valor 1 é o plano perfeito.

Três escolhas sustentam essa definição:

1. **O denominador é o que foi atendido, e não tudo o que era alvo.** Se fosse `km_alvo`, um plano que deixa trechos de fora teria `km_total` menor e pareceria melhor, podendo até ficar abaixo de 1. Com `km_exigido_atendido`, a razão nunca fica abaixo de 1, porque a sessão precisa percorrer pelo menos o que captura.
2. **Cada sentido exigido conta.** Com câmera frontal, um segmento `dois_sentidos` precisa de duas passadas; contá-lo uma vez inflaria a razão para perto de 2 mesmo num plano ótimo. Assim, 1 significa "nenhum metro em vazio" para qualquer câmera (questão Q3, resolvida).
3. **A cobertura vai em outro número.** A **fração atendida** é `km_exigido_atendido ÷ km_exigido` (1 quando tudo foi atendido). Ela não é um campo, porque deriva de dois que já existem, mas a aplicação DEVERIA exibi-la ao lado da razão. Comparar planos pela razão só é justo quando têm a mesma fração atendida.

**Deslocamento de acesso.** A razão só conta o que está desenhado nas sessões. Quando há `partida`, a sessão DEVERIA começar nela, para que o caminho até a primeira rua a fotografar entre em `km_total`; sem `partida` (opção de privacidade), a razão descreve só o percurso a partir do primeiro ponto da sessão. Na pesquisa, toda instância tem um ponto de partida, e todas as sessões começam e terminam nele.

**Distância e tempo.** O motor otimiza tempo, e com penalidade de retornos as duas medidas podem divergir. O plano guarda a razão em distância; a pesquisa reporta também a razão em tempo, calculada a partir das durações.

### 6.5 `plano.segmentos_nao_atendidos`

Nem sempre o motor consegue atender todos os segmentos-alvo: um trecho pode estar isolado da rede no modo escolhido, ou uma sessão pode estourar o limite. Em vez de esconder isso, o motor DEVE listar cada caso:

```json
"segmentos_nao_atendidos": [
  { "segmento": "s42", "motivo": "inalcancavel", "detalhe": "sem ligação viária no modo bicicleta" }
]
```

Motivos: `inalcancavel`, `limite_de_sessao`, `outro`. A aplicação DEVERIA mostrar esses trechos em destaque, para o usuário decidir o que fazer.

### 6.6 `plano.extensoes`

Um espaço livre para experimentar sem mudar o contrato. Use um prefixo com o nome do projeto, por exemplo `"p13_tempo_calculo_ms": 1840`. Nada aqui tem garantia entre versões. Um campo de extensão que se prove útil entra no contrato numa versão MINOR (seção 13).

### 6.7 Feature `area` (exatamente uma)

| Campo em `properties` | Significado |
|---|---|
| `tipo` | `"area"` |
| `origem` | `desenho` \| `arquivo` \| `nominatim` \| `relacao_osm` |
| `referencia` | Depende da origem: `r1234567` para relação OSM; o termo buscado no Nominatim; o nome do arquivo enviado. |
| `nome` | Nome legível ("Rio Paranaíba — sede urbana"). |

Geometria: `Polygon` ou `MultiPolygon` (um município com distritos, por exemplo).

### 6.8 Feature `segmento`

É o objeto mais importante. Cada segmento é um trecho de via que pode ou não precisar de imagens.

| Campo em `properties` | Significado |
|---|---|
| `tipo` | `"segmento"` |
| `id` | Id local. `planejar()` preserva os ids do plano de cobertura (seção 9). Formato recomendado em "Divisão das vias", abaixo. |
| `osm_way_id` | Id da via no OSM. Vários segmentos podem vir da mesma via. Permite abrir a via no editor. |
| `nome` | Nome da rua, se houver. |
| `classe_via` | Valor da etiqueta `highway` (`residential`, `primary`...). |
| `comprimento_m` | Comprimento do segmento. |
| `mao_unica` | Se é mão única **para o modo do plano**. Uma rua de mão única para carro pode ter `mao_unica = false` no modo bicicleta, se o contrafluxo for permitido (`oneway:bicycle=no`). No modo a pé é sempre `false`. |
| `na_area` | `true` se o segmento fica na área (pode ser alvo); `false` se está fora dela e entrou só para deslocamento (nunca é alvo, não aceita ajuste, não entra em `n_segmentos` nem em `km_rede_modo`). |
| `estado` | `sem_imagem` \| `desatualizado` \| `atual`, segundo as frações abaixo; `null` só em segmento fora da área não classificado. |
| `fracao_com_imagem` | Fração do comprimento com alguma imagem associada, de qualquer idade (0 a 1); `null` se `estado` for `null`. |
| `fracao_atual` | Fração do comprimento com imagem dentro de `idade_maxima_dias` (0 a 1, nunca maior que `fracao_com_imagem`); `null` se `estado` for `null`. |
| `ultima_imagem` | Data da imagem mais recente associada; `null` se, e somente se, `fracao_com_imagem` for 0 ou `null`. |
| `provedor_ultima_imagem` | De qual serviço veio essa imagem, ou `null`. |
| `exigencia` | O que o plano precisa fazer (tabela abaixo). |
| `ajuste` | Decisão manual: `incluido`, `excluido` ou `null`. |

**Divisão das vias.** O segmento é a unidade de cobertura, e as vias DEVEM ser divididas em segmentos, nesta ordem:

1. cada via do OSM é cortada nos nós que compartilha com outras vias trafegáveis no modo (cruzamentos);
2. cada trecho entre cruzamentos maior que `segmento_max_m` é dividido em partes iguais, com o menor número de partes que fique dentro do limite.

O id DEVERIA ser `w{osm_way_id}_{k}`, com `k` contado a partir de 1 no sentido de desenho da via no OSM (antes de qualquer inversão por `oneway=-1`). Assim, o mesmo retrato do OSM e o mesmo `segmento_max_m` dão sempre os mesmos ids. O exemplo usa `s1` a `s7`, por ser fictício.

**Cobertura parcial (regra provisória).** Com `f = cobertura.fracao_min`:

1. `fracao_atual ≥ f` → `atual`;
2. senão, `fracao_com_imagem ≥ f` → `desatualizado`;
3. senão → `sem_imagem`.

Um segmento com metade do comprimento fotografado e `f = 0,8` é `sem_imagem`, mas tem `ultima_imagem`; o mapa pode mostrar a fração. A regra é provisória: a pesquisa a calibra na QP3 e pode trocá-la antes da 1.0.0.

**O sentido da geometria.** A ordem dos vértices da `LineString` define um sentido, chamado aqui de *sentido da geometria* ou "direto". Em vias de mão única, o produtor DEVE ordenar os vértices no sentido permitido. No OSM, uma via com `oneway=-1` tem o sentido permitido contrário ao desenho; o motor inverte a geometria para que, no plano, "direto" sempre signifique "o sentido em que se pode trafegar".

**A exigência.** Ela resume, num único campo, tudo o que o consumidor precisa saber:

| `exigencia` | Quando | O que a sessão precisa fazer |
|---|---|---|
| `nenhuma` | Segmento atual (sem ajuste) ou excluído manualmente. | Nada; pode ser usado para deslocamento. |
| `qualquer_sentido` | Alvo, mão dupla, câmera 360°. | Uma passagem, em qualquer sentido. |
| `sentido_da_geometria` | Alvo, mão única. | Uma passagem no sentido `direto`. |
| `dois_sentidos` | Alvo, mão dupla, câmera frontal. | Uma passagem `direto` e uma `inverso`. |

Regra de decisão, na ordem (é a regra R6 do validador):

1. `na_area = false` ou `ajuste = excluido` → `nenhuma`.
2. `ajuste = null` e `estado = atual` → `nenhuma`.
3. `mao_unica = true` → `sentido_da_geometria`.
4. `camera = panoramica_360` → `qualquer_sentido`.
5. Senão → `dois_sentidos`.

Note que `ajuste = incluido` torna alvo até um segmento `atual`. Exemplo real: a rua tem imagem de seis meses atrás, mas acabou de ser asfaltada, e vale fotografar de novo.

### 6.9 Feature `sessao`

| Campo em `properties` | Significado |
|---|---|
| `tipo` | `"sessao"` |
| `id` | Id local. |
| `ordem` | 1, 2, 3... sem falhas. Ordem sugerida de execução. |
| `distancia_km` | Comprimento da linha da sessão. |
| `km_captura` | Soma das passagens. |
| `km_sem_captura` | `distancia_km − km_captura`. |
| `duracao_estimada_min` | Tempo estimado. |
| `passagens` | Lista ordenada de trechos de captura (abaixo). |
| `instrucoes` | **Opcional na 0.1.** Manobras ao longo da linha. |

Geometria: uma única `LineString` contínua, do início ao fim da sessão, incluindo os trechos sem captura.

**Passagem:**

| Campo | Significado |
|---|---|
| `segmento` | Id do segmento capturado. |
| `sentido` | `direto` (no sentido da geometria do segmento) ou `inverso`. |
| `inicio_m`, `fim_m` | Posição, em metros desde o início da linha da sessão, onde a captura do segmento começa e termina. |

Uma mesma rua pode aparecer como passagem e também ser percorrida de novo sem captura; só os trechos de captura viram passagens. Para uma sessão longa, isso significa que a lista de passagens é menor do que a lista de ruas percorridas.

**Instrução** (opcional): `posicao_m`, `manobra` (`iniciar`, `seguir`, `virar_esquerda`, `virar_direita`, `manter_esquerda`, `manter_direita`, `retorno`, `rotatoria`, `chegar`) e `texto`. O modo campo DEVE funcionar sem instruções, usando só a linha e as passagens.

### 6.10 Feature `ponto`

Partida e chegada, do plano inteiro (`sessao: null`) ou de uma sessão específica (`sessao: "ses2"`).

- O ponto do plano é o ponto do usuário **ajustado à rede**: o motor escolhe o vértice de segmento mais próximo de `parametros.partida` (ou `chegada`) e registra esse vértice como feature. Os parâmetros guardam o ponto escolhido; a feature, o ponto usado.
- Em plano `completo`, há ponto de partida do plano se, e somente se, `parametros.partida` não for `null`; o mesmo vale para a chegada. Em plano `cobertura`, o ponto é opcional.
- Pontos de sessão são opcionais e DEVEM coincidir com o primeiro (partida) ou o último (chegada) vértice da linha da sessão.
- O começo e o fim de cada sessão seguem `sessoes_partem_da_base` (6.3 e regra R14).

---

## 7. Regras de consistência (R1 a R15)

O esquema JSON confere estrutura: "este campo é um número", "este valor está na lista". Mas não consegue conferir relações entre partes do arquivo, como "a passagem aponta para um segmento que existe". Essas regras ficam no validador (`validar_plano.py`), e cada uma tem um teste que prova que ela funciona.

| Regra | O que exige | Por que importa |
|---|---|---|
| **R1** | Exatamente uma área, com anéis fechados e ao menos 3 pontos distintos. | Sem área não há como recalcular o plano. |
| **R2** | Ids de segmento e de sessão únicos; no máximo um ponto de partida e um de chegada para o plano e para cada sessão. | Passagens e pontos se referem a eles. |
| **R3** | `cobertura` sem sessões; `completo` com ao menos uma; ordens 1..n sem falhas. | O modo campo exibe as sessões pela ordem. |
| **R4** | Toda passagem e todo ponto apontam para itens existentes. | Evita referências quebradas. |
| **R5** | Nenhuma passagem `inverso` em segmento de mão única, e nenhum trecho da linha da sessão, com ou sem captura, percorre um segmento de mão única na contramão. | Segurança e legalidade: não mandar ninguém na contramão. |
| **R6** | `exigencia` segue a regra da seção 6.8; nada de mão única no modo a pé; segmento fora da área nunca é alvo nem tem ajuste. | Produtor e consumidores precisam concordar sobre o que é alvo. |
| **R7** | Passagens com `inicio_m < fim_m`, dentro da linha, em ordem, com extensão igual ao comprimento do segmento e com início e fim sobre as pontas do segmento, no sentido declarado (folga de 5%). Instruções dentro da linha. | A referência linear é o que permite medir progresso em campo. |
| **R8** | Totais de cada sessão batem com a geometria e as passagens (folga de 1%); a duração não é menor que o tempo de movimento, `km_captura` à velocidade de captura mais `km_sem_captura` à velocidade de deslocamento (penalidades só acrescentam). | Números exibidos ao usuário precisam ser verdadeiros. |
| **R9** | Todo segmento-alvo é atendido pelas passagens conforme a exigência, ou está em `segmentos_nao_atendidos`, que só cita, uma vez cada, segmentos-alvo de fato não atendidos. | É a promessa central do plano: "cobre tudo, ou diz o que não cobriu". |
| **R10** | `resumo` coerente com as features, inclusive `km_alvo`, `km_exigido`, `km_exigido_atendido`, `duracao_estimada_min` e `razao_deslocamento` (`null` quando nada foi atendido); campos de sessão `null` em plano `cobertura`. | Evita resumo desatualizado depois de ajustes. |
| **R11** | Segmentos, sessões e pontos a até ~2 km da área. | Pega latitude e longitude trocadas, que passam no esquema porque os números continuam em faixas válidas. |
| **R12** | Nenhuma sessão excede `limite_sessao` (duração ou distância; folga de 1%). | O limite representa bateria, cartão e cansaço; o que não couber vai para `segmentos_nao_atendidos` com o motivo `limite_de_sessao`. |
| **R13** | Segmento coerente: `comprimento_m` bate com a geometria e não excede `segmento_max_m` (folga de 1%); `estado` segue as frações (regra provisória de 6.8), com `fracao_atual ≤ fracao_com_imagem`; `ultima_imagem` existe se, e somente se, `fracao_com_imagem > 0`, vem com o provedor e tem idade coerente com `fracao_atual` (dentro de `idade_maxima_dias` se `fracao_atual > 0`, fora se for 0), contada da consulta de cobertura mais recente; só segmento fora da área pode ter `estado` nulo. | O mapa de cobertura e a métrica principal dependem desses valores. |
| **R14** | Pontos de partida e chegada do plano existem junto com os parâmetros; as sessões começam e terminam conforme `sessoes_partem_da_base` (na base, ou encadeadas); pontos de sessão coincidem com a linha. | Sem isso, o deslocamento de acesso some de `km_total` e a razão fica otimista. |
| **R15** | Cada trecho da linha de uma sessão coincide com um trecho de algum segmento do plano. | Toda via percorrida fica conferível (contramão, comprimento, cobertura); vias fora da área entram como segmentos com `na_area = false`. |

**Como o validador confere a contramão (R5) e a rede (R15).** Ele compara os vértices da linha da sessão com os dos segmentos. Por isso a linha DEVE ser a concatenação das geometrias dos segmentos percorridos, reutilizando seus vértices, sem simplificar nem redensificar.

---

## 8. Exemplo comentado

O arquivo `exemplo-plano.geojson` descreve dois quarteirões **fictícios** perto do centro de Rio Paranaíba, com ruas inventadas ("Rua Exemplo Um" etc.) e ids OSM falsos. Não use o exemplo como dado real.

```
   A ──s1──► B ──s2──► E          s1, s2: mão dupla (desenhadas para leste)
   ▲         ▲         │          s3: mão única, para o sul (E → F)
   s6        s7        s3         s7: mão única, para o norte (C → B)
   │         │         ▼          s4, s5, s6: mão dupla
   D ◄──s5── C ◄──s4── F
```

| Seg. | Estado | Ajuste | Exigência | Por quê |
|---|---|---|---|---|
| s1 | sem_imagem | — | qualquer_sentido | Alvo, mão dupla, câmera 360°. |
| s2 | desatualizado (2019) | — | qualquer_sentido | Imagem com mais de 730 dias. |
| s3 | sem_imagem | — | sentido_da_geometria | Alvo, mão única. |
| s4 | atual (2026) | — | nenhuma | Já tem imagem recente. |
| s5 | sem_imagem | excluido | nenhuma | Usuário excluiu (ex.: rua em obras). |
| s6 | atual (2025) | incluido | qualquer_sentido | Usuário quis fotografar de novo. |
| s7 | sem_imagem | — | sentido_da_geometria | Alvo, mão única. |

As duas sessões (limite de 60 min, câmera 360°, carro):

- **Sessão 1:** A → B → E → F. Captura s1, s2 e s3 (todos no sentido direto). Sem deslocamento em vazio.
- **Sessão 2:** F → C → B → A → D. Passa por s4 sem captura (já atual), captura s7 (C → B, sentido permitido), volta por s1 sem captura (já capturado na sessão 1) e captura s6 no sentido inverso (de A para D, enquanto a geometria vai de D para A; permitido por ser mão dupla).

Trecho da sessão 1 (as posições são em metros desde A):

```json
"passagens": [
  { "segmento": "s1", "sentido": "direto", "inicio_m": 0.0,   "fim_m": 105.0 },
  { "segmento": "s2", "sentido": "direto", "inicio_m": 105.0, "fim_m": 210.0 },
  { "segmento": "s3", "sentido": "direto", "inicio_m": 210.0, "fim_m": 321.2 }
]
```

Repare que s5 não aparece em lugar nenhum das sessões: não é alvo e a rota não precisou passar por ele.

Resumo: 7 segmentos, 5 alvos, 0,544 km alvo (com câmera 360°, igual a `km_exigido`), todos atendidos, 0,754 km percorridos, razão de deslocamento 1,39.

---

## 9. Interface do motor (Python)

O TCC 1 chama o motor como uma biblioteca Python. A interface está em `motor_interface.py`, na forma de um `Protocol`: uma lista de métodos que qualquer implementação precisa oferecer, sem dizer como.

```python
class Motor(Protocol):
    nome: str
    versao: str

    def analisar_cobertura(self, area, parametros, *, progresso=None, cancelado=None) -> dict: ...
    def planejar(self, cobertura, *, ajustes=None, parametros=None, progresso=None, cancelado=None) -> dict: ...
```

- `area`: geometria GeoJSON (`Polygon` ou `MultiPolygon`).
- `parametros` (em `analisar_cobertura`): dicionário no formato de `plano.parametros`.
- `cobertura`: o plano em estado `cobertura` devolvido por `analisar_cobertura()`, guardado pela API.
- `ajustes`: `{"s5": "excluido", "s6": "incluido"}`.
- `parametros` (em `planejar`, opcional): substitui só os parâmetros de rota (6.3); tentar mudar um parâmetro de cobertura levanta `ParametrosInvalidos`.
- `progresso(fracao, mensagem)`: o motor chama para informar o andamento; a API repassa à tela ("Consultando o Panoramax... 40%").
- `cancelado()`: o motor consulta periodicamente; se `True`, para e levanta `PlanejamentoCancelado`.
- Retorno: um plano que passa no validador.

**Por que `planejar()` parte do plano de cobertura.** Se recebesse a área de novo, o motor teria de consultar a cobertura outra vez, e ela pode ter mudado no intervalo: os ajustes do usuário passariam a valer sobre outro estado, e o mesmo pedido daria planos diferentes. Partindo do plano de cobertura, o motor continua sem estado (D7), os ajustes se referem exatamente aos segmentos que o usuário viu e o plano é reprodutível.

**O que `planejar()` DEVE preservar.** Os segmentos na área do plano de cobertura, com os mesmos ids, geometrias, estados e frações. Mudam só `ajuste` e `exigencia`, e podem entrar segmentos fora da área para deslocamento (`na_area = false`). O formato recomendado de id (`w{osm_way_id}_{k}`, seção 6.8) torna os ids estáveis também entre duas análises de cobertura da mesma área.

**O que o motor DEVE produzir para passar no validador.** Resumo das exigências espalhadas pelas regras:

- linha de cada sessão como concatenação das geometrias dos segmentos percorridos, com os mesmos vértices (R5, R15);
- cada passagem cobrindo o segmento inteiro, de uma ponta à outra, no sentido declarado (R7);
- partida e chegada ajustadas a um vértice da rede, registradas como features, e sessões começando e terminando conforme `sessoes_partem_da_base` (R14);
- duração de cada sessão pelo menos igual ao tempo de movimento pelas duas velocidades (R8), e dentro de `limite_sessao` (R12);
- segmentos classificados pela regra provisória de cobertura parcial (R13).

`conferir_entradas_de_planejar()`, em `motor_interface.py`, faz as conferências de entrada; o motor real DEVERIA reutilizá-la.

**Erros previstos** e como a API do TCC 1 DEVERIA traduzi-los:

| Exceção | Situação | HTTP sugerido |
|---|---|---|
| `AreaInvalida` | Geometria com defeito. | 422 |
| `AreaGrandeDemais` | Excede o limite (`limite_km2`), a definir pela capacidade do motor depois da primeira versão funcional. | 413 |
| `ParametrosInvalidos` | Combinação sem sentido; em `planejar()`, plano que não é de cobertura, ajuste a segmento inexistente ou fora da área, ou mudança de parâmetro de cobertura. | 422 |
| `ProvedorIndisponivel` | Mapillary ou Panoramax fora do ar. | 503 |
| `PlanejamentoCancelado` | Usuário cancelou. | — (tarefa encerrada) |

Qualquer outra exceção é um defeito do motor e DEVERIA virar HTTP 500 com registro em log.

**`MotorDeExemplo`.** Uma implementação falsa que confere as entradas como o motor real e devolve sempre o plano de exemplo, com id e data novos; não aplica ajustes nem parâmetros de rota. Com ela, o TCC 1 pode construir a API e as telas antes de o motor real existir. Quando o motor da IC ficar pronto, troca-se uma linha:

```python
# motor = MotorDeExemplo()
motor = MotorP13()  # implementação real da pesquisa
```

---

## 10. O mínimo que a API HTTP precisa garantir

A API pertence ao TCC 1 e será documentada por ele em OpenAPI. O contrato fixa apenas o que o modo campo (TCC 2) precisa para funcionar:

| Recurso | Comportamento exigido |
|---|---|
| `GET /api/v1/planos/{id}` | 200 com o plano, `Content-Type: application/geo+json`; 404 se não existe; 410 se expirou. |
| Link compartilhável | `https://{servidor}/p/{id}` abre o plano na aplicação. É o que o QR code contém. |
| Arquivo | O plano exportado DEVE ser o próprio JSON do contrato, com extensão `.geojson` e nome sugerido `plano-{8 primeiros caracteres do id}.geojson`. |

**Privacidade (LGPD).** O ponto de partida pode ser a casa do usuário. Por isso:

- `partida` e `chegada` são opcionais;
- a aplicação DEVERIA avisar antes de compartilhar um plano com ponto de partida;
- planos de usuários anônimos DEVERIAM ter `expira_em` definido (sugestão: 30 dias).

O plano não contém o trajeto realizado em campo. O trajeto, quando existir, é dado do modo campo e fica no aparelho do usuário.

---

## 11. Correspondência com GPX e KML (informativo)

Esta seção não é obrigatória; orienta os exportadores do TCC 1 para que os arquivos saiam iguais em qualquer versão.

| Plano | GPX 1.1 | KML |
|---|---|---|
| Sessão | um `<trk>` por sessão, `<name>` = "Sessão {ordem}" | um `<Placemark>` com `<LineString>` |
| Linha da sessão | `<trkseg>` com `<trkpt>` | coordenadas da `LineString` |
| Passagens | não representadas (opcional: `<extensions>`) | estilo diferente para captura e sem captura |
| Partida e chegada | `<wpt>` | `<Placemark>` com `<Point>` |
| Instruções | opcional: `<rte>` com `<rtept>` nos pontos de manobra | — |

Apps de navegação tratam GPX de formas diferentes: alguns seguem a trilha (`trk`), outros recalculam a rota entre pontos (`rte`) e podem escolher outro caminho, o que estraga o plano. A matriz de compatibilidade feita pelos voluntários deve definir quais variantes exportar.

---

## 12. Como validar um plano

**Linha de comando (Python):**

```bash
pip install "captura-contrato @ git+https://github.com/youthmappers-ufv/captura-contrato@v0.1.2"
validar-plano meu-plano.geojson
# ✓ meu-plano.geojson: plano válido
```

O mesmo validador roda com `python -m captura_contrato.validar_plano meu-plano.geojson`.

Quando há erro, cada linha indica a regra:

```
✗ meu-plano.geojson: 2 erro(s)
   [R5] sessão ses2, passagem 0: segmento de mão única percorrido no sentido inverso
   [R9] segmento obrigatório s3 (sentido_da_geometria) não foi atendido nem justificado
```

**Dentro de testes (Python):**

```python
from captura_contrato import validar, carregar_exemplo
assert validar(plano) == []
assert validar(carregar_exemplo()) == []
```

**No navegador ou em Node.js (TCC 1 e TCC 2):** o esquema pode ser usado com a biblioteca Ajv (com o pacote de formatos). Isso confere só a estrutura; as regras R1 a R15 ficam no validador Python, que roda na integração contínua.

**Na integração contínua (GitHub Actions):** cada repositório roda os testes a cada *pull request*. Exemplo mínimo:

```yaml
# .github/workflows/contrato.yml
name: contrato
on: [push, pull_request]
jobs:
  testes:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install pytest "captura-contrato @ git+https://github.com/youthmappers-ufv/captura-contrato@v0.1.2"
      - run: pytest -q
```

O que cada repositório testa:

| Repositório | Teste de contrato |
|---|---|
| Motor (IC) | Planos gerados para instâncias pequenas passam no validador. A instância de referência é o bairro Jardim Primavera, em Rio Paranaíba (relação OSM `r16523453`, origem `relacao_osm`; 34 vias, 5 de mão única, no retrato de 2026-11-13): pequena para rodar a cada *pull request* e real o bastante para ter mão única e cruzamentos. |
| Aplicação (TCC 1) | O motor em uso (de exemplo ou real) produz planos válidos; os exportadores aceitam o exemplo. |
| Modo campo (TCC 2) | Abre o exemplo e todos os planos da pasta de exemplos sem erro. |

---

## 13. Versionamento e processo de mudança

### Versões (SemVer: MAIOR.MENOR.CORREÇÃO)

| Mudança | Exemplo | Versão |
|---|---|---|
| Quebra consumidores antigos | Renomear `passagens`; mudar o significado de `exigencia` | MAIOR (1.0 → 2.0) |
| Acrescenta algo opcional | Novo campo opcional `velocidade_max_kmh` | MENOR (0.1 → 0.2) |
| Só corrige texto ou exemplo | Ajuste nesta documentação | CORREÇÃO (0.1.0 → 0.1.1) |

**Antes da 1.0.0**, o contrato está em construção: mudanças MENOR podem quebrar compatibilidade, e isso é aceitável enquanto o motor e a aplicação ainda estão nascendo. A **1.0.0** deve ser declarada quando o TCC 1 publicar a primeira versão funcional; a partir daí, valem as regras da tabela.

**Leitor tolerante.** Consumidores (TCC 1 e TCC 2) DEVEM ignorar campos que não conhecem. Assim, um plano 0.2 com um campo novo continua abrindo numa aplicação feita para a 0.1. O esquema estrito serve para o **produtor**, nos testes; o consumidor não deve recusar um plano por causa de um campo extra.

### Processo para mudar o contrato

1. Abrir uma *issue* descrevendo o problema que a mudança resolve.
2. Escrever um ADR curto (registro de decisão de arquitetura, como o programa já prevê): contexto, decisão, alternativas, consequências.
3. Abrir um *pull request* que mude, **juntos**, o esquema, este documento, o exemplo, o validador (se houver regra nova), os testes e o histórico de versões.
4. Aprovação do orientador.
5. Publicar a nova versão (etiqueta Git `v0.2.0`) e atualizar a dependência nos outros repositórios.

Se o *pull request* mudar o esquema sem mudar a documentação, ele não deve ser aceito.

---

## 14. Decisões de projeto e alternativas descartadas

**D1. GeoJSON com membros adicionais, em vez de um JSON próprio.**
*Alternativa:* um objeto com `area`, `segmentos` e `sessoes` separados.
*Escolha:* GeoJSON abre direto no QGIS, no geojson.io e no MapLibre, o que torna a depuração visual imediata e facilita a vida de estudantes novos. O custo é que os metadados ficam num membro adicional (`plano`), permitido pela RFC 7946, e os tipos de feature precisam do campo `tipo`.

**D2. Um único arquivo para cobertura e plano completo.**
*Alternativa:* dois formatos.
*Escolha:* o campo `estado` distingue os dois momentos; a aplicação usa o mesmo código para desenhar segmentos nos dois casos.

**D3. Referência linear nas passagens.**
*Alternativa:* uma lista de segmentos na ordem e o consumidor reconstrói a rota.
*Escolha:* com metros ao longo da linha, o modo campo calcula o progresso projetando o GPS numa linha, sem grafo no celular. Também permite desenhar captura e sem captura com estilos diferentes.

**D4. Campo `exigencia` explícito, em vez de cada consumidor deduzir.**
*Escolha:* a regra de decisão (6.8) fica num único lugar, o motor, e é conferida pelo validador (R6). Se cada aplicação deduzisse, cedo ou tarde duas deduções divergiriam.

**D5. Geometria orientada no sentido permitido.**
*Escolha:* "direto" sempre significa "sentido em que se pode trafegar" nas vias de mão única, eliminando o caso `oneway=-1` nos consumidores.

**D6. Esquema estrito, leitor tolerante.**
*Escolha:* estrito para pegar erros no produtor; tolerante no consumidor para permitir evolução.

**D7. API como dono do armazenamento; motor sem estado.**
*Escolha:* o motor recebe área e parâmetros (ou o plano de cobertura, em `planejar()`) e devolve o plano; guardar, expirar e compartilhar é papel da API (TCC 1). Isso mantém o motor simples e testável pela pesquisa.

**D8. Toda via percorrida é um segmento do plano.**
*Alternativa:* deixar a sessão passar por vias que não constam do plano.
*Escolha:* a sessão só percorre segmentos (R15); vias fora da área entram com `na_area = false`. O arquivo cresce um pouco, mas contramão, comprimentos e trechos percorridos ficam todos conferíveis.

**D9. Sessões na base ou encadeadas, de forma explícita.**
*Alternativa:* o booleano `retornar_a_partida`, que só dizia algo sobre a última sessão.
*Escolha:* `sessoes_partem_da_base` diz onde começa e termina cada sessão, e a R14 confere; o deslocamento de acesso entra em `km_total`.

---

## 15. Questões em aberto

Questões a decidir antes da 1.0.0, provavelmente com a experiência dos primeiros meses:

- **Q1. Tamanho dos planos.** Uma cidade média pode ter dezenas de milhares de segmentos. Se os arquivos ficarem grandes demais para celular, avaliar: retirar do plano `completo` os segmentos `nenhuma` que nenhuma sessão percorre (os percorridos são exigidos pela R15), simplificar geometrias, ou compactar.
- **Q2. Divisão entre colaboradores.** Campanhas com várias pessoas exigirão atribuir sessões a pessoas. Fora do escopo da 0.1; provável campo novo em `sessao`.
- **Q3. `km_alvo` com câmera frontal.** *Resolvida em 2026-11-13:* `km_alvo` continua contando cada segmento uma vez, e o novo campo `km_exigido` conta duas vezes os segmentos `dois_sentidos`; a razão de deslocamento usa a captura exigida e atendida (seção 6.4).
- **Q4. Instruções de manobra.** Hoje opcionais. Se o modo campo precisar delas, virão do motor (com o Valhalla, previsto no P12) ou da própria aplicação.
- **Q5. Panoramax federado.** Várias instâncias podem ter imagens da mesma área; avaliar se `fontes.cobertura` precisa listar todas.
- **Q6. Deslocamento por vias fora do plano.** *Resolvida em 2026-11-13:* a sessão só percorre segmentos do plano (R15); vias fora da área entram como segmentos com `na_area = false` (D8).

---

## 16. Glossário

| Termo | Significado |
|---|---|
| **Contrato** | Acordo, escrito e verificável, sobre o formato e o comportamento entre partes de um sistema. |
| **Esquema JSON** | Arquivo que descreve a estrutura permitida de um JSON (campos, tipos, valores). |
| **GeoJSON** | Formato padrão (RFC 7946) para dados geográficos em JSON. |
| **Feature** | Uma feição geográfica: geometria + propriedades. |
| **Produtor / consumidor** | Quem gera / quem lê o arquivo. |
| **Segmento** | Trecho de via; unidade de cobertura. |
| **Sessão** | Caminho contínuo para uma saída de campo. |
| **Passagem** | Trecho de captura dentro de uma sessão. |
| **Deslocamento sem captura (em vazio)** | Parte do percurso usada só para chegar ao próximo trecho. |
| **Referência linear** | Localizar algo pela distância percorrida desde o início de uma linha. |
| **Aresta / arco** | Ligação sem sentido / com sentido num grafo; correspondem a vias de mão dupla e de mão única. |
| **Invariante** | Regra que precisa valer sempre (R1 a R15). |
| **SemVer** | Versionamento semântico: MAIOR.MENOR.CORREÇÃO. |
| **ADR** | Registro curto de uma decisão de arquitetura e de seus motivos. |
| **Teste de contrato** | Teste automático que confere se um lado ainda cumpre o contrato. |

---

### Histórico de versões

| Versão | Data | Mudança |
|---|---|---|
| 0.1.0 | 2026-10-14 | Primeira proposta. |
| 0.1.0 (validador) | 2026-11-12 | Validador mais rigoroso, sem mudança no esquema: R1, R2, R5, R7, R8, R9 e R10 ampliadas; R12 e R13 novas; `segmento_max_m` do exemplo corrigido para 120; linha de comando com mensagem para arquivo ausente ou malformado e saída sem símbolos quando o terminal não os aceita. |
| 0.1.0 (resumo) | 2026-11-13 | Razão de deslocamento redefinida como `km_total ÷ km_exigido_atendido`; campos `km_exigido` e `km_exigido_atendido` no resumo; fração atendida e deslocamento de acesso documentados; Q3 resolvida. Mantida a versão 0.1.0 porque nenhuma implementação dependia ainda do contrato. |
| 0.1.0 (motor) | 2026-11-13 | Preparação para o motor: `planejar()` parte do plano de cobertura; `sessoes_partem_da_base` no lugar de `retornar_a_partida`; `velocidade_deslocamento_kmh`; segmentos com `na_area`, `fracao_com_imagem` e `fracao_atual`; regra provisória de cobertura parcial; divisão das vias em segmentos e formato de id; regras R14 e R15; R6, R8, R10 e R13 ampliadas; Q6 resolvida; instância de teste no Jardim Primavera. Mantida a versão 0.1.0. |
| 0.1.1 | 2026-11-13 | Contrato empacotado como `captura_contrato` (pacote Python instalável, com o esquema e o exemplo como recursos do pacote e o comando `validar-plano`); separação entre versão do formato e versão do pacote. O formato não mudou: continua 0.1.0. |
| 0.1.2 | 2026-11-13 | Pacote com anotações de tipo completas e o marcador `py.typed`, conferido pelo mypy em modo estrito; `Ajuste`, `Progresso` e `Cancelado` exportados pelo pacote. O formato não mudou: continua 0.1.0. |
