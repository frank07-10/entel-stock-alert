"""Revisa el stock del iPhone 18 Pro Max (256GB y 512GB) en Entel Peru y avisa por ntfy.

Solo considera los colores de COLORES.

Uso:
  python3 check_stock.py                 # una sola revision
  python3 check_stock.py --verify        # revisa y falla si no encuentra todos los colores/capacidades
  python3 check_stock.py --loop 340 10   # revisa cada 10 min durante 340 min
"""
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://miportal.entel.pe/personas/producto/equipos/iphone-18-pro-max/"
PRODUCTOS = [
    ("256GB", BASE + "prod1120059",
     BASE + "prod1120059?poId=PO_BSC_EQP_33890&modalidad=Renovacion&planId=undefined"
            "&oferta=regular&cuota=0&flow=equipos"),
    ("512GB", BASE + "prod1120060",
     BASE + "prod1120060?poId=PO_BSC_EQP_33940&modalidad=Renovacion&planId=PO_POS_OO_24453"
            "&oferta=regular&cuota=0&flow=equipos"),
]
COLORES = {"black", "burgundy"}
TOPIC = os.environ.get("NTFY_TOPIC", "")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")
LIMA = timezone(timedelta(hours=-5))


def ahora():
    return datetime.now(LIMA).strftime("%Y-%m-%d %H:%M")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-PE,es"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", errors="replace")


def parse(html):
    """Devuelve dict color -> (stockDelivery, stockPickup), con el maximo si hay repetidos."""
    out = {}
    for m in re.finditer(r'"stockDelivery"\s*:\s*(\d+)\s*,\s*"stockPickup"\s*:\s*(\d+)', html):
        tail = html[m.end():m.end() + 600]
        c = re.search(r"iPhone_18_Pro_Max_([A-Za-z]+(?:_[A-Za-z]+)*?)_Img", tail)
        color = c.group(1).replace("_", " ") if c else "?"
        d, p = int(m.group(1)), int(m.group(2))
        prev = out.get(color, (0, 0))
        out[color] = (max(prev[0], d), max(prev[1], p))
    return out


def notify(title, msg, click):
    if not TOPIC:
        print("NTFY_TOPIC no configurado; no se envia aviso.")
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{TOPIC}", data=msg.encode("utf-8"), method="POST",
        headers={"Title": title.encode("utf-8"), "Priority": "urgent",
                 "Tags": "iphone,rotating_light", "Click": click})
    urllib.request.urlopen(req, timeout=30).read()


def check_once():
    """True si se pudo leer el stock de todos los colores buscados en ambas capacidades."""
    ok = True
    for cap, url, buy in PRODUCTOS:
        try:
            stock = parse(fetch(url))
        except Exception as e:  # red, timeout, bloqueo
            print(f"[{ahora()}] {cap}: error al leer la pagina: {e}")
            ok = False
            continue
        buscados = {c: v for c, v in stock.items() if c.lower() in COLORES}
        faltan = COLORES - {c.lower() for c in buscados}
        if faltan:
            print(f"[{ahora()}] {cap}: no se encontraron los colores {sorted(faltan)} "
                  f"(colores en la pagina: {sorted(stock)})")
            ok = False
        resumen = ", ".join(f"{c} {d}/{p}" for c, (d, p) in buscados.items())
        disponibles = {c: v for c, v in buscados.items() if v[0] > 0 or v[1] > 0}
        if disponibles:
            detalle = "\n".join(f"{c}: {d} delivery / {p} recojo" for c, (d, p) in disponibles.items())
            notify(f"iPhone 18 Pro Max {cap} CON STOCK en Entel",
                   detalle + "\nToca para abrir la pagina.", buy)
            print(f"[{ahora()}] {cap}: STOCK DISPONIBLE - aviso enviado ({resumen})")
        else:
            print(f"[{ahora()}] {cap}: sigue agotado ({resumen})")
    return ok


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--loop":
        total_min = int(sys.argv[2]) if len(sys.argv) > 2 else 340
        every_min = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        fin = time.time() + total_min * 60
        fallos = 0
        while True:
            fallos = 0 if check_once() else fallos + 1
            if fallos >= 3:
                print("3 fallos seguidos: se detiene para que GitHub avise por correo.")
                sys.exit(1)
            if time.time() + every_min * 60 > fin:
                break
            time.sleep(every_min * 60)
    else:
        sys.exit(0 if check_once() else 1)


if __name__ == "__main__":
    main()
