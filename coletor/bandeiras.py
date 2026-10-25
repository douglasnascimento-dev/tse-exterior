"""Descobre o código ISO de cada país, para a bandeira no painel.

Geocodificação reversa das coordenadas já conhecidas: o país é determinado
pelo ponto, não pelo nome. Grava 'iso2' em docs/dados/coordenadas.json.
Roda uma vez; o resultado é versionado.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORD = os.path.join(RAIZ, "docs", "dados", "coordenadas.json")
UA = "tse-exterior/1.0 (dashboard de apuracao; contato via GitHub)"

# Postos onde o ponto cai num país mas a bandeira esperada é outra.
MANUAL = {"HONG KONG": "hk", "TAIPÉ": "tw", "RAMALLAH": "ps",
          "CAIENA": "gf", "ST GEORGES DE LOYAPOCK": "gf"}


def reverso(lat, lon):
    url = ("https://nominatim.openstreetmap.org/reverse?"
           + urllib.parse.urlencode({"lat": lat, "lon": lon, "format": "json",
                                     "zoom": 3, "addressdetails": 1}))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    return (d.get("address") or {}).get("country_code")


def main():
    coords = json.load(open(COORD, encoding="utf-8"))
    faltando = []
    for cd, v in sorted(coords.items(), key=lambda x: x[1]["nome"]):
        if v.get("iso2"):
            continue
        if v["nome"] in MANUAL:
            v["iso2"] = MANUAL[v["nome"]]
            continue
        if v.get("lat") is None:
            faltando.append(v["nome"])
            continue
        try:
            iso = reverso(v["lat"], v["lon"])
        except Exception as e:
            print(f"  erro {v['nome']}: {e}", file=sys.stderr)
            iso = None
        time.sleep(1.1)                       # política do Nominatim
        if iso:
            v["iso2"] = iso.lower()
            print(f"  {v['nome']:<26} {v.get('pais','')[:22]:<23} {iso.upper()}")
        else:
            faltando.append(v["nome"])
            print(f"  {v['nome']:<26} SEM CÓDIGO")

    json.dump(coords, open(COORD, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    com = sum(1 for v in coords.values() if v.get("iso2"))
    print(f"\n{com}/{len(coords)} com código ISO"
          + (f" · sem: {', '.join(faltando)}" if faltando else ""))


if __name__ == "__main__":
    main()
