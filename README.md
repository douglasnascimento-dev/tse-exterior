# Apuração no exterior — 1º × 2º turno de 2026

Dashboard que compara, **nas mesmas seções**, o 1º e o 2º turno da eleição
presidencial de 2026 nas zonas eleitorais do exterior, lendo os **boletins de
urna** publicados pelo TSE.

Para cada cidade mostra: votos de cada candidato nos dois turnos, crescimento
individual (absoluto e percentual), diferença entre os crescimentos, margem
entre os dois e sua variação, total de votos e seu crescimento — além do
detalhamento por seção.

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

Edite `config.json`:

```json
{ "uf": "zz", "cidades": ["30805"] }
```

Para ver os códigos das 186 cidades do exterior:

```bash
PYTHONPATH=coletor python3 coletor/listar_cidades.py
```

Algumas: `30805` Wellington · `30627` Lisboa · `30295` Miami ·
`30279` Londres · `29971` Tóquio.

> Monitorar o exterior inteiro são ~2.700 seções por turno. O cache do Actions
> evita rebaixar o que já veio, mas a primeira execução é demorada.

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

## Arquivos

| Arquivo | O quê |
|---|---|
| `coletor/der.py` | parser ASN.1 DER genérico |
| `coletor/bu.py` | download e leitura dos boletins de urna |
| `coletor/coleta.py` | agrega, calcula as métricas e grava o JSON |
| `coletor/listar_cidades.py` | lista as cidades do exterior |
| `docs/index.html` | dashboard (HTML/SVG, sem dependências) |
| `docs/dados/resumo.json` | saída da coleta, lida pelo dashboard |
| `docs/dados/historico.jsonl` | uma linha por execução, para série temporal |

Dados: [resultados.tse.jus.br](https://resultados.tse.jus.br) e
[dadosabertos.tse.jus.br](https://dadosabertos.tse.jus.br).
