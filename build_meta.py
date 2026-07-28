#!/usr/bin/env python3
"""
build_meta.py — actualiza los datos del meta que usa el HUD.

El meta de Champions cambia regulacion a regulacion, asi que meta.json esta
pensado para reemplazarse sin tocar la app. Este script arma el archivo con la
forma que el HUD espera; de donde salen los numeros lo decidis vos abajo.

Uso:
    python build_meta.py --regulation M-B --out meta.json
    # despues: copiar meta.json a app/src/main/assets/  (o servirlo por HTTP
    #          y pegar la URL en el HUD, pestaña ⚙)

IMPORTANTE: no incluye scraping de ningun sitio. Pikalytics y compania tienen
terminos propios y su HTML cambia seguido; meter un scraper fragil aca solo
sirve para que te de datos mal sin avisar. Implementa fetch_usage() contra la
fuente que uses (una exportacion, una API publica, o carga manual) y el resto
del pipeline ya funciona.
"""

import argparse, json, sys
from datetime import date

SCHEMA = """
species: { "<dex>": {
    usage:     float,                       # % de uso en el formato
    items:     [[nombre, %], ...],          # ordenados de mayor a menor
    moves:     [[nombre, %], ...],
    abilities: [[nombre, %], ...],
    spreads:   [{label, sp:[hp,atk,def,spa,spd,spe], nat, pct}, ...]
}}
Los nombres de movimientos y objetos tienen que coincidir EXACTO con los de
hud.html (constante MV y las pastillas de objeto), o el HUD los ignora.
"""


def fetch_usage(regulation: str, fmt: str) -> dict:
    """
    Devolve el dict de especies con la forma de arriba.

    Opciones razonables, de mas a menos solida:
      1. Exportar los datos de la fuente que uses a un CSV/JSON y leerlo aca.
      2. Usar una API publica si la fuente ofrece una.
      3. Cargar a mano las 20-30 especies del meta que de verdad te cruzas.

    Mientras devuelva {}, el script conserva lo que ya haya en el archivo de
    salida en vez de dejarte sin datos.
    """
    return {}


def main():
    ap = argparse.ArgumentParser(description="Genera meta.json para Champions HUD")
    ap.add_argument("--regulation", default="M-B")
    ap.add_argument("--format", default="doubles", choices=["doubles", "singles"])
    ap.add_argument("--out", default="meta.json")
    ap.add_argument("--schema", action="store_true", help="mostrar el formato esperado")
    a = ap.parse_args()

    if a.schema:
        print(SCHEMA); return

    species = fetch_usage(a.regulation, a.format)

    if not species:
        print("fetch_usage() todavia no devuelve nada.", file=sys.stderr)
        print("Implementala y volve a correr. Formato esperado:", file=sys.stderr)
        print(SCHEMA, file=sys.stderr)
        try:
            prev = json.load(open(a.out, encoding="utf-8"))
            print(f"\n{a.out} existente conservado ({len(prev.get('species', {}))} especies).",
                  file=sys.stderr)
        except Exception:
            pass
        sys.exit(1)

    out = {
        "regulation": a.regulation,
        "format": a.format,
        "updated": date.today().isoformat(),
        "source": "importado",
        "species": species,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"{a.out}: {len(species)} especies, regulacion {a.regulation}")


if __name__ == "__main__":
    main()
