"""Coleta e leitura de Boletins de Urna do TSE (eleições 2026)."""
import json
import os
import time
import urllib.error
import urllib.request

from der import parse

BASE = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

# Tipos de voto no BU (campo CTX1 de cada entrada)
NOMINAL, BRANCO, NULO = 1, 2, 3


class NaoPublicado(Exception):
    """O arquivo não existe (404) — a seção ainda não foi apurada."""


def _get(url, raw=False, tentativas=4):
    """GET com retry. 404 vira NaoPublicado; falha transitória propaga."""
    espera = 1.0
    for n in range(tentativas):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
            return data if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NaoPublicado(url) from None
            if e.code in (403, 429) or e.code >= 500:
                if n == tentativas - 1:
                    raise
            else:
                raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if n == tentativas - 1:
                raise
        time.sleep(espera)
        espera *= 2
    raise RuntimeError(f"falhou após {tentativas} tentativas: {url}")


def secoes_previstas(pleito, uf, municipio):
    """Seções que o TSE prevê para o município, e quais já têm BU gerado."""
    cfg = _get(f"{BASE}/{pleito}/config/{uf}/{uf}-p{pleito:0>6}-cs.json")
    for abr in cfg["abr"]:
        if abr["cd"] != uf:
            continue
        for mu in abr["mu"]:
            if mu["cd"] != municipio:
                continue
            return [(z["cd"], s["ns"], "da" in s)
                    for z in mu["zon"] for s in z["sec"]]
    return []


def baixa_bu(pleito, uf, municipio, zona, secao, cache="cache"):
    """Devolve os bytes do BU, ou None se ainda não foi publicado."""
    os.makedirs(cache, exist_ok=True)
    dest = f"{cache}/p{pleito}-{municipio}-{zona}-{secao}.bu"
    if os.path.exists(dest):
        return open(dest, "rb").read()

    d = f"{BASE}/{pleito}/dados/{uf}/{municipio}/{zona}/{secao}"
    try:
        aux = _get(f"{d}/p{pleito:0>6}-{uf}-m{municipio}-z{zona}-s{secao}-aux.json")
    except NaoPublicado:
        return None

    h = aux["hashes"][0]
    nomes = [a["nm"] for a in h["arq"] if a["tp"] in ("bu", "busa")]
    if not nomes:
        return None
    try:
        bs = _get(f"{d}/{h['hash']}/{nomes[0]}", raw=True)
    except NaoPublicado:
        return None
    with open(dest, "wb") as f:
        f.write(bs)
    return bs


def le_bu(bs):
    """Extrai de um BU: eleição, aptos, comparecimento e votos por número."""
    env = parse(bs)[0][3]
    bu = parse(env[4][3])[0][3]          # o BU vem encapsulado num OCTET STRING

    ident = bu[3][3]
    municipio = int.from_bytes(ident[0][3][0][3], "big")
    zona = int.from_bytes(ident[0][3][1][3], "big")
    secao = int.from_bytes(ident[2][3], "big")

    pleito = bu[7][3][0][3]
    eleicao = int.from_bytes(pleito[0][3], "big")
    aptos = int.from_bytes(pleito[1][3], "big")
    comparecimento = int.from_bytes(bu[6][3], "big")

    votos, nulos, brancos = {}, 0, 0
    for cargo in pleito[4][3]:
        # cargo: [tipo, total de votos, lista de blocos de votação]
        for bloco in cargo[3][2][3]:
            for entrada in bloco[3][2][3]:
                e = entrada[3]
                tipo = int.from_bytes(e[0][3], "big")
                qt = int.from_bytes(e[1][3], "big")
                if tipo == NULO:
                    nulos += qt
                elif tipo == BRANCO:
                    brancos += qt
                else:
                    # voto nominal: o candidato vem num campo construído
                    nr = int.from_bytes(e[2][3][0][3], "big")
                    votos[nr] = votos.get(nr, 0) + qt

    return {"municipio": municipio, "zona": zona, "secao": secao,
            "eleicao": eleicao, "aptos": aptos,
            "comparecimento": comparecimento,
            "votos": votos, "nulos": nulos, "brancos": brancos}
