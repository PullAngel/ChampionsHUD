#!/usr/bin/env python3
"""
update_data.py — Champions HUD, actualización de datos en un solo comando

Los cuatro generadores (build_sprite_index / build_dex / build_meta /
build_meta_v2) ya existían y funcionaban, pero se corrían a mano, en orden,
recordando cuál dependía de cuál y copiando archivos a assets/ con `cp`. Este
script es ese proceso, escrito una vez, para no volver a reconstruirlo de
memoria cada vez que cambia el meta.

TRES NIVELES, por frecuencia real de cambio
-------------------------------------------
    python update_data.py meta      # semanal — el meta de torneos cambia solo
    python update_data.py dex       # parche del juego: nerfeos/bufeos/stats
    python update_data.py completo  # Pokémon u objetos NUEVOS en Champions

Cada nivel corre todo lo que está río abajo de él, porque las dependencias son
reales, no una convención:

    sprites  →  dex  →  meta  →  meta+CBD
    (qué especies    (stats,   (uso real  (repartos y
     existen)        movs,      de         naturalezas
                     learnsets) torneo)    reales)

  · `completo` arranca en sprites. Es el único que descubre especies nuevas:
    sprite_index.json es la fuente de verdad de qué existe en Champions
    (sale de la categoría de sprites del propio juego, no de una lista a
    mano). Tarda varios minutos; por eso no se corre siempre.
  · `dex` salta sprites. Sirve cuando el juego cambia stats, movimientos o
    habilidades de Pokémon que YA existen — el caso de un parche de balance.
  · `meta` salta los dos primeros. Es el semanal.

SEGURIDAD: STAGING → VALIDAR → PROMOVER
---------------------------------------
Nada pisa `app/src/main/assets/` hasta que `validate_data.py` da OK sobre los
archivos recién generados. Se generan en `_staging/`, se validan ahí (con
`--datos`), y solo entonces se promueven. Si la validación falla, lo instalado
sigue intacto y el proceso termina con código 1 diciendo qué pasó.

Esto no es celo de más: la app corre offline y confía en que estos archivos
son mutuamente consistentes. Un meta.json que nombre un movimiento que el
dex no conoce no rompe con una excepción — degrada en silencio, que es
justo el patrón de bug que `docs/audit.md` §8 identifica como el recurrente
de este proyecto.

Uso:
    pip install -r requirements.txt
    python update_data.py meta
    python update_data.py meta --dry-run     # muestra qué haría, sin tocar red
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# La consola de Windows abre en cp1252 y revienta (o imprime basura) con
# acentos y comillas angulares. Esto es una herramienta de línea de comandos
# en español: que el texto se lea bien no es cosmético, es la diferencia
# entre un mensaje de error útil y uno ilegible.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).parent
ASSETS = ROOT / "app/src/main/assets"
STAGING = ROOT / "_staging"

# Los tres archivos de datos que la app consume. `origen` es dónde los deja su
# generador (todos escriben en la raíz del repo, comportamiento que no se
# cambia para no romper su uso suelto).
ARCHIVOS = ["sprite_index.json", "dex.json", "meta.json"]

NIVELES = {
    "completo": ["sprites", "dex", "meta", "meta_cbd"],
    "dex":      ["dex", "meta", "meta_cbd"],
    "meta":     ["meta", "meta_cbd"],
}

PASOS = {
    "sprites":  ("build_sprite_index.py", "sprite_index.json",
                 "índice de sprites (qué especies existen en Champions)"),
    "dex":      ("build_dex.py", "dex.json",
                 "dex completo (stats, movimientos, learnsets)"),
    "meta":     ("build_meta.py", "meta.json",
                 "meta real de torneos (Limitless)"),
    "meta_cbd": ("build_meta_v2.py", "meta_v2.json",
                 "cruce con Champions Battle Data (repartos y naturalezas)"),
}


def log(msg=""):
    print(msg, flush=True)


def titulo(msg):
    log(f"\n{'=' * 62}\n{msg}\n{'=' * 62}")


def correr(script, args, dry):
    """Corre un generador. Devuelve True si salió bien."""
    cmd = [sys.executable, script, *args]
    log(f"\n$ {' '.join(cmd)}")
    if dry:
        log("  (dry-run: no se ejecuta)")
        return True
    t0 = time.time()
    # Cinturón y tirantes sobre lo mismo que ya arregla build_meta.py por su
    # cuenta: los generadores imprimen texto que viene de internet (nombres de
    # torneo con emojis, especies con acentos) y la consola de Windows abre en
    # cp1252. Un solo carácter fuera de esa tabla abortaba la corrida entera.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8:replace"}
    r = subprocess.run(cmd, cwd=ROOT, env=env)
    if r.returncode != 0:
        log(f"\n  FALLÓ {script} (código {r.returncode}).")
        return False
    log(f"  ok, {time.time() - t0:.0f}s")
    return True


def preparar_staging(dry):
    """
    Copia lo instalado a staging como punto de partida.

    Sin esto, un nivel que no regenera los tres archivos (`meta`, por ejemplo)
    dejaría staging incompleto y la validación fallaría por archivos que en
    realidad están bien — reportando un problema inventado.
    """
    if dry:
        return True
    STAGING.mkdir(exist_ok=True)
    for nombre in ARCHIVOS:
        inst = ASSETS / nombre
        if inst.exists():
            shutil.copy2(inst, STAGING / nombre)
        else:
            log(f"  ! {nombre} no está instalado todavía; se espera que este nivel lo genere.")
    return True


def recoger(salida, destino_nombre, dry):
    """Mueve la salida de un generador (raíz del repo) a staging."""
    if dry:
        return True
    origen = ROOT / salida
    if not origen.exists():
        log(f"\n  FALLÓ: {salida} no se generó.")
        return False
    shutil.copy2(origen, STAGING / destino_nombre)
    kb = origen.stat().st_size // 1024
    log(f"  → staging/{destino_nombre} ({kb} KB)")
    return True


def validar(dry):
    titulo("Validando lo generado (antes de tocar nada instalado)")
    if dry:
        log("  (dry-run: no se valida)")
        return True
    r = subprocess.run([sys.executable, "validate_data.py", "--datos", str(STAGING)],
                       cwd=ROOT)
    return r.returncode == 0


def promover(dry):
    titulo("Promoviendo a app/src/main/assets/")
    if dry:
        log("  (dry-run: no se promueve)")
        return
    ASSETS.mkdir(parents=True, exist_ok=True)
    for nombre in ARCHIVOS:
        src = STAGING / nombre
        if not src.exists():
            continue
        shutil.copy2(src, ASSETS / nombre)
        log(f"  {nombre} → assets/ ({src.stat().st_size // 1024} KB)")
    # sprite_index.json vive también en la raíz: es la entrada de build_dex.py
    # y de validate_data.py cuando se corre sin --datos.
    shutil.copy2(STAGING / "sprite_index.json", ROOT / "sprite_index.json")


def resumen():
    """Qué quedó instalado, en una línea por archivo."""
    titulo("Instalado")
    meta = json.loads((ASSETS / "meta.json").read_text(encoding="utf-8"))
    dex = json.loads((ASSETS / "dex.json").read_text(encoding="utf-8"))
    idx = json.loads((ASSETS / "sprite_index.json").read_text(encoding="utf-8"))
    log(f"  sprite_index : {idx.get('count', 0)} sprites")
    log(f"  dex          : {len(dex.get('species', {}))} especies, "
        f"{len(dex.get('moves', {}))} movimientos")
    log(f"  meta         : {len(meta.get('species', {}))} especies, "
        f"regulación {meta.get('regulation', '?')}, "
        f"actualizado {meta.get('updated', '?')}"
        + ("  [PARCIAL]" if meta.get("partial") else ""))


def main():
    ap = argparse.ArgumentParser(
        description="Actualiza los datos de Champions HUD en un solo comando.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Niveles:\n"
               "  meta      semanal — solo el meta de torneos\n"
               "  dex       parche de balance — stats/movimientos/habilidades\n"
               "  completo  Pokémon u objetos nuevos — regenera todo\n")
    ap.add_argument("nivel", choices=list(NIVELES))
    ap.add_argument("--regulacion", default="M-B",
                    help="regulación de Limitless a bajar (default: M-B)")
    ap.add_argument("--torneos", type=int, default=40,
                    help="cuántos torneos recientes procesar (default: 40)")
    ap.add_argument("--dry-run", action="store_true",
                    help="muestra los pasos sin ejecutar nada ni tocar la red")
    a = ap.parse_args()

    pasos = NIVELES[a.nivel]
    titulo(f"Nivel «{a.nivel}» — {len(pasos)} paso(s)")
    for i, p in enumerate(pasos, 1):
        log(f"  {i}. {PASOS[p][2]}")
    if a.nivel != "completo":
        log(f"\n  (se saltan los pasos previos: se reusa lo ya instalado)")

    preparar_staging(a.dry_run)

    for p in pasos:
        script, salida, desc = PASOS[p]
        titulo(desc)
        args = []
        if p == "meta":
            args = ["--regulation", a.regulacion, "--limit", str(a.torneos),
                    "--dex", str(STAGING / "dex.json")]
        elif p == "meta_cbd":
            # Sobre el meta y el dex de STAGING, no sobre lo instalado: si
            # leyera assets/ cruzaría CBD contra el meta de la corrida
            # anterior, en silencio y con pinta de haber funcionado.
            args = ["--base", str(STAGING / "meta.json"),
                    "--dex", str(STAGING / "dex.json")]
        if not correr(script, args, a.dry_run):
            log("\nNo se instaló nada. Lo que ya estaba sigue intacto.")
            return 1
        # build_meta_v2 lee el meta.json de assets como base y escribe
        # meta_v2.json — su salida es la que termina siendo meta.json.
        destino = "meta.json" if p == "meta_cbd" else salida
        if not recoger(salida, destino, a.dry_run):
            log("\nNo se instaló nada. Lo que ya estaba sigue intacto.")
            return 1

    if not validar(a.dry_run):
        log("\nLA VALIDACIÓN FALLÓ. No se instaló nada — lo que ya estaba sigue intacto.")
        log(f"Los archivos generados quedaron en {STAGING}/ para poder mirarlos.")
        return 1

    promover(a.dry_run)
    if not a.dry_run:
        resumen()
        log("\nListo. Recompilá la app para que tome los datos nuevos,")
        log("o publicalos para actualización por internet (ver build_data_manifest.py).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
