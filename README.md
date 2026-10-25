# Apuração no exterior — 1º × 2º turno de 2026

Dashboard que compara, **nas mesmas seções**, o 1º e o 2º turno da eleição
presidencial de 2026 nas zonas eleitorais do exterior, lendo os **boletins de
urna** publicados pelo TSE.

Cobre as **186 cidades** do exterior, em 134 países. Traz:

- **mapa-múndi** com cada país pintado na cor de quem lidera ali (países
  pequenos demais para o mapa 110m aparecem como ponto);
- **evolução da apuração** — a porcentagem de cada candidato ao longo do dia,
  com o 1º turno nas mesmas seções como linha tracejada de referência;
- **recorte por cidade, por país ou pelo exterior inteiro**;
- para cada recorte: votos nos dois turnos, crescimento individual (absoluto e
  percentual), diferença entre os crescimentos, margem e sua variação, total de
  votos e seu crescimento;
- **detalhamento por seção** ao abrir uma cidade.

## Como funciona

O site do TSE **não libera CORS**: uma requisição de navegador com header
`Origin` recebe `403`. Por isso o dashboard não busca os dados direto — quem
coleta é o GitHub Actions:

```
GitHub Actions (cron)  ->  coletor/coleta.py  ->  docs/dados/resumo.json
                                                        |
                                            docs/index.html (GitHub Pages)
```

O coletor:

1. lê `<uf>-p<pleito>-cs.json` para saber as seções previstas de cada cidade;
2. baixa o `-aux.json` de cada seção e, dele, o boletim de urna assinado;
3. decodifica o BU (ASN.1 DER) e extrai votos, brancos, nulos, comparecimento
   e eleitores aptos;
4. compara **somente as seções que já saíram no 2º turno** com as mesmas seções
   no 1º turno, para a comparação ser 1:1.

### Validação do leitor de BU

O parser foi conferido contra o CSV oficial do Portal de Dados Abertos
(`votacao_secao_2026_BR.zip`) nas 5 seções apuradas de Wellington no 1º turno:
votos por candidato, brancos, nulos e comparecimento batem exatamente, e a soma
fecha com o comparecimento registrado no próprio BU.

## Rodando localmente

Só precisa de Python 3.9+ (biblioteca padrão, sem dependências):

```bash
PYTHONPATH=coletor python3 coletor/coleta.py
python3 -m http.server -d docs 8000   # abra http://localhost:8000
```

## Escolhendo as cidades

Por padrão coleta todas. Para restringir, edite `config.json`:

```json
{ "uf": "zz", "cidades": ["30805", "30627"] }
```

Para ver os códigos das 186 cidades do exterior:

```bash
PYTHONPATH=coletor python3 coletor/listar_cidades.py
```

Algumas: `30805` Wellington · `30627` Lisboa · `30295` Miami ·
`30279` Londres · `29971` Tóquio.

> O exterior inteiro são ~2.700 seções por turno. A coleta usa 8 downloads
> simultâneos (`TSE_PARALELO` ajusta) e o cache do Actions evita rebaixar o que
> já veio; uma execução completa leva ~4 min.

### Porcentagens

São calculadas sobre **votos válidos** (total menos brancos e nulos), que é a
base da apuração oficial. No 2º turno os dois somam 100%; no 1º turno não, já
que havia 14 candidatos e os votos dos demais também são válidos.

### O mapa

Cada cidade é ligada ao polígono do país **por geometria** (ponto dentro do
polígono), não por nome — os nomes vêm do Nominatim em português e o mapa usa
inglês. Sete cidades litorâneas são resolvidas pelo contorno mais próximo
(até 0,6°) e nove casos têm correção manual em `coletor/mapear_paises.py`:
o mapa 110m não traz Singapura, Barein, Barbados, Cabo Verde, São Tomé,
Antígua nem Santa Lúcia, e sem correção o vizinho seria pintado no lugar.
Essas aparecem como ponto.

As coordenadas das 186 cidades estão em `docs/dados/coordenadas.json`,
geocodificadas uma única vez via Nominatim/OSM e **versionadas** — a coleta
periódica não refaz geocoding. 26 cidades precisaram de consulta explícita por
país (Artigas caía na França, Madri na Índia, Chuy no Quirguistão); essas ficam
em `coletor/coordenadas_manuais.json`, que tem precedência. Os contornos dos
países (`docs/dados/mundo.json`, Natural Earth 110m) também são versionados,
então o dashboard não depende de CDN.

Postos muito próximos (Nagóia, Hamamatsu e Tóquio ficam a poucos pixels) são
afastados por repulsão, com uma linha fina ligando cada bolha ao ponto real.

## Publicando

1. Suba o repositório no GitHub.
2. **Settings → Pages → Source: Deploy from a branch**, branch `main`, pasta
   `/docs`.
3. **Settings → Actions → General → Workflow permissions: Read and write**
   (o workflow commita os dados).
4. O cron roda a cada 15 min; `workflow_dispatch` permite rodar na hora.

Terminada a apuração, desligue o cron para não gastar minutos de Actions.

## Ressalvas

- Boletins com status `Recebida` são os números da própria urna: definitivos
  para aquela seção, mas anteriores à totalização oficial do TSE.
- Seções sem boletim publicado ficam de fora dos dois lados da comparação.
- `coletor/bu.py` distingue `404` (seção ainda não apurada) de erro transitório,
  que é repetido com backoff — uma falha de rede não vira "seção sem votos".
- Uma cidade que falhe mesmo após a segunda tentativa **permanece** no resultado,
  marcada com `falhou`, e o dashboard mostra um aviso. Removê-la encolheria o
  total de seções previstas sem ninguém notar.
- O gráfico de evolução depende do histórico acumulado: com uma única leitura
  ele não aparece. A cadência é a do cron (15 min), não minuto a minuto.

## Arquivos

| Arquivo | O quê |
|---|---|
| `coletor/der.py` | parser ASN.1 DER genérico |
| `coletor/bu.py` | download e leitura dos boletins de urna |
| `coletor/coleta.py` | agrega, calcula as métricas e grava o JSON |
| `coletor/listar_cidades.py` | lista as cidades do exterior |
| `coletor/geocodificar.py` | geocodifica as cidades (roda uma vez) |
| `coletor/mapa_base.py` | gera os contornos dos países (roda uma vez) |
| `coletor/mapear_paises.py` | liga cada cidade ao polígono do seu país |
| `coletor/coordenadas_manuais.json` | correções de geocoding |
| `docs/index.html` | dashboard (HTML/SVG, sem dependências) |
| `docs/dados/resumo.json` | saída da coleta, lida pelo dashboard |
| `docs/dados/coordenadas.json` | lat/lon das 186 cidades |
| `docs/dados/mundo.json` | contornos dos países para o mapa |
| `docs/dados/historico.jsonl` | uma linha por execução — alimenta o gráfico de evolução |

Dados: [resultados.tse.jus.br](https://resultados.tse.jus.br) e
[dadosabertos.tse.jus.br](https://dadosabertos.tse.jus.br).
