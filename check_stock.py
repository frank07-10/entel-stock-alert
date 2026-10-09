"""Revisa el stock del iPhone 18 Pro Max en Entel Peru y avisa por ntfy si hay unidades.

Uso:
  python3 check_stock.py                 # una sola revision
  python3 check_stock.py --loop 340 10   # revisa cada 10 min durante 340 min
"""
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

URL = "https://miportal.entel.pe/personas/producto/equipos/iphone-18-pro-max/prod1120059"
BUY_URL = (URL + "?poId=PO_BSC_EQP_33890&modalidad=Renovacion&planId=undefined"
           "&oferta=regular&cuota=0&flow=equipos")
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
    """Devuelve lista de (color, stockDelivery, stockPickup)."""
    out = []
    for m in re.finditer(r'"stockDelivery"\s*:\s*(\d+)\s*,\s*"stockPickup"\s*:\s*(\d+)', html):
        tail = html[m.end():m.end() + 600]
        c = re.search(r"Apple_iPhone_18_Pro_Max_([A-Za-z]+)_Img", tail)
        out.append((c.group(1) if c else "?", int(m.group(1)), int(m.group(2))))
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


def check_once():
    """True si la revision funciono, False si no se pudo leer el stock."""
    try:
        rows = parse(fetch(URL))
    except Exception as e:  # red, timeout, bloqueo
        print(f"[{ahora()}] Error al leer la pagina: {e}")
        return False
    if not rows:
        print(f"[{ahora()}] No se encontraron los campos de stock (la pagina pudo cambiar).")
        return False
    disponibles = [(c, d, p) for c, d, p in rows if d > 0 or p > 0]
    resumen = ", ".join(f"{c} {d}/{p}" for c, d, p in rows)
    if disponibles:
        detalle = "\n".join(f"{c}: {d} delivery / {p} recojo" for c, d, p in disponibles)
        notify("iPhone 18 Pro Max CON STOCK en Entel", detalle + "\nToca para abrir la pagina.")
        print(f"[{ahora()}] STOCK DISPONIBLE - aviso enviado ({resumen})")
    else:
        print(f"[{ahora()}] Sigue agotado ({resumen})")
    return True


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
