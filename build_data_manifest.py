#!/usr/bin/env python3
"""
build_data_manifest.py — Champions HUD, publicación de datos por internet

Arma la carpeta que se sube a cualquier hosting estático (GitHub Pages, un
bucket, un CDN) para que las apps ya instaladas se actualicen solas, sin APK
nuevo.

POR QUÉ UN MANIFIESTO Y NO SOLO LOS ARCHIVOS
--------------------------------------------
Los tres archivos pesan ~1.7 MB juntos, y el que más cambia (`meta.json`, 279
KB) es el más chico. Bajarlos todos cada semana sería gastar 6 veces más datos
del usuario de lo necesario. El manifiesto pesa menos de 1 KB y dice qué
cambió: la app lo baja, compara, y descarga **solo lo que hace falta**.

Con miles de usuarios eso deja de ser un detalle: es la diferencia entre
servir gigabytes por semana o unos pocos megas.

QUÉ GARANTIZA
-------------
  · `sha256` por archivo — una descarga cortada a la mitad es JSON inválido y
    se detecta igual, pero una corrupta y *parseable* no. El hash cierra ese
    hueco antes de que un dex roto llegue a pisar el que funciona.
  · `bytes` — permite avisar "son 500 KB" antes de bajar con datos móviles.
  · `schema` por archivo — si algún día el formato cambia de forma
    incompatible (ver architecture.md §10.2), una app vieja puede negarse a
    instalarlo en vez de leerlo a medias.
  · `minAppVersion` — el freno de mano. Si un archivo nuevo necesita código
    que las apps viejas no tienen, se marca acá y esas apps lo ignoran.

Uso:
    python update_data.py meta          # primero generá los datos
    python build_data_manifest.py       # después empaquetá para publicar
    # subir todo el contenido de dist/ a la raíz de la URL pública

El resultado queda en `dist/`:
    dist/manifest.json
    dist/meta.json
    dist/dex.json
    dist/sprite_index.json
"""

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).parent
ASSETS = ROOT / "app/src/main/assets"
DIST = ROOT / "dist"

MANIFEST_SCHEMA = 1

# Versión mínima de la app que puede consumir estos archivos. Se sube a mano y
# solo cuando un cambio de datos DEPENDE de código nuevo — no en cada corrida.
MIN_APP_VERSION = 1

ARCHIVOS = ["meta.json", "dex.json", "sprite_index.json"]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def version_de(nombre, data):
    """
    La 'versión' de un archivo de datos es su fecha de contenido.

    Cada generador la escribe con su propio nombre, así que se busca en orden.
    Si no hay ninguna, se cae al hash — nunca se inventa una fecha, y nunca se
    devuelve vacío: sin versión no hay forma de comparar y la app bajaría todo
    siempre.
    """
    for campo in ("updated", "generatedAtV2", "generatedAt"):
        v = data.get(campo)
        if v:
            return str(v)[:10]
    return None


def describir(nombre, path):
    data = json.loads(path.read_text(encoding="utf-8"))
    ver = version_de(nombre, data)
    h = sha256(path)
    if ver is None:
        # sprite_index.json no lleva fecha: su "versión" es su contenido.
        ver = h[:12]
    return {
        "version": ver,
        "bytes": path.stat().st_size,
        "sha256": h,
        # meta.json usa `schema`; dex.json y sprite_index.json usan `v`.
        "schema": data.get("schema", data.get("v", 1)),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", default=str(DIST), help=f"carpeta destino (default: {DIST})")
    ap.add_argument("--base-url", default="",
                    help="URL pública donde va a vivir esto, solo informativa "
                         "(la app resuelve las rutas relativas al manifiesto)")
    a = ap.parse_args()

    dist = Path(a.salida)
    faltan = [n for n in ARCHIVOS if not (ASSETS / n).exists()]
    if faltan:
        print(f"Faltan archivos en {ASSETS}: {', '.join(faltan)}\n"
              f"Corré `python update_data.py completo` primero.", file=sys.stderr)
        return 1

    dist.mkdir(parents=True, exist_ok=True)
    files = {}
    print("Empaquetando para publicar:\n")
    for nombre in ARCHIVOS:
        src = ASSETS / nombre
        shutil.copy2(src, dist / nombre)
        info = describir(nombre, src)
        files[nombre] = info
        print(f"  {nombre:20} v{info['version']:12} {info['bytes'] // 1024:5} KB  "
              f"sha256 {info['sha256'][:12]}…")

    manifest = {
        "manifestSchema": MANIFEST_SCHEMA,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minAppVersion": MIN_APP_VERSION,
        "files": files,
    }
    if a.base_url:
        manifest["baseUrl"] = a.base_url.rstrip("/")

    (dist / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(f["bytes"] for f in files.values())
    print(f"\n  manifest.json        {(dist / 'manifest.json').stat().st_size} bytes")
    print(f"\nListo en {dist}/ — {total // 1024} KB en total.")
    print("Subí el contenido de esa carpeta a la URL pública.")
    print("La app baja manifest.json (menos de 1 KB) y descarga solo lo que cambió.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
