"""Gera docs/dados/mundo.json — contornos dos países para o mapa.

Converte o TopoJSON do world-atlas (Natural Earth 110m) em GeoJSON simples,
com coordenadas arredondadas. Roda uma vez; o arquivo é versionado.
"""
import json
import os
import urllib.request

FONTE = "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "dados", "mundo.json")
CASAS = 2          # ~1 km; sobra precisão para um mapa-múndi


def decodifica_arcos(topo):
    """Desfaz a quantização e o delta-encoding dos arcos do TopoJSON."""
    t = topo.get("transform")
    saida = []
    for arco in topo["arcs"]:
        x = y = 0
        pontos = []
        for dx, dy in arco:
            x += dx
            y += dy
            if t:
                px = x * t["scale"][0] + t["translate"][0]
                py = y * t["scale"][1] + t["translate"][1]
            else:
                px, py = x, y
            pontos.append([round(px, CASAS), round(py, CASAS)])
        saida.append(pontos)
    return saida


def linha(arcos, indices):
    pts = []
    for i in indices:
        a = arcos[~i][::-1] if i < 0 else arcos[i]
        pts.extend(a[1:] if pts else a)
    return pts


def main():
    with urllib.request.urlopen(FONTE, timeout=60) as r:
        topo = json.load(r)
    arcos = decodifica_arcos(topo)

    feicoes = []
    for g in topo["objects"]["countries"]["geometries"]:
        nome = (g.get("properties") or {}).get("name", "")
        if g["type"] == "Polygon":
            coords = [linha(arcos, anel) for anel in g["arcs"]]
        elif g["type"] == "MultiPolygon":
            coords = [[linha(arcos, anel) for anel in poly] for poly in g["arcs"]]
        else:
            continue
        feicoes.append({"type": "Feature",
                        "properties": {"nome": nome},
                        "geometry": {"type": g["type"], "coordinates": coords}})

    gj = {"type": "FeatureCollection", "features": feicoes}
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(gj, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(feicoes)} países · {os.path.getsize(SAIDA) / 1024:.0f} KB -> {SAIDA}")


if __name__ == "__main__":
    main()
