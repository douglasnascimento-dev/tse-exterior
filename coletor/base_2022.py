"""Gera docs/dados/turno2_2022.json — 2º turno de 2022 no exterior, por cidade.

Fonte: Portal de Dados Abertos (votacao_secao_2022_BR.zip), filtrando a UF ZZ.
Resultado final e oficial; roda uma vez e é versionado.

Uso: python3 coletor/base_2022.py
"""
import csv
import io
import json
import os
import urllib.request
import zipfile

URL = ("https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/"
       "votacao_secao_2022_BR.zip")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "dados", "turno2_2022.json")
CACHE = os.path.join(RAIZ, ".cache", "votacao_secao_2022_BR.zip")

# números de urna em 2022 (mesmos de 2026, outros nomes no 22)
LULA, BOLSONARO = "13", "22"
NOMES = {"LUIZ INÁCIO LULA DA SILVA": LULA, "JAIR MESSIAS BOLSONARO": BOLSONARO}


def baixa():
    if not os.path.exists(CACHE):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        print("baixando votacao_secao_2022_BR.zip (~271 MB)...", flush=True)
        urllib.request.urlretrieve(URL, CACHE)
    return CACHE


def main():
    caminho = baixa()
    cidades = {}
    with zipfile.ZipFile(caminho) as z:
        nome = [n for n in z.namelist() if n.endswith(".csv")][0]
        with z.open(nome) as bruto:
            texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
            for r in csv.DictReader(texto, delimiter=";"):
                if r["SG_UF"] != "ZZ" or r["NR_TURNO"] != "2":
                    continue
                cd = r["CD_MUNICIPIO"]
                c = cidades.setdefault(cd, {
                    "nome": r["NM_MUNICIPIO"], LULA: 0, BOLSONARO: 0,
                    "brancos": 0, "nulos": 0, "secoes": set()})
                c["secoes"].add((r["NR_ZONA"], r["NR_SECAO"]))
                qt = int(r["QT_VOTOS"])
                v = r["NM_VOTAVEL"]
                if v in NOMES:
                    c[NOMES[v]] += qt
                elif v == "VOTO BRANCO":
                    c["brancos"] += qt
                elif v == "VOTO NULO":
                    c["nulos"] += qt

    saida = {}
    for cd, c in cidades.items():
        validos = c[LULA] + c[BOLSONARO]
        saida[cd] = {
            "nome": c["nome"], LULA: c[LULA], BOLSONARO: c[BOLSONARO],
            "brancos": c["brancos"], "nulos": c["nulos"],
            "validos": validos,
            "total": validos + c["brancos"] + c["nulos"],
            "secoes": len(c["secoes"]),
        }

    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    json.dump(saida, open(SAIDA, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    tl = sum(c[LULA] for c in saida.values())
    tb = sum(c[BOLSONARO] for c in saida.values())
    print(f"{len(saida)} cidades · Lula {tl} ({100*tl/(tl+tb):.2f}%) · "
          f"Bolsonaro {tb} ({100*tb/(tl+tb):.2f}%) sobre válidos")


if __name__ == "__main__":
    main()
