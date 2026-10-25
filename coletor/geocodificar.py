"""Geocodifica as cidades do exterior uma única vez (Nominatim/OSM).

O resultado vai para docs/dados/coordenadas.json e é versionado — a coleta
periódica não refaz geocoding. Correções manuais ficam em
coletor/coordenadas_manuais.json e sempre têm precedência.

Uso: PYTHONPATH=coletor python3 coletor/geocodificar.py
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import bu

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "dados", "coordenadas.json")
MANUAIS = os.path.join(RAIZ, "coletor", "coordenadas_manuais.json")
UA = "tse-exterior/1.0 (dashboard de apuracao; contato via GitHub)"


def busca(nome, pais=None):
    q = f"{nome}, {pais}" if pais else nome
    url = ("https://nominatim.openstreetmap.org/search?"
           + urllib.parse.urlencode({"q": q, "format": "json", "limit": 1,
                                     "accept-language": "pt"}))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if not d:
        return None
    return {"lat": round(float(d[0]["lat"]), 4),
            "lon": round(float(d[0]["lon"]), 4),
            "match": d[0].get("display_name", "")}


def main(pleito=3221, uf="zz"):
    cfg = bu._get(f"{bu.BASE}/{pleito}/config/{uf}/{uf}-p{pleito:0>6}-cs.json")
    cidades = {}
    for abr in cfg["abr"]:
        if abr["cd"] == uf:
            for mu in abr["mu"]:
                cidades[mu["cd"]] = mu["nm"]

    manuais = {}
    if os.path.exists(MANUAIS):
        manuais = json.load(open(MANUAIS, encoding="utf-8"))

    antigo = {}
    if os.path.exists(SAIDA):
        antigo = json.load(open(SAIDA, encoding="utf-8"))

    out, faltando = {}, []
    for cd, nm in sorted(cidades.items(), key=lambda x: x[1]):
        if cd in manuais:
            out[cd] = {"nome": nm, **manuais[cd], "fonte": "manual"}
            continue
        if cd in antigo and antigo[cd].get("fonte") != "falha":
            out[cd] = antigo[cd]
            continue
        try:
            r = busca(nm)
        except Exception as e:
            print(f"  erro {nm}: {e}", file=sys.stderr)
            r = None
        time.sleep(1.1)                      # política de uso do Nominatim
        if r:
            out[cd] = {"nome": nm, "lat": r["lat"], "lon": r["lon"],
                       "fonte": "nominatim", "match": r["match"]}
            print(f"  {nm:<26} {r['lat']:>9.4f} {r['lon']:>10.4f}  {r['match'][:52]}")
        else:
            out[cd] = {"nome": nm, "fonte": "falha"}
            faltando.append((cd, nm))
            print(f"  {nm:<26} SEM RESULTADO")

    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    json.dump(out, open(SAIDA, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    print(f"\n{len(out)} cidades · {len(faltando)} sem coordenada")
    for cd, nm in faltando:
        print(f"   falta: {cd} {nm}")


if __name__ == "__main__":
    main()
