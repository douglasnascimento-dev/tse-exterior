"""Lista as cidades do exterior disponíveis, com o total de seções previstas."""
import json
import sys

import bu


def main(pleito=3221, uf="zz"):
    cfg = bu._get(f"{bu.BASE}/{pleito}/config/{uf}/{uf}-p{pleito:0>6}-cs.json")
    for abr in cfg["abr"]:
        if abr["cd"] != uf:
            continue
        linhas = []
        for mu in abr["mu"]:
            n = sum(len(z["sec"]) for z in mu["zon"])
            linhas.append((mu["nm"], mu["cd"], n))
        for nm, cd, n in sorted(linhas):
            print(f"{cd}  {nm:<28} {n:>3} seções")
        print(f"\n{len(linhas)} cidades")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3221)
