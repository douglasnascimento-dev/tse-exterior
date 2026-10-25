"""Parser DER/BER genérico, suficiente para os BUs do TSE."""

CLASSES = {0: "UNIV", 1: "APPL", 2: "CTX", 3: "PRIV"}
UNIV = {1: "BOOL", 2: "INT", 3: "BITSTR", 4: "OCTSTR", 5: "NULL", 6: "OID",
        10: "ENUM", 12: "UTF8", 19: "PRINTSTR", 22: "IA5", 26: "VISSTR",
        27: "GENSTR", 16: "SEQ", 17: "SET", 24: "GENTIME"}


def _len(buf, i):
    n = buf[i]
    i += 1
    if n < 0x80:
        return n, i
    k = n & 0x7F
    return int.from_bytes(buf[i:i + k], "big"), i + k


def parse(buf, i=0, end=None):
    """Devolve lista de nós: (tag_str, tag_num, constructed, valor_ou_filhos)."""
    if end is None:
        end = len(buf)
    out = []
    while i < end:
        t = buf[i]
        cls, cons, num = t >> 6, bool(t & 0x20), t & 0x1F
        i += 1
        if num == 0x1F:                      # tag de múltiplos bytes
            num = 0
            while buf[i] & 0x80:
                num = (num << 7) | (buf[i] & 0x7F)
                i += 1
            num = (num << 7) | buf[i]
            i += 1
        ln, i = _len(buf, i)
        body = buf[i:i + ln]
        name = UNIV.get(num, str(num)) if cls == 0 else f"{CLASSES[cls]}{num}"
        out.append((name, num, cons, parse(body, 0, ln) if cons else body))
        i += ln
    return out


def dump(nodes, depth=0, path=""):
    for k, (name, num, cons, val) in enumerate(nodes):
        p = f"{path}.{k}"
        pad = "  " * depth
        if cons:
            print(f"{pad}{p:<14} {name}")
            dump(val, depth + 1, p)
        else:
            if name == "INT" or name == "ENUM":
                shown = int.from_bytes(val, "big") if val else 0
            elif name in ("UTF8", "PRINTSTR", "IA5", "VISSTR", "GENSTR", "GENTIME"):
                shown = val.decode("latin-1")
            else:
                shown = val.hex() if len(val) <= 24 else val[:24].hex() + "..."
            print(f"{pad}{p:<14} {name:<9} {shown}")
