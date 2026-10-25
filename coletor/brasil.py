"""Acompanha a totalização no Brasil, minuto a minuto.

No exterior dá para ler boletim por boletim (2.715 seções). No Brasil são
~499 mil seções — inviável. Aqui a fonte é o feed de totalização agregada que
o TSE publica durante a apuração, por UF e para o país inteiro.

Uso:  PYTHONPATH=coletor python3 coletor/brasil.py [--loop SEGUNDOS]
Saída: docs/dados/brasil.json e docs/dados/brasil_historico.jsonl
"""
import argparse
import datetime
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import bu

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "dados")
BASE = "https://resultados.tse.jus.br/oficial"

UFS = ["ac", "al", "am", "ap", "ba", "ce", "df", "es", "go", "ma", "mg", "ms",
       "mt", "pa", "pb", "pe", "pi", "pr", "rj", "rn", "ro", "rr", "rs", "sc",
       "se", "sp", "to", "zz"]


def num(s):
    """'1.234' ou '45,16' -> número. O TSE manda tudo como texto."""
    if s in (None, ""):
        return 0
    s = str(s).replace(".", "").replace(",", ".")
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return 0


def url_u(ciclo, eleicao, uf, cargo=1):
    return (f"{BASE}/{ciclo}/{eleicao}/dados/{uf}/"
            f"{uf}-c{cargo:04d}-e{eleicao:06d}-u.json")


def le_abrangencia(ciclo, eleicao, uf, nums):
    """Lê o arquivo unificado de uma UF (ou 'br') e extrai o essencial."""
    d = bu._get(url_u(ciclo, eleicao, uf))
    v, s, e = d.get("v", {}), d.get("s", {}), d.get("e", {})

    votos = {}
    for cargo in d.get("carg", []):
        for agr in cargo.get("agr", []):
            for par in agr.get("par", []):
                for c in par.get("cand", []):
                    n = str(c.get("n"))
                    if n in nums:
                        votos[n] = num(c.get("vap"))

    return {
        "uf": uf,
        "atualizado": f"{d.get('dt', '')} {d.get('ht', '')}".strip(),
        "finalizado": d.get("tf") == "s",
        "votos": votos,
        "validos": num(v.get("vv")),
        "brancos": num(v.get("vb")),
        "nulos": num(v.get("vn")),
        "total": num(v.get("tv")),
        "secoes_totais": num(s.get("ts")),
        "secoes_totalizadas": num(s.get("st")),
        "pct_secoes": num(s.get("pstn")),
        "eleitorado": num(e.get("te")),
        "eleitorado_totalizado": num(e.get("est")),
        "comparecimento": num(v.get("tv")),
    }


def coleta(cfg, ciclo="ele2026"):
    nums = [str(n) for n in sorted(cfg["candidatos"], key=int)]
    e2 = cfg["turno2"]["eleicao"]
    e1 = cfg["turno1"]["eleicao"]

    def pega(args):
        eleicao, uf = args
        try:
            return (eleicao, uf, le_abrangencia(ciclo, eleicao, uf, nums))
        except Exception as exc:
            print(f"  erro {uf} e{eleicao}: {exc}", file=sys.stderr)
            return (eleicao, uf, None)

    alvos = [(e2, "br")] + [(e2, u) for u in UFS] \
        + [(e1, "br")] + [(e1, u) for u in UFS]
    with ThreadPoolExecutor(max_workers=10) as pool:
        resultados = list(pool.map(pega, alvos))

    por = {}
    for eleicao, uf, r in resultados:
        if r:
            por[(eleicao, uf)] = r

    return {
        "gerado_em": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds"),
        "fonte": "resultados.tse.jus.br — totalização agregada",
        "candidatos": cfg["candidatos"],
        "turno2": {"eleicao": e2, "br": por.get((e2, "br")),
                   "ufs": [por[(e2, u)] for u in UFS if (e2, u) in por]},
        "turno1": {"eleicao": e1, "br": por.get((e1, "br")),
                   "ufs": [por[(e1, u)] for u in UFS if (e1, u) in por]},
    }


def grava(saida):
    os.makedirs(SAIDA, exist_ok=True)
    with open(os.path.join(SAIDA, "brasil.json"), "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)

    br = saida["turno2"]["br"]
    if not br:
        return None
    nums = sorted(saida["candidatos"], key=int)
    linha = {"gerado_em": saida["gerado_em"],
             "pct": round(br["pct_secoes"], 4),
             "secoes": br["secoes_totalizadas"],
             "validos": br["validos"]}
    for n in nums:
        vv = br["votos"].get(n, 0)
        linha[f"v{n}"] = vv
        linha[f"p{n}"] = round(100.0 * vv / br["validos"], 4) if br["validos"] else None

    arq = os.path.join(SAIDA, "brasil_historico.jsonl")
    anterior = None
    if os.path.exists(arq):
        linhas = [l for l in open(arq, encoding="utf-8") if l.strip()]
        if linhas:
            anterior = json.loads(linhas[-1])
    # só grava quando algum número mudou — evita inflar o arquivo parado
    if anterior and all(anterior.get(k) == v
                        for k, v in linha.items() if k != "gerado_em"):
        return linha
    with open(arq, "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return linha


def uma_vez(cfg):
    saida = coleta(cfg)
    linha = grava(saida)
    br = saida["turno2"]["br"]
    if br:
        nums = sorted(cfg["candidatos"], key=int)
        parte = "  ".join(
            f"{cfg['candidatos'][n]}: {linha[f'p{n}']:.2f}%" if linha.get(f"p{n}")
            is not None else f"{cfg['candidatos'][n]}: —" for n in nums)
        print(f"{br['pct_secoes']:6.2f}% apurado · "
              f"{br['secoes_totalizadas']:,}/{br['secoes_totais']:,} seções · "
              f"{parte}".replace(",", "."), flush=True)
    else:
        print("sem dados do Brasil ainda", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0,
                    help="segundos entre leituras; 0 = uma leitura só")
    ap.add_argument("--ate", type=int, default=0,
                    help="duração máxima do loop, em segundos")
    args = ap.parse_args()

    cfg = json.load(open(os.path.join(RAIZ, "config.json"), encoding="utf-8"))
    if not args.loop:
        uma_vez(cfg)
        return

    fim = time.time() + (args.ate or 3600)
    while time.time() < fim:
        inicio = time.time()
        try:
            uma_vez(cfg)
        except Exception as exc:                 # uma leitura ruim não para o loop
            print(f"leitura falhou: {exc}", file=sys.stderr, flush=True)
        espera = args.loop - (time.time() - inicio)
        if espera > 0:
            time.sleep(espera)


if __name__ == "__main__":
    main()
