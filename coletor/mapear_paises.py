"""Liga cada cidade do exterior ao polígono de país do mapa.

Faz por geometria (ponto dentro do polígono), não por nome: os nomes vêm do
Nominatim em português e o mapa usa inglês. Grava 'pais_mapa' em
docs/dados/coordenadas.json. Roda uma vez, junto com mapa_base.py.
"""
import json
import math
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORD = os.path.join(RAIZ, "docs", "dados", "coordenadas.json")
MUNDO = os.path.join(RAIZ, "docs", "dados", "mundo.json")


def aneis(geom):
    """Anéis externos de um Polygon ou MultiPolygon."""
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [poly[0] for poly in geom["coordinates"]]


def dentro(x, y, anel):
    """Ray casting: o ponto está dentro do anel?"""
    d = False
    n = len(anel)
    for i in range(n):
        x1, y1 = anel[i]
        x2, y2 = anel[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xc = x1 + (y - y1) / (y2 - y1) * (x2 - x1)
            if x < xc:
                d = not d
    return d


def dist_min(x, y, anel):
    return min(math.hypot(x - px, y - py) for px, py in anel)


# Correções onde a geometria 110m não resolve. None = sem polígono no mapa
# (o painel desenha um ponto em vez de pintar um país).
# O mapa 110m não traz países pequenos e insulares. Sem correção, o vizinho
# mais próximo seria pintado no lugar — Singapura viraria Malásia, Barein
# viraria Arábia Saudita. None = o painel desenha um ponto, não pinta país.
MANUAL = {
    "ST GEORGES DE LOYAPOCK": "France",   # Guiana Francesa, cai do lado brasileiro
    "MALABO": "Eq. Guinea",               # ilha de Bioco, vizinha de Camarões
    "SINGAPURA": None,                    # vizinho seria a Malásia
    "BAREIN": None,                       # vizinho seria a Arábia Saudita
    "BRIDGETOWN": None,                   # Barbados
    "SÃO TOMÉ": None,                     # São Tomé e Príncipe
    "PRAIA": None,                        # Cabo Verde
    "SAINT JOHNS": None,                  # Antígua e Barbuda
    "CASTRIES": None,                     # Santa Lúcia
}


def main():
    coords = json.load(open(COORD, encoding="utf-8"))
    mundo = json.load(open(MUNDO, encoding="utf-8"))
    feats = [(f["properties"]["nome"], aneis(f["geometry"]))
             for f in mundo["features"]]

    acertos = aprox = 0
    for cd, v in coords.items():
        if v.get("lat") is None:
            continue
        if v["nome"] in MANUAL:
            v["pais_mapa"] = MANUAL[v["nome"]]
            v["pais_mapa_fonte"] = "manual"
            continue
        x, y = v["lon"], v["lat"]
        achou = None
        for nome, rings in feats:
            if any(dentro(x, y, r) for r in rings):
                achou = nome
                break
        if achou:
            acertos += 1
            v["pais_mapa_fonte"] = "poligono"
        else:
            # cidade costeira ou ilha pequena some no mapa 110m: usa o país
            # cujo contorno estiver mais perto, se for perto o bastante.
            melhor, dmin = None, 1e9
            for nome, rings in feats:
                d = min(dist_min(x, y, r) for r in rings)
                if d < dmin:
                    melhor, dmin = nome, d
            achou = melhor if dmin < 0.6 else None       # ~65 km
            v["pais_mapa_fonte"] = "proximidade" if achou else "nenhum"
            if achou:
                aprox += 1
                print(f"  por proximidade: {v['nome']} -> {achou} "
                      f"({dmin:.2f}°)")
        v["pais_mapa"] = achou

    json.dump(coords, open(COORD, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    sem = [v["nome"] for v in coords.values() if not v.get("pais_mapa")]
    print(f"{acertos} dentro do polígono · {aprox} por proximidade · "
          f"{len(sem)} sem país no mapa")
    if sem:
        print("  sem polígono:", ", ".join(sem))


if __name__ == "__main__":
    main()
