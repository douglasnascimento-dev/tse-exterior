"""Coleta os BUs do exterior e grava o JSON que alimenta o dashboard.

Uso:  python3 coletor/coleta.py [caminho/config.json]
Saída: docs/dados/resumo.json  e  docs/dados/historico.jsonl
"""
import datetime
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import bu

# Downloads simultâneos. Modesto de propósito: o volume todo são ~2.700 seções
# por turno e o cache evita rebaixar o que já veio.
PARALELO = int(os.environ.get("TSE_PARALELO", "8"))

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URNAS = {}          # município -> boletins esperados, preenchido em main()
SAIDA = os.path.join(RAIZ, "docs", "dados")


def zeros(nums):
    return {str(n): 0 for n in nums}


def agrega(pleito, uf, municipio, secoes, nums, cache, pool=None):
    """Soma os BUs disponíveis das seções pedidas."""
    tot = zeros(nums)
    tot.update(brancos=0, nulos=0, outros=0, comparecimento=0, aptos=0)
    por_secao = {}

    def pega(arg):
        zona, secao = arg
        return secao, bu.baixa_bu(pleito, uf, municipio, zona, secao, cache=cache)

    mapa = pool.map(pega, secoes) if pool else map(pega, secoes)
    for secao, bs in mapa:
        if bs is None:
            continue
        r = bu.le_bu(bs)
        linha = zeros(nums)
        for nr, v in r["votos"].items():
            if str(nr) in linha:
                linha[str(nr)] = v
            else:
                tot["outros"] += v
        linha.update(brancos=r["brancos"], nulos=r["nulos"],
                     comparecimento=r["comparecimento"], aptos=r["aptos"])
        por_secao[secao] = linha
        for k in linha:
            tot[k] = tot.get(k, 0) + linha[k]
    tot["total"] = sum(tot[str(n)] for n in nums) + tot["brancos"] + \
        tot["nulos"] + tot["outros"]
    # válidos = total menos brancos e nulos; votos em outros candidatos contam
    tot["validos"] = tot["total"] - tot["brancos"] - tot["nulos"]
    return tot, por_secao


def metricas(t1, t2, nums):
    """Crescimento individual, diferença de crescimento e totais.

    As porcentagens são sobre os votos válidos (total menos brancos e nulos),
    que é a base usada na apuração oficial.
    """
    def cresc(nr):
        a, b = t1[str(nr)], t2[str(nr)]
        return {"t1": a, "t2": b, "delta": b - a,
                "pct": (100.0 * (b - a) / a) if a else None,
                "share_t1": (100.0 * a / t1["validos"]) if t1["validos"] else None,
                "share_t2": (100.0 * b / t2["validos"]) if t2["validos"] else None}

    c = {str(n): cresc(n) for n in nums}
    a, b = nums[0], nums[1]
    marg1 = t1[str(a)] - t1[str(b)]
    marg2 = t2[str(a)] - t2[str(b)]
    return {
        "candidatos": c,
        "diferenca_crescimento": c[str(a)]["delta"] - c[str(b)]["delta"],
        "margem_t1": marg1,
        "margem_t2": marg2,
        "variacao_margem": marg2 - marg1,
        "total_t1": t1["total"],
        "total_t2": t2["total"],
        "delta_total": t2["total"] - t1["total"],
        "pct_total": (100.0 * (t2["total"] - t1["total"]) / t1["total"])
        if t1["total"] else None,
        "validos_t1": t1["validos"],
        "validos_t2": t2["validos"],
        "delta_validos": t2["validos"] - t1["validos"],
        "aptos_t2": t2["aptos"],
        "comparecimento_t2": t2["comparecimento"],
        "brancos_nulos_t1": t1["brancos"] + t1["nulos"],
        "brancos_nulos_t2": t2["brancos"] + t2["nulos"],
    }


def coleta_cidade(cfg, municipio, nomes, cache, prev2, pool=None):
    uf = cfg["uf"]
    p1, p2 = cfg["turno1"]["pleito"], cfg["turno2"]["pleito"]
    nums = sorted(cfg["candidatos"], key=int)

    t2, sec2 = agrega(p2, uf, municipio, [(z, s) for z, s, _ in prev2],
                      nums, cache, pool)

    # comparação apples-to-apples: só as seções que já saíram no 2º turno
    comparaveis = [(z, s) for z, s, _ in prev2 if s in sec2]
    t1, sec1 = agrega(p1, uf, municipio, comparaveis, nums, cache, pool)

    secoes = []
    for zona, secao in comparaveis:
        secoes.append({"zona": zona, "secao": secao,
                       "t1": sec1.get(secao), "t2": sec2.get(secao)})

    return {
        "codigo": municipio,
        "nome": nomes.get(municipio, municipio),
        "secoes_previstas": URNAS.get(municipio, len(prev2)),
        "secoes_listadas": len(prev2),
        "secoes_apuradas_t2": len(sec2),
        "secoes_comparaveis": len([s for s in secoes if s["t1"] and s["t2"]]),
        "t1": t1, "t2": t2,
        "metricas": metricas(t1, t2, nums) if t2["total"] else None,
        "secoes": secoes,
    }


def urnas_previstas(ciclo, eleicao, uf, municipios, cargo=1, pool=None):
    """Quantos boletins cada cidade deve gerar, segundo o próprio TSE.

    O config de arquivo de urna lista seções eleitorais, mas várias delas são
    agregadas numa mesma urna e não geram boletim próprio: no 1º turno eram
    2.715 seções listadas para 1.310 boletins. O campo 's.ts' do arquivo
    unificado traz o número de urnas, e já vem preenchido antes da apuração.
    """
    base = "https://resultados.tse.jus.br/oficial"

    def pega(cd):
        url = (f"{base}/{ciclo}/{eleicao}/dados/{uf}/"
               f"{uf}{cd}-c{cargo:04d}-e{eleicao:06d}-u.json")
        try:
            d = bu._get(url)
            return cd, int(str(d.get("s", {}).get("ts", 0)).replace(".", "") or 0)
        except Exception:
            return cd, None

    it = pool.map(pega, municipios) if pool else map(pega, municipios)
    return {cd: n for cd, n in it if n}


def catalogo(pleito, uf):
    """Nome e seções previstas de cada cidade, num único download."""
    cfg = bu._get(f"{bu.BASE}/{pleito}/config/{uf}/{uf}-p{pleito:0>6}-cs.json")
    nomes, secoes = {}, {}
    for abr in cfg["abr"]:
        if abr["cd"] != uf:
            continue
        for mu in abr["mu"]:
            nomes[mu["cd"]] = mu["nm"]
            secoes[mu["cd"]] = [(z["cd"], s["ns"], "da" in s)
                                for z in mu["zon"] for s in z["sec"]]
    return nomes, secoes


def main(caminho=None):
    caminho = caminho or os.path.join(RAIZ, "config.json")
    cfg = json.load(open(caminho, encoding="utf-8"))
    uf = cfg["uf"]
    nums = sorted(cfg["candidatos"], key=int)
    cache = os.path.join(RAIZ, ".cache")
    nomes, secoes = catalogo(cfg["turno2"]["pleito"], uf)

    alvo = cfg["cidades"]
    if alvo == "todas":
        alvo = sorted(nomes, key=lambda c: nomes[c])

    coords = {}
    arq_coords = os.path.join(SAIDA, "coordenadas.json")
    if os.path.exists(arq_coords):
        coords = json.load(open(arq_coords, encoding="utf-8"))

    cidades, falhas = [], []
    with ThreadPoolExecutor(max_workers=PARALELO) as pool:
        global URNAS
        URNAS = urnas_previstas("ele2026", cfg["turno2"]["eleicao"], uf,
                                alvo, pool=pool)
        print(f"boletins esperados: {sum(URNAS.values())} "
              f"(em {len(URNAS)} cidades)", flush=True)
        for i, cd in enumerate(alvo, 1):
            print(f"[{i}/{len(alvo)}] {nomes.get(cd, cd)}", flush=True)
            c = None
            for tentativa in (1, 2):                # uma segunda chance antes de desistir
                try:
                    c = coleta_cidade(cfg, cd, nomes, cache, secoes.get(cd, []), pool)
                    break
                except Exception as e:
                    erro = f"{type(e).__name__}: {e}"
                    if tentativa == 2:
                        print(f"  FALHA em {nomes.get(cd, cd)}: {erro}",
                              file=sys.stderr)
                        falhas.append({"codigo": cd, "nome": nomes.get(cd, cd),
                                       "erro": erro})
            if c is None:
                # mantém a cidade no resultado: tirá-la encolheria o denominador
                # de seções sem ninguém perceber.
                c = {"codigo": cd, "nome": nomes.get(cd, cd),
                     "secoes_previstas": URNAS.get(cd, len(secoes.get(cd, []))),
                     "secoes_listadas": len(secoes.get(cd, [])),
                     "secoes_apuradas_t2": 0, "secoes_comparaveis": 0,
                     "t1": zeros(nums) | {"brancos": 0, "nulos": 0, "outros": 0,
                                          "comparecimento": 0, "aptos": 0,
                                          "total": 0, "validos": 0},
                     "t2": zeros(nums) | {"brancos": 0, "nulos": 0, "outros": 0,
                                          "comparecimento": 0, "aptos": 0,
                                          "total": 0, "validos": 0},
                     "metricas": None, "secoes": [], "falhou": True}
            p = coords.get(cd) or {}
            if p.get("lat") is not None:
                c["lat"], c["lon"] = p["lat"], p["lon"]
            c["pais"] = p.get("pais", "—")
            c["pais_mapa"] = p.get("pais_mapa")
            c["iso2"] = p.get("iso2")
            cidades.append(c)

    # agregado de todas as cidades coletadas
    ag1 = zeros(nums); ag1.update(brancos=0, nulos=0, outros=0,
                                  comparecimento=0, aptos=0, total=0, validos=0)
    ag2 = dict(ag1)
    for c in cidades:
        for k in ag1:
            ag1[k] += c["t1"].get(k, 0)
            ag2[k] += c["t2"].get(k, 0)

    saida = {
        "gerado_em": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds"),
        "fonte": "resultados.tse.jus.br — arquivo de urna (BU)",
        "uf": uf,
        "turno1": cfg["turno1"], "turno2": cfg["turno2"],
        "candidatos": cfg["candidatos"],
        "cidades": cidades,
        "falhas": falhas,
        "agregado": {
            "t1": ag1, "t2": ag2,
            "metricas": metricas(ag1, ag2, nums) if ag2["total"] else None,
            "secoes_apuradas_t2": sum(c["secoes_apuradas_t2"] for c in cidades),
            "secoes_previstas": sum(c["secoes_previstas"] for c in cidades),
        },
    }

    os.makedirs(SAIDA, exist_ok=True)
    with open(os.path.join(SAIDA, "resumo.json"), "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)

    # histórico: uma linha por execução, com o share de cada turno nas mesmas
    # seções — é o que o gráfico de evolução consome.
    linha = {"gerado_em": saida["gerado_em"],
             "secoes": saida["agregado"]["secoes_apuradas_t2"],
             "secoes_previstas": saida["agregado"]["secoes_previstas"],
             "falhas": len(falhas)}
    if saida["agregado"]["metricas"]:
        m = saida["agregado"]["metricas"]
        linha.update(total_t1=m["total_t1"], total_t2=m["total_t2"],
                     margem_t2=m["margem_t2"])
        linha["validos_t1"] = m["validos_t1"]
        linha["validos_t2"] = m["validos_t2"]
        for k, v in m["candidatos"].items():
            linha[f"v{k}_t1"] = v["t1"]
            linha[f"v{k}_t2"] = v["t2"]
            linha[f"p{k}_t2"] = round(v["share_t2"], 3) if v["share_t2"] is not None else None
            linha[f"p{k}_t1"] = round(v["share_t1"], 3) if v["share_t1"] is not None else None
            # taxa de crescimento: é o que o gráfico de ritmo consome
            linha[f"g{k}"] = round(v["pct"], 3) if v["pct"] is not None else None
    arq_hist = os.path.join(SAIDA, "historico.jsonl")
    anterior = None
    if os.path.exists(arq_hist):
        linhas = [l for l in open(arq_hist, encoding="utf-8") if l.strip()]
        if linhas:
            anterior = json.loads(linhas[-1])
    igual = anterior and all(anterior.get(k) == v
                             for k, v in linha.items() if k != "gerado_em")
    if not igual:
        linhas = linhas if os.path.exists(arq_hist) else []
        registros = [json.loads(l) for l in linhas if l.strip()] + [linha]
        # o merge=union do git pode reintroduzir linhas de outro push fora de
        # ordem; normalizar na escrita mantém o arquivo sempre consistente
        por_hora = {}
        for r in registros:
            antes = por_hora.get(r["gerado_em"])
            if antes is None or len(r) >= len(antes):
                por_hora[r["gerado_em"]] = r
        with open(arq_hist, "w", encoding="utf-8") as f:
            for r in sorted(por_hora.values(), key=lambda x: x["gerado_em"]):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    a = saida["agregado"]
    if falhas:
        print(f"\nATENÇÃO: {len(falhas)} cidade(s) não coletada(s): "
              + ", ".join(f["nome"] for f in falhas), file=sys.stderr)
    print(f"\nok: {len(cidades)} cidade(s), "
          f"{a['secoes_apuradas_t2']}/{a['secoes_previstas']} seções no 2º turno")
    if a["metricas"]:
        print(f"   total 2T {a['metricas']['total_t2']} votos · "
              f"margem {a['metricas']['margem_t2']:+}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
