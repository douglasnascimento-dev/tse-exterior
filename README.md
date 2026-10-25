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
- **comparação com o 2º turno de 2022** (Lula × Jair Bolsonaro), restrita às
  mesmas cidades dos dois lados, mais o total fechado do exterior inteiro
  daquele ano como referência de patamar;
- **detalhamento por seção** ao abrir uma cidade.

Clicar num país abre uma página só daquele recorte, com URL própria
(`.../#mapa:Japan`) que pode ser compartilhada ou recarregada. Nesse recorte a
tabela lista só as cidades daquele país e o gráfico de evolução some — o
histórico acumulado é do exterior inteiro e descreveria outro conjunto de
dados ali.

A tabela é ordenável por qualquer coluna e traz a bandeira de cada país. A
margem vem com sinal — positiva quando o primeiro candidato está à frente — para
que ordenar por ela separe os dois lados em vez de misturá-los.

O gráfico "Quem acelerou mais, e onde" compara as **taxas** de crescimento de
cada um, em pontos percentuais. Quem parte de uma base menor cresce mais fácil
em proporção, então lugares com menos de 50 votos para algum dos dois no 1º
turno ficam de fora: sem esse corte, Jacarta apareceria com +66 p.p. vindo de 8
votos contra 19. As
bandeiras são emoji: no Windows o Chrome não as desenha e mostra as duas
letras do país, que continua legível.

## Duas páginas

| Página | O quê | Fonte |
|---|---|---|
| `docs/index.html` | votação no exterior, cidade a cidade | boletins de urna, lidos um a um |
| `docs/brasil.html` | apuração no Brasil, minuto a minuto | totalização agregada do TSE |

O Brasil tem ~499 mil seções: ler boletim por boletim seria mais de um milhão
de requisições. Lá a fonte é o feed de totalização que o TSE publica por UF e
para o país, que já vem somado.

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

### Quantas urnas, não quantas seções

O config de arquivo de urna lista **seções eleitorais**, mas várias delas votam
na mesma urna e não geram boletim próprio: no 1º turno eram 2.715 seções
listadas para 1.310 boletins. O denominador do progresso vem do campo `s.ts`
do arquivo unificado do TSE (`zz<municipio>-c0001-e<eleicao>-u.json`), que é o
número de urnas e já vem preenchido antes da apuração começar.

Usar o número de seções subestimava o progresso pela metade — Wellington
aparecia como 5 de 9 quando já estava completa, com 5 de 5 urnas.

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

Terminada a apuração, desligue os crons para não gastar minutos de Actions.

### O acompanhamento minuto a minuto

O cron do GitHub Actions não desce de 5 minutos e costuma atrasar, então
`Acompanhar apuração no Brasil` não depende dele: é **um único job** que fica
rodando até 5h40 e lê o feed de minuto em minuto por dentro, publicando a cada
5 leituras. Dispare pelo botão *Run workflow* ou deixe o cron de domingo 17h
(BRT) iniciar sozinho.

Os dois workflows escrevem no mesmo repositório. Para o push concorrente não
virar conflito, `.gitattributes` marca os `.jsonl` como `merge=union` (são
append-only) e `coletor/publicar.sh` resolve `brasil.json` ficando com a
leitura mais recente.

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
- "Ritmo ao longo do dia" só começa nas 50 urnas apuradas: com meia dúzia, a
  taxa de crescimento oscila 80 pontos e achata o resto do gráfico.
- Os horários do TSE vêm em **horário de Brasília**. Dizer isso ao parser é
  obrigatório: num runner em UTC, uma hora naive de Brasília vira UTC e a série
  inteira sai 3h deslocada — foi o que aconteceu na primeira reconstrução, e o
  gráfico mostrava a virada às 11h quando ela foi às 14h11.
- `historico.jsonl` é normalizado (ordenado e sem repetições) a cada escrita, e
  o painel também deduplica na leitura: o `merge=union` do git resolve o push
  concorrente sem conflito, mas pode deixar as linhas fora de ordem.
- O trecho inicial da série é **reconstruído** por `reconstruir_historico.py`,
  que remonta o estado da apuração a partir da hora em que o TSE recebeu cada
  boletim (campo `hr` do `aux.json`, horário de Brasília — a hora gravada
  dentro do boletim é a local da urna e não serve para uma linha do tempo
  global). Essas linhas vêm marcadas com `origem: "reconstruido"`.
- A comparação com 2022 usa só as cidades que já apuraram em 2026 **e**
  existiam em 2022, nos dois lados — somar 2022 inteiro contra um 2026 parcial
  compararia conjuntos diferentes. Ainda assim 2022 é resultado fechado e 2026
  é parcial, e o candidato do PL mudou: é tendência, não equivalência.

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
| `coletor/codigos_iso.py` | atribui o código ISO de cada país, para a bandeira |
| `coletor/reconstruir_historico.py` | refaz a série do dia a partir dos boletins |
| `coletor/base_2022.py` | extrai o 2º turno de 2022 no exterior (roda uma vez) |
| `coletor/brasil.py` | lê a totalização agregada do Brasil, por UF |
| `coletor/publicar.sh` | commita e empurra lidando com push concorrente |
| `docs/brasil.html` | painel do Brasil, minuto a minuto, com 2022 |
| `docs/estilo.css` | estilos comuns às duas páginas |
| `coletor/coordenadas_manuais.json` | correções de geocoding |
| `docs/index.html` | dashboard (HTML/SVG, sem dependências) |
| `docs/dados/resumo.json` | saída da coleta, lida pelo dashboard |
| `docs/dados/coordenadas.json` | lat/lon das 186 cidades |
| `docs/dados/mundo.json` | contornos dos países para o mapa |
| `docs/dados/turno2_2022.json` | 2º turno de 2022 por cidade do exterior |
| `docs/dados/brasil_2022.json` | 2º turno de 2022 no Brasil e por UF |
| `docs/dados/historico.jsonl` | uma linha por execução — alimenta o gráfico de evolução |

Dados: [resultados.tse.jus.br](https://resultados.tse.jus.br) e
[dadosabertos.tse.jus.br](https://dadosabertos.tse.jus.br).
