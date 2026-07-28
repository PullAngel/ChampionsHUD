#!/usr/bin/env python3
"""
build_sprite_index.py — Champions HUD, paso 1

Descarga los menu sprites de Pokemon Champions (normales Y variocolor) desde
Bulbagarden Archives y construye el indice de huellas que usa el HUD para
identificar al equipo rival.

Mejoras sobre la version que tardaba horas:
  - una sola sesion HTTP reutilizada, en vez de abrir conexion por archivo
  - descargas en paralelo (8 hilos por defecto, configurable)
  - reintentos con espera creciente cuando el servidor corta
  - reanuda solo: lo ya descargado y valido no se vuelve a bajar
  - progreso con velocidad y tiempo restante
  - los que fallan se reintentan todos juntos al final
  - la huella se calcula solo si el PNG bajo entero y valido

En una conexion normal deberia tardar 2-4 minutos.

Uso:
    pip install requests pillow numpy
    python build_sprite_index.py                 # normales + variocolor
    python build_sprite_index.py --no-shiny      # solo normales
    python build_sprite_index.py --workers 12    # mas agresivo

Licencia de los sprites: CC BY-NC-SA 2.5 (Bulbagarden). Uso no comercial.
"""

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import numpy as np
import requests
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = "https://archives.bulbagarden.net/w/api.php"
CATS = [
    ("normal", "Category:Champions menu sprites"),
    ("shiny", "Category:Champions Shiny menu sprites"),
]
UA = "ChampionsHUD/0.4 (proyecto personal no comercial)"

OUT_DIR = Path("sprites")
INDEX = Path("sprite_index.json")
GRID = 16
CGRID = 8      # rejilla de color, mas gruesa: alcanza para desempatar

_lock = Lock()


def make_session(workers):
    """Sesion unica, pool grande y reintentos automaticos a nivel transporte."""
    s = requests.Session()
    s.headers["User-Agent"] = UA
    retry = Retry(total=5, connect=5, read=5, backoff_factor=0.8,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset(["GET"]))
    ad = HTTPAdapter(pool_connections=workers * 2, pool_maxsize=workers * 2,
                     max_retries=retry)
    s.mount("https://", ad)
    s.mount("http://", ad)
    return s


def list_category(sess, category):
    out, cont = [], {}
    while True:
        r = sess.get(API, params={
            "action": "query", "generator": "categorymembers",
            "gcmtitle": category, "gcmtype": "file", "gcmlimit": "500",
            "prop": "imageinfo", "iiprop": "url",
            "format": "json", "formatversion": "2", **cont,
        }, timeout=60)
        r.raise_for_status()
        data = r.json()
        for page in data.get("query", {}).get("pages", []):
            info = page.get("imageinfo")
            if info:
                out.append((page["title"], info[0]["url"]))
        if "continue" not in data:
            return out
        cont = data["continue"]


# Los variocolor llevan «shiny» como SUFIJO, no como prefijo:
#     Menu CP 0003 shiny.png
#     Menu CP 0128-Paldea Aqua shiny.png
# El patron anterior lo esperaba al principio, asi que descartaba en silencio
# los que no tenian forma con guion — dos tercios de la categoria — y a los que
# si tenian les metia « shiny» dentro del nombre de la forma.
NAME_RE = re.compile(r"^Menu[ _]CP[ _](\d{4})(?:-(.+?))?(?:[ _]shiny)?\.png$", re.I)


def parse(title, from_shiny_cat):
    name = title.split(":", 1)[-1]
    m = NAME_RE.match(name)
    if not m:
        return None
    dex = int(m.group(1))
    form = (m.group(2) or "").replace("_", " ").strip()
    # El nombre manda: si dice shiny, es shiny, venga de la categoria que venga.
    shiny = from_shiny_cat or bool(re.search(r"[ _]shiny\.png$", name, re.I))
    slug = f"{dex:04d}"
    if form:
        slug += "-" + form.lower().replace(" ", "-")
    if shiny:
        slug += "-shiny"
    return dex, form, slug, shiny


def valid_png(path):
    """Un PNG a medio bajar no sirve: mejor detectarlo aca que al calcular."""
    try:
        if path.stat().st_size < 200:
            return False
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False


def download(sess, url, dest, tries=4):
    if dest.exists() and valid_png(dest):
        return "cache"
    last = None
    for i in range(tries):
        try:
            r = sess.get(url, timeout=45)
            r.raise_for_status()
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(r.content)
            if not valid_png(tmp):
                tmp.unlink(missing_ok=True)
                raise ValueError("PNG incompleto")
            tmp.replace(dest)
            return "ok"
        except Exception as e:
            last = e
            time.sleep(0.5 * (2 ** i))          # espera creciente
    raise RuntimeError(str(last))


def fingerprint(path):
    """
    Huella NORMALIZADA POR CAJA ENVOLVENTE.

    Esta es la correccion clave. Antes se usaba el lienzo completo de 128x128,
    pero en pantalla el sprite ocupa una caja distinta —mas chica, corrida— asi
    que comparar celda contra celda no significaba nada: la misma criatura daba
    distancias enormes.

    Ahora los dos lados se recortan a la caja que ocupa el dibujo y se reescalan
    al mismo tamano. La comparacion pasa a ser invariante a escala y posicion,
    que es lo unico que hace falta para reconocerlo en la tarjeta del juego.

    silhouette — forma, GRID x GRID. Igual entre normal y variocolor.
    color      — paleta, CGRID x CGRID x 3. Desempata y separa variocolor.
    ratio      — proporcion ancho/alto de la caja. Discrimina barato y rapido.
    """
    img = Image.open(path).convert("RGBA")
    a = np.asarray(img, dtype=np.float32) / 255.0
    alpha = a[..., 3]

    ys, xs = np.where(alpha > 0.35)
    if len(xs) < 8:
        raise ValueError("sprite vacio")
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1

    box = img.crop((x0, y0, x1, y1))
    ratio = (x1 - x0) / max(1, (y1 - y0))

    sil_img = box.resize((GRID, GRID), Image.BILINEAR)
    sa = np.asarray(sil_img, dtype=np.float32)[..., 3] / 255.0

    col_img = box.resize((CGRID, CGRID), Image.BILINEAR)
    ca = np.asarray(col_img, dtype=np.float32) / 255.0
    ca_alpha = ca[..., 3:4]
    rgb = np.divide(ca[..., :3] * ca_alpha, np.maximum(ca_alpha, 1e-3))

    return (
        [int(round(v * 100)) for v in sa.flatten().tolist()],
        [int(round(v * 100)) for v in rgb.flatten().tolist()],
        round(float(ratio), 3),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-shiny", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)

    # La version anterior guardaba nombres corruptos («0003-mega-shiny-shiny»,
    # formas con « shiny» adentro). Se borran para que no queden como basura ni
    # ensucien el indice; los buenos se vuelven a bajar en esta misma corrida.
    basura = [f for f in OUT_DIR.glob("*.png")
              if "-shiny-shiny" in f.name or "-shiny-" in f.name]
    if basura:
        print(f"Limpiando {len(basura)} sprites con nombre corrupto de la versión anterior.")
        for f in basura:
            f.unlink(missing_ok=True)

    sess = make_session(args.workers)

    jobs = []
    for kind, cat in CATS:
        if kind == "shiny" and args.no_shiny:
            continue
        print(f"Listando «{cat}» ...", end=" ", flush=True)
        try:
            files = list_category(sess, cat)
        except Exception as e:
            print(f"falló ({e}). Sigo sin esta categoría.")
            continue
        print(f"{len(files)} archivos")
        malos = []
        for title, url in files:
            pr = parse(title, kind == "shiny")
            if pr:
                dex, form, slug, shiny = pr
                jobs.append((slug, dex, form, shiny, url))
            else:
                malos.append(title.split(":", 1)[-1])
        # Antes esto se perdia en silencio y el script decia "Listo" igual.
        if malos:
            print(f"  ATENCION: {len(malos)} nombres no reconocidos, "
                  f"por ejemplo: {', '.join(malos[:3])}")

    if not jobs:
        print("No hay nada para descargar.", file=sys.stderr)
        sys.exit(1)

    seen, uniq = set(), []
    for j in jobs:
        if j[0] not in seen:
            seen.add(j[0]); uniq.append(j)
    jobs = uniq

    ya = sum(1 for j in jobs if valid_png(OUT_DIR / f"{j[0]}.png"))
    print(f"\n{len(jobs)} sprites en total; {ya} ya estaban descargados.")
    if ya == len(jobs):
        print("No hay nada que bajar: solo recalculo las huellas.\n")
    else:
        print(f"Descargando con {args.workers} hilos ...\n")

    t0 = time.time()
    done = [0]
    failed = []

    def work(job):
        slug, dex, form, shiny, url = job
        try:
            download(sess, url, OUT_DIR / f"{slug}.png")
        except Exception as e:
            return ("fail", job, str(e))
        with _lock:
            done[0] += 1
            n = done[0]
            if n % 25 == 0 or n == len(jobs):
                el = time.time() - t0
                rate = n / max(el, .001)
                eta = (len(jobs) - n) / max(rate, .001)
                print(f"  {n}/{len(jobs)}   {rate:5.1f}/s   faltan ~{eta:4.0f}s")
        return ("ok", job, None)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(work, j) for j in jobs]):
            st, job, info = fut.result()
            if st == "fail":
                failed.append((job, info))

    if failed:
        print(f"\nSegunda vuelta para {len(failed)} que fallaron ...")
        rec, still = 0, []
        for job, _ in failed:
            try:
                download(sess, job[4], OUT_DIR / f"{job[0]}.png", tries=5)
                rec += 1
            except Exception as e:
                still.append((job, str(e)))
        print(f"  recuperados {rec}, siguen fallando {len(still)}")
        failed = still

    print("\nCalculando huellas ...")
    entries = []
    ok_jobs = [j for j in jobs if valid_png(OUT_DIR / f"{j[0]}.png")]
    for i, (slug, dex, form, shiny, _) in enumerate(ok_jobs, 1):
        try:
            sil, col, ratio = fingerprint(OUT_DIR / f"{slug}.png")
        except Exception as e:
            print(f"  huella falló en {slug}: {e}")
            continue
        entries.append({"slug": slug, "dex": dex, "form": form, "shiny": shiny,
                        "sil": sil, "col": col, "ratio": ratio})
        if i % 150 == 0:
            print(f"  {i}/{len(ok_jobs)}")

    INDEX.write_text(json.dumps(
        {"v": 2, "grid": GRID, "cgrid": CGRID, "count": len(entries),
         "sprites": entries},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    el = time.time() - t0
    n_sh = sum(1 for e in entries if e["shiny"])
    n_no = len(entries) - n_sh
    print(f"\nListo en {el:.0f}s: {len(entries)} sprites "
          f"({n_no} normales, {n_sh} variocolor)")
    # Aviso claro si faltan: normales y variocolor deberian ser casi iguales.
    if not args.no_shiny and n_sh < n_no * 0.9:
        print(f"  ATENCION: hay {n_no} normales pero solo {n_sh} variocolor. "
              f"Faltan {n_no - n_sh}. Volvé a correr el script.")
    print(f"{INDEX} → {INDEX.stat().st_size // 1024} KB")
    if failed:
        print(f"\nNo se pudieron bajar {len(failed)}: "
              f"{', '.join(j[0][0] for j in failed[:6])}")
        print("Volvé a correr el script; retoma solo los que faltan.")
    print("\nCopiá sprite_index.json a app/src/main/assets/")


if __name__ == "__main__":
    main()
