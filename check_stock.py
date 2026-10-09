"""Revisa el stock del iPhone 18 Pro Max en Entel Peru y avisa por ntfy si hay unidades."""
import os
import re
import sys
import urllib.request

URL = "https://miportal.entel.pe/personas/producto/equipos/iphone-18-pro-max/prod1120059"
BUY_URL = (URL + "?poId=PO_BSC_EQP_33890&modalidad=Renovacion&planId=undefined"
           "&oferta=regular&cuota=0&flow=equipos")
TOPIC = os.environ.get("NTFY_TOPIC", "")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-PE,es"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", errors="replace")


def parse(html):
    """Devuelve lista de (color, stockDelivery, stockPickup)."""
    out = []
    for m in re.finditer(r'"stockDelivery"\s*:\s*(\d+)\s*,\s*"stockPickup"\s*:\s*(\d+)', html):
        tail = html[m.end():m.end() + 600]
        c = re.search(r"Apple_iPhone_18_Pro_Max_([A-Za-z]+)_Img", tail)
        out.append((c.group(1) if c else "?", int(m.group(1)), int(m.group(2))))
    # quitar duplicados conservando orden
    seen, uniq = set(), []
    for row in out:
        if row not in seen:
            seen.add(row)
            uniq.append(row)
    return uniq


def notify(title, msg):
    if not TOPIC:
        print("NTFY_TOPIC no configurado; no se envia aviso.")
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{TOPIC}", data=msg.encode("utf-8"), method="POST",
        headers={"Title": title.encode("utf-8"), "Priority": "urgent",
                 "Tags": "iphone,rotating_light", "Click": BUY_URL})
    urllib.request.urlopen(req, timeout=30).read()


def main():
    rows = parse(fetch(URL))
    if not rows:
        print("No se encontraron los campos de stock: la pagina pudo cambiar o bloquear la consulta.")
        sys.exit(1)  # el workflow falla y GitHub te avisa por correo
    for color, d, p in rows:
        print(f"{color}: delivery={d} pickup={p}")
    disponibles = [(c, d, p) for c, d, p in rows if d > 0 or p > 0]
    if disponibles:
        detalle = "\n".join(f"{c}: {d} delivery / {p} recojo" for c, d, p in disponibles)
        notify("iPhone 18 Pro Max CON STOCK en Entel", detalle + "\nToca para abrir la pagina.")
        print("STOCK DISPONIBLE - aviso enviado")
    else:
        print("Sigue agotado")


if __name__ == "__main__":
    main()
