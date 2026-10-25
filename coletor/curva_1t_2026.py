"""Converte o histórico de totalização do 1º turno de 2026 na curva do painel.

O TSE ainda não publicou o "Histórico de Totalização" de 2026 nos dados
abertos (404). Enquanto isso, o mesmo conteúdo existe no arquivo
HISTORICO_EXECUTIVO_PRESIDENTE_BR.json, que traz 384 instantes da apuração,
de 1,23% a 100% das urnas, com os votos de cada candidato em cada um.

Uso:
    python3 coletor/curva_1t_2026.py caminho/HISTORICO_EXECUTIVO_PRESIDENTE_BR.json
    python3 coletor/curva_1t_2026.py https://.../HISTORICO_...json

Antes eu tentava reconstruir essa curva pela hora de recebimento dos boletins
(campo `ha` do config de arquivo de urna). Não funciona: aquele campo carimba
o lote inteiro de cada UF no mesmo instante — São Paulo tem 103.656 seções
dentro de 3 minutos. A curva saía na ordem "UF por UF", que não é a ordem da
apuração, e conferir só o total final não detectava, porque soma não depende
de ordem.
"""
import json
import os
import sys
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "dados", "curva_1t_2026.json")
LULA, FLAVIO = "13", "22"


def num(s):
    return float(str(s or "0").replace(".", "").replace(",", "."))


def inteiro(s):
    return int(str(s or "0").replace(".", "").replace(",", ""))


def carrega(origem):
    if origem.startswith("http"):
        req = urllib.request.Request(origem, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    return json.load(open(origem, encoding="utf-8"))


def main(origem):
    d = carrega(origem)
    mapas = d.get("MAPAS") or []
    if not mapas:
        print("arquivo sem a lista MAPAS", file=sys.stderr)
        return 1

    pontos = []
    for m in mapas:
        votos = {c["n"]: inteiro(c.get("vap")) for c in m.get("CANDIDATOS", [])}
        l, f = votos.get(LULA, 0), votos.get(FLAVIO, 0)
        if not (l + f):
            continue
        # pvap do arquivo já é sobre todos os válidos; a base dos dois
        # finalistas é a comparável com o 2º turno
        pv = {c["n"]: num(c.get("pvap")) for c in m.get("CANDIDATOS", [])}
        dois = l + f
        pontos.append({
            "pct": round(num(m.get("PC_URNAS_APUR")), 4),
            "hora": m.get("HR_MAPA", ""),
            "quando": m.get("DT_TOTALIZACAO", ""),
            "validos": sum(votos.values()),
            "p13": pv.get(LULA), "p22": pv.get(FLAVIO),
            "d13": round(100 * l / dois, 3), "d22": round(100 * f / dois, 3),
        })

    pontos.sort(key=lambda x: x["pct"])
    saida = {"eleicao": "1º turno de 2026",
             "fonte": "histórico de totalização (HISTORICO_EXECUTIVO_PRESIDENTE_BR)",
             "instantes": len(pontos), "pontos": pontos}
    json.dump(saida, open(SAIDA, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))

    p, u = pontos[0], pontos[-1]
    print(f"{len(pontos)} instantes · de {p['hora']} ({p['pct']}% apurado) "
          f"a {u['hora']} ({u['pct']}%)")
    print(f"  final sobre todos os válidos: Lula {u['p13']}% x Flávio {u['p22']}%")
    print(f"  oficial do 1º turno         : Lula 45,16% x Flávio 47,03%")
    print(f"  final só entre os dois      : Lula {u['d13']}% x Flávio {u['d22']}%")
    print(f"-> {SAIDA} ({os.path.getsize(SAIDA) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
