"""Reconstrói o histórico do exterior a partir dos boletins já publicados.

O painel só começou a registrar leituras no meio do dia, e as primeiras não
guardavam os votos do 1º turno — sem eles não dá para calcular a taxa de
crescimento. Aqui a série é refeita do zero: cada boletim tem, no seu
aux.json, a hora em que o TSE o recebeu (horário de Brasília), então dá para
remontar o estado da apuração em qualquer instante do dia.

Uso: PYTHONPATH=coletor python3 coletor/reconstruir_historico.py
"""
import datetime
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import bu

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# o TSE carimba em horário de Brasília; sem dizer isso, um container em UTC
# trataria 11:41 de Brasília como 11:41 UTC e a série sairia 3h deslocada
BRASILIA = ZoneInfo("America/Sao_Paulo")
SAIDA = os.path.join(RAIZ, "docs", "dados", "historico.jsonl")
PASSO = 10          # minutos entre pontos da série


def hora_de_recebimento(args):
    """Quando o TSE recebeu o boletim desta seção, em horário de Brasília."""
    pleito, uf, mun, zona, secao = args
    d = f"{bu.BASE}/{pleito}/dados/{uf}/{mun}/{zona}/{secao}"
    try:
        aux = bu._get(f"{d}/p{pleito:0>6}-{uf}-m{mun}-z{zona}-s{secao}-aux.json")
    except Exception:
        return None
    h = aux["hashes"][0]
    try:
        q = datetime.datetime.strptime(f"{h['dr']} {h['hr']}",
                                       "%d/%m/%Y %H:%M:%S")
        return q.replace(tzinfo=BRASILIA)
    except Exception:
        return None


def main():
    cfg = json.load(open(os.path.join(RAIZ, "config.json"), encoding="utf-8"))
    uf, nums = cfg["uf"], sorted(cfg["candidatos"], key=int)
    p1, p2 = cfg["turno1"]["pleito"], cfg["turno2"]["pleito"]
    cache = os.path.join(RAIZ, ".cache")

    resumo = json.load(open(os.path.join(RAIZ, "docs", "dados", "resumo.json"),
                            encoding="utf-8"))

    # seções que já têm boletim no 2º turno, pelo resumo mais recente
    alvos = []
    for c in resumo["cidades"]:
        for s in c.get("secoes", []):
            if s.get("t2"):
                alvos.append((c["codigo"], s["zona"], s["secao"]))
    print(f"{len(alvos)} seções com boletim; buscando horários...", flush=True)

    with ThreadPoolExecutor(max_workers=12) as pool:
        horas = list(pool.map(hora_de_recebimento,
                              [(p2, uf, m, z, s) for m, z, s in alvos]))

    eventos = []
    for (mun, zona, secao), quando in zip(alvos, horas):
        if quando is None:
            continue
        b2 = bu.baixa_bu(p2, uf, mun, zona, secao, cache=cache)
        b1 = bu.baixa_bu(p1, uf, mun, zona, secao, cache=cache)
        if not b2 or not b1:
            continue
        eventos.append((quando, bu.le_bu(b1), bu.le_bu(b2)))
    eventos.sort(key=lambda e: e[0])
    print(f"{len(eventos)} seções com boletim nos dois turnos", flush=True)
    if not eventos:
        return 1

    def zerado():
        d = {n: 0 for n in nums}
        d.update(brancos=0, nulos=0, total=0)
        return d

    def soma(acc, r):
        for n in nums:
            acc[n] += r["votos"].get(int(n), 0)
        acc["brancos"] += r["brancos"]
        acc["nulos"] += r["nulos"]
        acc["total"] += r["comparecimento"]

    inicio, fim = eventos[0][0], eventos[-1][0]
    t = inicio
    acc1, acc2, i, linhas = zerado(), zerado(), 0, []
    while t <= fim + datetime.timedelta(minutes=PASSO):
        while i < len(eventos) and eventos[i][0] <= t:
            soma(acc1, eventos[i][1])
            soma(acc2, eventos[i][2])
            i += 1
        if i:
            v1 = acc1["total"] - acc1["brancos"] - acc1["nulos"]
            v2 = acc2["total"] - acc2["brancos"] - acc2["nulos"]
            linha = {"gerado_em": t.astimezone(datetime.timezone.utc)
                     .isoformat(timespec="seconds"),
                     "origem": "reconstruido", "secoes": i,
                     "secoes_previstas": resumo["agregado"]["secoes_previstas"],
                     "validos_t1": v1, "validos_t2": v2,
                     "total_t1": acc1["total"], "total_t2": acc2["total"]}
            for n in nums:
                linha[f"v{n}_t1"] = acc1[n]
                linha[f"v{n}_t2"] = acc2[n]
                linha[f"p{n}_t1"] = round(100 * acc1[n] / v1, 3) if v1 else None
                linha[f"p{n}_t2"] = round(100 * acc2[n] / v2, 3) if v2 else None
                linha[f"g{n}"] = (round(100 * (acc2[n] - acc1[n]) / acc1[n], 3)
                                  if acc1[n] else None)
            linhas.append(linha)
        t += datetime.timedelta(minutes=PASSO)

    # preserva as leituras ao vivo que vieram DEPOIS do último ponto
    # reconstruído; as anteriores são substituídas pela reconstrução, que é
    # mais densa e tem todos os campos
    corte = linhas[-1]["gerado_em"]
    vivas = []
    if os.path.exists(SAIDA):
        for l in open(SAIDA, encoding="utf-8"):
            if not l.strip():
                continue
            r = json.loads(l)
            if r.get("origem") != "reconstruido" and r["gerado_em"] > corte:
                vivas.append(r)
    todas = linhas + sorted(vivas, key=lambda r: r["gerado_em"])
    with open(SAIDA, "w", encoding="utf-8") as f:
        for r in todas:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  + {len(vivas)} leituras ao vivo posteriores mantidas")
    u = linhas[-1]
    print(f"{len(linhas)} pontos, de {linhas[0]['gerado_em'][11:16]} a "
          f"{u['gerado_em'][11:16]} UTC")
    print(f"  último: {u['secoes']} seções · "
          + " · ".join(f"{cfg['candidatos'][n]} {u[f'g{n}']:+.2f}%" for n in nums))
    return 0


if __name__ == "__main__":
    sys.exit(main())
