"""Coleta os BUs do exterior e grava o JSON que alimenta o dashboard.

Uso:  python3 coletor/coleta.py [caminho/config.json]
Saída: docs/dados/resumo.json  e  docs/dados/historico.jsonl
"""
import datetime
import json
import os
import sys

import bu

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "dados")


def zeros(nums):
    return {str(n): 0 for n in nums}


def agrega(pleito, uf, municipio, secoes, nums, cache):
    """Soma os BUs disponíveis das seções pedidas."""
    tot = zeros(nums)
    tot.update(brancos=0, nulos=0, outros=0, comparecimento=0, aptos=0)
    por_secao = {}
    for zona, secao in secoes:
        bs = bu.baixa_bu(pleito, uf, municipio, zona, secao, cache=cache)
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
    return tot, por_secao


def metricas(t1, t2, nums):
    """Crescimento individual, diferença de crescimento e totais."""
    def cresc(nr):
        a, b = t1[str(nr)], t2[str(nr)]
        return {"t1": a, "t2": b, "delta": b - a,
                "pct": (100.0 * (b - a) / a) if a else None,
                "share_t1": (100.0 * a / t1["total"]) if t1["total"] else None,
                "share_t2": (100.0 * b / t2["total"]) if t2["total"] else None}

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
        "brancos_nulos_t1": t1["brancos"] + t1["nulos"],
        "brancos_nulos_t2": t2["brancos"] + t2["nulos"],
    }


def coleta_cidade(cfg, municipio, nomes, cache):
    uf = cfg["uf"]
    p1, p2 = cfg["turno1"]["pleito"], cfg["turno2"]["pleito"]
    nums = sorted(cfg["candidatos"], key=int)

    prev2 = bu.secoes_previstas(p2, uf, municipio)
    t2, sec2 = agrega(p2, uf, municipio, [(z, s) for z, s, _ in prev2],
                      nums, cache)

    # comparação apples-to-apples: só as seções que já saíram no 2º turno
    comparaveis = [(z, s) for z, s, _ in prev2 if s in sec2]
    t1, sec1 = agrega(p1, uf, municipio, comparaveis, nums, cache)

    secoes = []
    for zona, secao in comparaveis:
        secoes.append({"zona": zona, "secao": secao,
                       "t1": sec1.get(secao), "t2": sec2.get(secao)})

    return {
        "codigo": municipio,
        "nome": nomes.get(municipio, municipio),
        "secoes_previstas": len(prev2),
        "secoes_apuradas_t2": len(sec2),
        "secoes_comparaveis": len([s for s in secoes if s["t1"] and s["t2"]]),
        "t1": t1, "t2": t2,
        "metricas": metricas(t1, t2, nums) if t2["total"] else None,
        "secoes": secoes,
    }


def nomes_cidades(pleito, uf):
    cfg = bu._get(f"{bu.BASE}/{pleito}/config/{uf}/{uf}-p{pleito:0>6}-cs.json")
    out = {}
    for abr in cfg["abr"]:
        if abr["cd"] == uf:
            for mu in abr["mu"]:
                out[mu["cd"]] = mu["nm"]
    return out


def main(caminho=None):
    caminho = caminho or os.path.join(RAIZ, "config.json")
    cfg = json.load(open(caminho, encoding="utf-8"))
    uf = cfg["uf"]
    nums = sorted(cfg["candidatos"], key=int)
    cache = os.path.join(RAIZ, ".cache")
    nomes = nomes_cidades(cfg["turno2"]["pleito"], uf)

    cidades = []
    for cd in cfg["cidades"]:
        print(f"coletando {nomes.get(cd, cd)} ({cd})...", flush=True)
        try:
            cidades.append(coleta_cidade(cfg, cd, nomes, cache))
        except Exception as e:                      # uma cidade não derruba o resto
            print(f"  erro em {cd}: {e}", file=sys.stderr)

    # agregado de todas as cidades coletadas
    ag1 = zeros(nums); ag1.update(brancos=0, nulos=0, outros=0,
                                  comparecimento=0, aptos=0, total=0)
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

    # histórico enxuto, uma linha por execução
    linha = {"gerado_em": saida["gerado_em"],
             "secoes": saida["agregado"]["secoes_apuradas_t2"]}
    if saida["agregado"]["metricas"]:
        m = saida["agregado"]["metricas"]
        linha.update(total_t2=m["total_t2"], margem_t2=m["margem_t2"],
                     **{f"c{k}": v["t2"] for k, v in m["candidatos"].items()})
    with open(os.path.join(SAIDA, "historico.jsonl"), "a",
              encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")

    a = saida["agregado"]
    print(f"\nok: {len(cidades)} cidade(s), "
          f"{a['secoes_apuradas_t2']}/{a['secoes_previstas']} seções no 2º turno")
    if a["metricas"]:
        print(f"   total 2T {a['metricas']['total_t2']} votos · "
              f"margem {a['metricas']['margem_t2']:+}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
