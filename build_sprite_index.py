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
    pip install -r requirements.txt
    python build_sprite_index.py                 # normales + variocolor
    python build_sprite_index.py --no-shiny      # solo normales
    python build_sprite_index.py --workers 12    # mas agresivo

    # Sin red, desde los PNG ya descargados (fondo de red — ver PROVEEDORES):
    python build_sprite_index.py --fuente carpeta
    python build_sprite_index.py --fuente carpeta --carpeta /ruta/a/los/png

Normalmente no se corre a mano: `python update_data.py completo` lo encadena
con el resto del pipeline y valida antes de instalar nada.

Licencia de los sprites: CC BY-NC-SA 2.5 (Bulbagarden). Uso no comercial.
"""

import argparse
import json
import re
import sys
import time
from collections import namedtuple
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import numpy as np
import requests
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Mismo motivo que en build_meta.py: la consola de Windows abre en cp1252 y un
# solo carácter fuera de esa tabla (una flecha «→» del resumen, un nombre de
# archivo con acento) tira UnicodeEncodeError. Acá reventaba DESPUÉS de haber
# escrito el índice, así que el script "fallaba" con el trabajo ya hecho.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

API = "https://archives.bulbagarden.net/w/api.php"
CATS = [
    ("normal", "Category:Champions menu sprites"),
    ("shiny", "Category:Champions Shiny menu sprites"),
]
UA = "ChampionsHUD/0.4 (proyecto personal no comercial)"

# ─────────────────────────────────────────────────────────────────────────────
# PROVEEDORES DE SPRITES — el plan de contingencia
#
# Bulbagarden es una wiki de la comunidad: puede cambiar la convención de
# nombres de archivo, renombrar las categorías, o directamente dejar de
# publicar los sprites de Champions. Que eso pase no debería obligar a
# reescribir este script.
#
# Por eso la parte que sabe DE DÓNDE salen las imágenes está separada de la
# que sabe QUÉ HACER con ellas. Un proveedor tiene un solo trabajo:
#
#     listar() -> [Sprite(slug, dex, form, shiny, origen), ...]
#
# donde `origen` es una URL http(s) o una ruta local. Todo lo de abajo —
# descarga con reintentos, validación del PNG, huella de forma/color/
# proporción, y el formato de sprite_index.json v2 que lee SpriteMatcher.kt —
# es agnóstico de la fuente y NO se toca al cambiarla.
#
# CAMBIAR DE FUENTE = ESCRIBIR UNA FUNCIÓN. Nada más. El contrato de salida
# (sprite_index.json v2) queda idéntico, así que la app ni se entera.
#
# `carpeta` ya es el fondo de red garantizado: si mañana no hay NINGUNA fuente
# web disponible, se juntan los PNG como sea (extraídos del juego, de un
# respaldo, a mano) en una carpeta con el nombre `NNNN[-forma][-shiny].png` y
# el índice se reconstruye igual. Nunca se depende de que un sitio siga vivo.
# ─────────────────────────────────────────────────────────────────────────────

Sprite = namedtuple("Sprite", "slug dex form shiny origen")


def proveedor_bulbagarden(sess, incluir_shiny):
    """Fuente por defecto: categorías de Champions en Bulbagarden Archives."""
    out, malos = [], []
    for kind, cat in CATS:
        if kind == "shiny" and not incluir_shiny:
            continue
        print(f"Listando «{cat}» ...", end=" ", flush=True)
        try:
            files = list_category(sess, cat)
        except Exception as e:
            print(f"falló ({e}). Sigo sin esta categoría.")
            continue
        print(f"{len(files)} archivos")
        for title, url in files:
            pr = parse(title, kind == "shiny")
            if pr:
                dex, form, slug, shiny = pr
                out.append(Sprite(slug, dex, form, shiny, url))
            else:
                malos.append(title.split(":", 1)[-1])
    # Antes esto se perdia en silencio y el script decia "Listo" igual.
    if malos:
        print(f"  ATENCION: {len(malos)} nombres no reconocidos, "
              f"por ejemplo: {', '.join(malos[:3])}")
    return out


# Nombre de archivo del fondo de red: `0003.png`, `0128-paldea-aqua.png`,
# `0003-shiny.png`. Es EXACTAMENTE el `slug` que este script ya venía usando
# para guardar en sprites/, así que la carpeta que el proveedor de
# Bulbagarden deja como caché sirve tal cual como entrada de este otro.
#
# El sufijo -shiny se saca ANTES de mirar la forma, en dos pasos, en vez de en
# un solo regex con dos grupos opcionales. Con un regex, `0003-shiny.png` se
# leía como «forma shiny, no variocolor»: el grupo de forma es no-codicioso
# pero igual se come "shiny" cuando no hay nada más que capturar. Medido: 567
# "normales" y 151 variocolor, cuando la división real es ~359/359.
# Es la TERCERA vez que este archivo tropieza con lo mismo — el comentario de
# NAME_RE, más arriba, documenta las dos anteriores. Dos pasos no tienen esa
# ambigüedad y no hay que razonarlos.
SUF_SHINY = "-shiny"
CARPETA_RE = re.compile(r"^(\d{4})(?:-(.+))?$", re.I)


def parse_nombre_carpeta(stem):
    """`0128-paldea-aqua-shiny` -> (128, 'paldea aqua', True). None si no cuadra."""
    shiny = stem.lower().endswith(SUF_SHINY)
    base = stem[:-len(SUF_SHINY)] if shiny else stem
    m = CARPETA_RE.match(base)
    if not m:
        return None
    return int(m.group(1)), (m.group(2) or "").replace("-", " ").strip(), shiny


def proveedor_carpeta(carpeta, incluir_shiny):
    """
    Fondo de red: PNGs ya descargados en una carpeta local.

    No depende de ningún sitio web. Sirve para regenerar el índice sin red,
    y como salida de emergencia si la fuente online desaparece.
    """
    d = Path(carpeta)
    if not d.is_dir():
        print(f"No existe la carpeta {d}", file=sys.stderr)
        sys.exit(1)
    out, malos = [], []
    for f in sorted(d.glob("*.png")):
        pr = parse_nombre_carpeta(f.stem)
        if not pr:
            malos.append(f.name)
            continue
        dex, form, shiny = pr
        if shiny and not incluir_shiny:
            continue
        out.append(Sprite(f.stem, dex, form, shiny, f))
    print(f"Carpeta {d}: {len(out)} sprites reconocidos.")
    if malos:
        print(f"  ATENCION: {len(malos)} nombres no reconocidos, "
              f"por ejemplo: {', '.join(malos[:3])}. "
              f"El formato esperado es NNNN[-forma][-shiny].png")
    return out


PROVEEDORES = {"bulbagarden": proveedor_bulbagarden, "carpeta": proveedor_carpeta}


def es_remoto(sp):
    """¿Hay que descargarlo, o el archivo ya está en disco?"""
    return isinstance(sp.origen, str) and sp.origen.startswith(("http://", "https://"))


def ruta_de(sp):
    """Dónde vive (o va a vivir) el PNG de este sprite."""
    return OUT_DIR / f"{sp.slug}.png" if es_remoto(sp) else Path(sp.origen)

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
    # Minúsculas a propósito: es la única forma que el proveedor «carpeta»
    # puede recuperar (el slug del archivo ya viene en minúsculas), así que
    # normalizar acá es lo que hace que las dos fuentes produzcan un índice
    # IDÉNTICO. Sin esto, cambiar de fuente cambiaba 302 entradas por puras
    # mayúsculas. El campo es informativo — el motor nunca lo compara
    # (`onScan` solo lee dex/confidence/shiny) — pero un artefacto que cambia
    # según de dónde salió no sirve para comparar ni para diagnosticar.
    form = (m.group(2) or "").replace("_", " ").strip().lower()
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
    ap.add_argument("--fuente", choices=list(PROVEEDORES), default="bulbagarden",
                    help="de dónde salen las imágenes (default: bulbagarden). "
                         "«carpeta» las toma de un directorio local, sin red.")
    ap.add_argument("--carpeta", default=str(OUT_DIR),
                    help="con --fuente carpeta: dónde están los PNG "
                         f"(default: {OUT_DIR}/, la caché de descargas)")
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

    # Único punto que sabe de dónde salen las imágenes. Cambiar de fuente es
    # escribir otra función acá arriba y agregarla a PROVEEDORES — nada de lo
    # que sigue (descarga, huella, formato del índice) cambia.
    if args.fuente == "carpeta":
        jobs = proveedor_carpeta(args.carpeta, not args.no_shiny)
    else:
        jobs = proveedor_bulbagarden(sess, not args.no_shiny)

    if not jobs:
        print("La fuente no devolvió ningún sprite.", file=sys.stderr)
        sys.exit(1)

    seen, uniq = set(), []
    for j in jobs:
        if j.slug not in seen:
            seen.add(j.slug); uniq.append(j)
    jobs = uniq

    ya = sum(1 for j in jobs if valid_png(ruta_de(j)))
    print(f"\n{len(jobs)} sprites en total; {ya} ya estaban descargados.")
    if ya == len(jobs):
        print("No hay nada que bajar: solo recalculo las huellas.\n")
    else:
        print(f"Descargando con {args.workers} hilos ...\n")

    t0 = time.time()
    done = [0]
    failed = []

    def work(job):
        try:
            if not es_remoto(job):
                return ("ok", job, None)      # ya es un archivo local
            download(sess, job.origen, ruta_de(job))
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
                download(sess, job.origen, ruta_de(job), tries=5)
                rec += 1
            except Exception as e:
                still.append((job, str(e)))
        print(f"  recuperados {rec}, siguen fallando {len(still)}")
        failed = still

    print("\nCalculando huellas ...")
    entries = []
    ok_jobs = [j for j in jobs if valid_png(ruta_de(j))]
    for i, sp in enumerate(ok_jobs, 1):
        try:
            sil, col, ratio = fingerprint(ruta_de(sp))
        except Exception as e:
            print(f"  huella falló en {sp.slug}: {e}")
            continue
        entries.append({"slug": sp.slug, "dex": sp.dex, "form": sp.form, "shiny": sp.shiny,
                        "sil": sil, "col": col, "ratio": ratio})
        if i % 150 == 0:
            print(f"  {i}/{len(ok_jobs)}")

    # `updated` NO es cosmetico: es con lo que la app compara su copia contra
    # el manifiesto publicado para decidir si hace falta bajar el archivo de
    # nuevo (build_data_manifest.py / DataRepository.version en Storage.kt).
    # Sin este campo la comparacion daba siempre distinto y este archivo, que
    # pesa ~970 KB, se re-descargaba en CADA chequeo aunque no hubiera
    # cambiado — justo lo que el manifiesto existe para evitar.
    ahora = datetime.now(timezone.utc)
    INDEX.write_text(json.dumps(
        {"v": 2, "grid": GRID, "cgrid": CGRID, "count": len(entries),
         "updated": ahora.date().isoformat(),
         "generatedAt": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
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
