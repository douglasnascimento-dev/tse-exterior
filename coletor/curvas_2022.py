"""Extrai as curvas de totalização de 2022 (1º e 2º turnos, Brasil).

O TSE publica o histórico minuto a minuto de eleições passadas em
"Histórico de Totalização". Aqui ele vira uma curva enxuta, indexada pelo
percentual de seções totalizadas — que é o eixo comparável entre eleições
diferentes.

Uso: python3 coletor/curvas_2022.py
"""
import csv
import io
import json
import os
import sys
import urllib.request
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "dados", "curvas_2022.json")
CACHE = os.path.join(RAIZ, ".cache")
BASE = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022"
PASSOS = 400


def num(s):
    s = (s or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def baixa(turno):
    nome = f"Historico_Totalizacao_Presidente_BR_{turno}_2022.zip"
    destino = os.path.join(CACHE, nome)
    if not os.path.exists(destino):
        os.makedirs(CACHE, exist_ok=True)
        print(f"baixando {nome}...", flush=True)
        urllib.request.urlretrieve(f"{BASE}/{nome}", destino)
    return destino


def curva(turno):
    with zipfile.ZipFile(baixa(turno)) as z:
        nome = [n for n in z.namelist() if n.endswith(".csv")][0]
        with z.open(nome) as bruto:
            texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
            linhas = list(csv.DictReader(texto, delimiter=";"))

    campos = {k.strip(): k for k in linhas[0]}

    def c(r, nome_campo):
        return r.get(campos.get(nome_campo, ""), "")

    # o arquivo do 1º turno não traz coluna de UF (já é só Brasil); o do 2º traz
    tem_uf = "SG_UE_UF" in campos
    pontos = []
    for r in linhas:
        if tem_uf and c(r, "SG_UE_UF").strip() != "BR":
            continue
        pct = num(c(r, "PE_SECOES_TOT_ACUMULADO")) * 100
        l = num(c(r, "LULA_QT_VOTOS_TOT_ACUMULADO"))
        b = num(c(r, "JAIR_BOLSONARO_QT_VOTOS_TOT_ACUMULADO"))
        conc = num(c(r, "QT_VOTOS_CONCORRENTES_ACUMULADO"))
        if not (l + b):
            continue
        dois = l + b
        validos = conc or dois
        pontos.append({
            "pct": round(pct, 4),
            "hora": c(r, "DT_TOTALIZACAO").strip()[11:16],
            "quando": c(r, "DT_TOTALIZACAO").strip(),
            "validos": int(validos),
            "p13": round(100 * l / validos, 3),
            "p22": round(100 * b / validos, 3),
            "d13": round(100 * l / dois, 3),
            "d22": round(100 * b / dois, 3),
        })

    pontos.sort(key=lambda x: x["pct"])
    if len(pontos) > PASSOS:                       # desbasta mantendo o fim
        passo = len(pontos) / PASSOS
        pontos = [pontos[int(i * passo)] for i in range(PASSOS)] + [pontos[-1]]
    return pontos


def main():
    saida = {}
    for turno, rot in (("1T", "1º turno de 2022"), ("2T", "2º turno de 2022")):
        p = curva(turno)
        saida[turno] = {"rotulo": rot, "pontos": p}
        u = p[-1]
        print(f"{rot}: {len(p)} pontos · final Lula {u['p13']}% x "
              f"Bolsonaro {u['p22']}% (sobre válidos) · "
              f"{u['d13']}% x {u['d22']}% (só entre os dois)")

    json.dump(saida, open(SAIDA, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"-> {SAIDA} ({os.path.getsize(SAIDA) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
