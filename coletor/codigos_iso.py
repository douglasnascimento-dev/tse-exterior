"""Atribui o código ISO alpha-2 a cada cidade, para a bandeira no painel.

Sem rede: o mapa do mundo traz o código ISO numérico de cada país e a tabela
oficial vem do pacote iso-codes, presente na maioria das distribuições Linux
(/usr/share/iso-codes/json/iso_3166-1.json). O resultado é versionado, então
quem clonar o repositório não precisa do pacote.
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORD = os.path.join(RAIZ, "docs", "dados", "coordenadas.json")
MUNDO = os.path.join(RAIZ, "docs", "dados", "mundo.json")
TABELA = "/usr/share/iso-codes/json/iso_3166-1.json"

# Cidades sem polígono no mapa 110m, ou cujo país político difere do desenhado.
MANUAL = {
    "SINGAPURA": "sg", "BAREIN": "bh", "BRIDGETOWN": "bb", "PRAIA": "cv",
    "SÃO TOMÉ": "st", "SAINT JOHNS": "ag", "CASTRIES": "lc",
    "HONG KONG": "hk", "CAIENA": "gf", "ST GEORGES DE LOYAPOCK": "gf",
    "NICOSIA": "cy",        # o ponto cai em "N. Cyprus", que não tem código ISO
}


def main():
    if not os.path.exists(TABELA):
        print(f"tabela ISO não encontrada em {TABELA}.\n"
              "Instale o pacote iso-codes, ou use o coordenadas.json versionado.",
              file=sys.stderr)
        return 1

    iso = json.load(open(TABELA, encoding="utf-8"))["3166-1"]
    por_num = {e["numeric"]: e["alpha_2"].lower() for e in iso if "numeric" in e}

    mundo = json.load(open(MUNDO, encoding="utf-8"))
    por_pais = {}
    for f in mundo["features"]:
        num = str(f["properties"].get("num", "")).zfill(3)
        if num in por_num:
            por_pais[f["properties"]["nome"]] = por_num[num]

    coords = json.load(open(COORD, encoding="utf-8"))
    sem = []
    for v in coords.values():
        if v["nome"] in MANUAL:
            v["iso2"] = MANUAL[v["nome"]]
            continue
        cod = por_pais.get(v.get("pais_mapa"))
        if cod:
            v["iso2"] = cod
        else:
            sem.append(v["nome"])

    json.dump(coords, open(COORD, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    com = sum(1 for v in coords.values() if v.get("iso2"))
    print(f"{com}/{len(coords)} cidades com código ISO")
    if sem:
        print("  sem código:", ", ".join(sem))
    return 0


if __name__ == "__main__":
    sys.exit(main())
