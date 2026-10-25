"""Reconstrói a curva minuto a minuto do 1º turno de 2026 no Brasil.

O TSE só publica o "Histórico de Totalização" depois da eleição — para 2026
ainda não existe (404). Mas dá para remontar: o config de arquivo de urna traz
a hora em que cada seção foi recebida, e o CSV de dados abertos traz os votos
de cada seção. Juntando os dois e acumulando em ordem de chegada, sai a curva.

É a curva de *recebimento dos boletins*, não a da totalização oficial — as
duas andam juntas, mas não são a mesma coisa. O resultado final confere com o
oficial, o que valida o cruzamento.

Uso: PYTHONPATH=coletor python3 coletor/curva_1t_2026.py
"""
import csv
import datetime
import io
import json
import os
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor

import bu

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "dados", "curva_1t_2026.json")
CACHE = os.path.join(RAIZ, ".cache")
CSV_URL = ("https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/"
           "votacao_secao_2026_BR.zip")
PLEITO, CICLO = 3220, "ele2026"
LULA, FLAVIO = "13", "22"
PASSOS = 400          # pontos na curva final


def ufs_do_pleito():
    cfg = bu._get("https://resultados.tse.jus.br/oficial/comum/config/ele-c.json")
    for pl in cfg["pl"]:
        if pl.get("c") == CICLO and str(pl.get("cd")) == str(PLEITO):
            return sorted({a["cd"] for e in pl.get("e", [])
                           for a in e.get("abr", [])} - {"br"})
    return []


def horas_da_uf(uf):
    """{(municipio, zona, secao): hora de recebimento} de uma UF."""
    url = (f"https://resultados.tse.jus.br/oficial/{CICLO}/arquivo-urna/"
           f"{PLEITO}/config/{uf}/{uf}-p{PLEITO:0>6}-cs.json")
    try:
        d = bu._get(url)
    except Exception as e:
        print(f"  {uf}: {e}", file=sys.stderr)
        return {}
    out = {}
    for abr in d.get("abr", []):
        for m in abr.get("mu", []):
            for z in m.get("zon", []):
                for s in z.get("sec", []):
                    if "da" not in s:
                        continue
                    try:
                        q = datetime.datetime.strptime(
                            f"{s['da']} {s['ha']}", "%d/%m/%Y %H:%M:%S")
                    except Exception:
                        continue
                    out[(m["cd"].zfill(5), z["cd"].zfill(4),
                         s["ns"].zfill(4))] = q
    return out


def baixa_csv():
    destino = os.path.join(CACHE, "votacao_secao_2026_BR.zip")
    if not os.path.exists(destino):
        os.makedirs(CACHE, exist_ok=True)
        print("baixando votacao_secao_2026_BR.zip (~161 MB)...", flush=True)
        import urllib.request
        urllib.request.urlretrieve(CSV_URL, destino)
    return destino


def votos_por_secao(caminho):
    """{(mun, zona, secao): [lula, flavio, brancos, nulos, outros]} no 1T."""
    acc = {}
    with zipfile.ZipFile(caminho) as z:
        nome = [n for n in z.namelist() if n.endswith(".csv")][0]
        with z.open(nome) as bruto:
            texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
            for r in csv.DictReader(texto, delimiter=";"):
                if r["NR_TURNO"] != "1" or r["DS_CARGO"].upper() != "PRESIDENTE":
                    continue
                k = (r["CD_MUNICIPIO"].zfill(5), r["NR_ZONA"].zfill(4),
                     r["NR_SECAO"].zfill(4))
                a = acc.setdefault(k, [0, 0, 0, 0, 0])
                qt = int(r["QT_VOTOS"])
                nr, nome_v = r["NR_VOTAVEL"], r["NM_VOTAVEL"]
                if nr == LULA:
                    a[0] += qt
                elif nr == FLAVIO:
                    a[1] += qt
                elif nome_v == "VOTO BRANCO":
                    a[2] += qt
                elif nome_v == "VOTO NULO":
                    a[3] += qt
                else:
                    a[4] += qt          # demais candidatos, também válidos
    return acc


def main():
    ufs = ufs_do_pleito() or [
        "ac", "al", "am", "ap", "ba", "ce", "df", "es", "go", "ma", "mg", "ms",
        "mt", "pa", "pb", "pe", "pi", "pr", "rj", "rn", "ro", "rr", "rs", "sc",
        "se", "sp", "to", "zz"]
    print(f"lendo horários de {len(ufs)} UFs...", flush=True)
    horas = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for parcial in pool.map(horas_da_uf, ufs):
            horas.update(parcial)
    print(f"  {len(horas):,} seções com hora de recebimento".replace(",", "."),
          flush=True)

    print("lendo votos por seção...", flush=True)
    votos = votos_por_secao(baixa_csv())
    print(f"  {len(votos):,} seções com votos".replace(",", "."), flush=True)

    eventos = [(h, votos[k]) for k, h in horas.items() if k in votos]
    eventos.sort(key=lambda e: e[0])
    print(f"  {len(eventos):,} seções cruzadas".replace(",", "."), flush=True)
    if not eventos:
        return 1

    total = len(eventos)
    passo = max(1, total // PASSOS)
    l = f = br = nu = ou = 0
    pontos = []
    for i, (quando, v) in enumerate(eventos, 1):
        l += v[0]; f += v[1]; br += v[2]; nu += v[3]; ou += v[4]
        if i % passo and i != total:
            continue
        # duas bases: a oficial (todos os válidos, com os outros 12
        # candidatos) e a dos dois finalistas, que é a comparável com o 2º turno
        validos = l + f + ou
        dois = l + f
        pontos.append({
            "secoes": i,
            "pct": round(100 * i / total, 4),
            "hora": quando.strftime("%H:%M"),
            "validos": validos,
            "p13": round(100 * l / validos, 3) if validos else None,
            "p22": round(100 * f / validos, 3) if validos else None,
            "d13": round(100 * l / dois, 3) if dois else None,
            "d22": round(100 * f / dois, 3) if dois else None,
        })

    saida = {"eleicao": "1º turno de 2026", "fonte":
             "config de arquivo de urna + votação por seção (dados abertos)",
             "observacao": "curva por hora de recebimento dos boletins, não "
                           "pela totalização oficial",
             "secoes": total, "pontos": pontos}
    json.dump(saida, open(SAIDA, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    u = pontos[-1]
    print(f"\n{len(pontos)} pontos · {total:,} seções".replace(",", "."))
    print(f"  final sobre todos os válidos: Lula {u['p13']}% x Flávio {u['p22']}%"
          f"  ({u['validos']:,} votos)".replace(",", "."))
    print(f"  oficial do 1º turno         : Lula 45,16% x Flávio 47,03%")
    print(f"  final só entre os dois      : Lula {u['d13']}% x Flávio {u['d22']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
