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
SAIDA_BR = os.path.join(RAIZ, "docs", "dados", "brasil_2022.json")
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


def novo():
    return {LULA: 0, BOLSONARO: 0, "brancos": 0, "nulos": 0}


def soma(acc, votavel, qt):
    if votavel in NOMES:
        acc[NOMES[votavel]] += qt
    elif votavel == "VOTO BRANCO":
        acc["brancos"] += qt
    elif votavel == "VOTO NULO":
        acc["nulos"] += qt


def fecha(acc, extra=None):
    validos = acc[LULA] + acc[BOLSONARO]
    out = {LULA: acc[LULA], BOLSONARO: acc[BOLSONARO],
           "brancos": acc["brancos"], "nulos": acc["nulos"],
           "validos": validos,
           "total": validos + acc["brancos"] + acc["nulos"]}
    out.update(extra or {})
    return out


def main():
    caminho = baixa()
    cidades = {}
    ufs, brasil = {}, novo()
    with zipfile.ZipFile(caminho) as z:
        nome = [n for n in z.namelist() if n.endswith(".csv")][0]
        with z.open(nome) as bruto:
            texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
            for r in csv.DictReader(texto, delimiter=";"):
                if r["NR_TURNO"] != "2":
                    continue
                qt = int(r["QT_VOTOS"])
                soma(brasil, r["NM_VOTAVEL"], qt)
                soma(ufs.setdefault(r["SG_UF"].lower(), novo()),
                     r["NM_VOTAVEL"], qt)
                if r["SG_UF"] != "ZZ":
                    continue
                cd = r["CD_MUNICIPIO"]
                c = cidades.setdefault(cd, {
                    "nome": r["NM_MUNICIPIO"], LULA: 0, BOLSONARO: 0,
                    "brancos": 0, "nulos": 0, "secoes": set()})
                c["secoes"].add((r["NR_ZONA"], r["NR_SECAO"]))
                soma(c, r["NM_VOTAVEL"], qt)

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
    print(f"exterior: {len(saida)} cidades · Lula {tl} ({100*tl/(tl+tb):.2f}%) · "
          f"Bolsonaro {tb} ({100*tb/(tl+tb):.2f}%) sobre válidos")

    nacional = {"br": fecha(brasil),
                "ufs": {u: fecha(a) for u, a in sorted(ufs.items())}}
    json.dump(nacional, open(SAIDA_BR, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    b = nacional["br"]
    print(f"Brasil: Lula {b[LULA]} ({100*b[LULA]/b['validos']:.2f}%) · "
          f"Bolsonaro {b[BOLSONARO]} ({100*b[BOLSONARO]/b['validos']:.2f}%) "
          f"sobre {b['validos']} válidos · {len(nacional['ufs'])} UFs")


if __name__ == "__main__":
    main()
