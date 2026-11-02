"""Vigila el precio de las aspiradoras Xiaomi Robot Vacuum 6 Max y 6 Pro en mi.com/pe.

Avisa por ntfy cuando el precio baja del precio base (PRODUCTOS) o baja todavia mas
durante la misma ejecucion.

Uso:
  python3 check_xiaomi.py                 # una sola revision
  python3 check_xiaomi.py --loop 340 10   # revisa cada 10 min durante 340 min
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

# nombre, tag de la tienda, precio base en soles (avisa si baja de este valor)
PRODUCTOS = [
    ("Robot Vacuum 6 Max", "xiaomi-robot-vacuum-6-max", 3599),
    ("Robot Vacuum 6 Pro", "xiaomi-robot-vacuum-6-pro", 3099),
]
API = "https://go.buy.mi.com/pe/v2/item/productinfo?tag={tag}&is_bundle=0"
PAGE = "https://www.mi.com/pe/product/{tag}/"
TOPIC = os.environ.get("NTFY_TOPIC", "")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")
LIMA = timezone(timedelta(hours=-5))

ultimo_aviso = {}  # tag -> precio con el que ya se aviso en esta ejecucion


def ahora():
    return datetime.now(LIMA).strftime("%Y-%m-%d %H:%M")


def precio(tag):
    req = urllib.request.Request(API.format(tag=tag), headers={
        "User-Agent": UA, "Accept": "application/json",
        "Origin": "https://www.mi.com", "Referer": PAGE.format(tag=tag)})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read().decode("utf-8"))["data"]
    return float(data["item_min_price"]), float(data.get("rrp") or 0)


def notify(title, msg, click):
    if not TOPIC:
        print("NTFY_TOPIC no configurado; no se envia aviso.")
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{TOPIC}", data=msg.encode("utf-8"), method="POST",
        headers={"Title": title.encode("utf-8"), "Priority": "urgent",
                 "Tags": "moneybag,chart_with_downwards_trend", "Click": click})
    urllib.request.urlopen(req, timeout=30).read()


def check_once():
    ok = True
    for nombre, tag, base in PRODUCTOS:
        try:
            p, rrp = precio(tag)
        except Exception as e:
            print(f"[{ahora()}] {nombre}: error al leer el precio: {e}")
            ok = False
            continue
        if p <= 0:
            print(f"[{ahora()}] {nombre}: precio invalido ({p})")
            ok = False
            continue
        bajo = p < base and p < ultimo_aviso.get(tag, base)
        if bajo:
            notify(f"Bajo de precio: Xiaomi {nombre}",
                   f"Ahora S/ {p:,.2f} (antes S/ {base:,.2f}, ahorras S/ {base - p:,.2f}).\n"
                   f"Toca para abrir la pagina.", PAGE.format(tag=tag))
            ultimo_aviso[tag] = p
            print(f"[{ahora()}] {nombre}: S/ {p:,.2f} - BAJO DE PRECIO, aviso enviado")
        else:
            print(f"[{ahora()}] {nombre}: S/ {p:,.2f} (base S/ {base:,.2f}, lista S/ {rrp:,.2f})")
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
