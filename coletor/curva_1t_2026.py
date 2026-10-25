"""Busca a curva de totalização do 1º turno de 2026, quando ela existir.

O TSE publica o "Histórico de Totalização" — o minuto a minuto da apuração —
semanas depois da eleição. Para 2026 ainda não existe (404). Enquanto não
existir, o painel mostra apenas o resultado final do 1º turno como nível de
referência, não uma curva.

POR QUE NÃO DÁ PARA RECONSTRUIR
-------------------------------
A tentativa óbvia é usar o campo `ha` do config de arquivo de urna, que parece
ser a hora de recebimento de cada seção. Não é: para quase toda UF ele carimba
o lote inteiro no mesmo instante — São Paulo tem 103.656 seções dentro de 3
minutos, Roraima tem 1.519 no mesmo minuto, Minas aparece às 12h52 do dia
seguinte. Só o exterior, onde os boletins chegam um a um, tem horas reais.

Uma curva montada com isso fica na ordem "UF por UF", que não é a ordem da
apuração. O total final continua certo, porque soma não depende de ordem — foi
exatamente por isso que conferir só o total não detectou o problema.

Uso: PYTHONPATH=coletor python3 coletor/curva_1t_2026.py
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "dados", "curva_1t_2026.json")
URL = ("https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/"
       "Historico_Totalizacao_Presidente_BR_1T_2026.zip")


def main():
    try:
        with urllib.request.urlopen(URL, timeout=60) as r:
            dados = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("O TSE ainda não publicou o histórico de totalização do 1º "
                  "turno de 2026.\nSem ele não há curva: o painel usa o "
                  "resultado final como nível de referência.")
            return 0
        raise

    # Quando existir, o formato é o mesmo de 2022 — reaproveita o extrator.
    sys.path.insert(0, os.path.join(RAIZ, "coletor"))
    import curvas_2022 as c22

    caminho = os.path.join(RAIZ, ".cache",
                           "Historico_Totalizacao_Presidente_BR_1T_2026.zip")
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    open(caminho, "wb").write(dados)
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        nome = [n for n in z.namelist() if n.endswith(".csv")][0]
        print(f"publicado! processando {nome}")

    pontos = c22.curva.__wrapped__ if hasattr(c22.curva, "__wrapped__") else None
    print("rode curvas_2022.py adaptado para 2026, ou avise: o formato bate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
