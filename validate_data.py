#!/usr/bin/env python3
"""
validate_data.py — Champions HUD

Verifica que meta.json, dex.json, sprite_index.json y las tablas canónicas
embebidas en hud.html (IT, ABIL_I18N, MV, MEGA) son mutuamente consistentes.
Es la respuesta directa a que varios de los hallazgos más graves de la
auditoría (meta.json desincronizado, habilidades inexistentes para una
especie) no se detectaron hasta que alguien leyó el código línea por línea
(ver docs/audit.md, docs/architecture.md §6).

No descarga nada ni modifica ningún archivo — solo lee y reporta. Termina
con código de salida 1 si encuentra algún problema, para poder engancharse
a un paso de build o a CI.

Uso:
    python validate_data.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
HUD = ROOT / "app/src/main/assets/hud.html"
DEX = ROOT / "app/src/main/assets/dex.json"
META = ROOT / "app/src/main/assets/meta.json"
SPRITE_INDEX = ROOT / "sprite_index.json"

errors = []
warnings = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def load_json(path, label):
    if not path.exists():
        err(f"{label}: no existe ({path})")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        err(f"{label}: JSON inválido — {e}")
        return None


def slug(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def extract_tables(html):
    """Tablas canónicas embebidas en hud.html, parseadas con regex — no hay
    forma de import-earlas como módulo real todavía (ver roadmap Fase 0 §4)."""
    tables = {}

    it_m = re.search(r"const IT=\[(.*?)\];", html, re.S)
    tables["items"] = set(re.findall(r'\["([^"]+)","[^"]*","[a-z]+"\]', it_m.group(1))) if it_m else set()

    mega_m = re.search(r"const MEGA=\{(.*?)\};", html, re.S)
    tables["mega_items"] = set(re.findall(r'"([^"]+)":\[', mega_m.group(1))) if mega_m else set()

    mv_m = re.search(r"const MV=\{(.*?)\};", html, re.S)
    tables["moves"] = set(re.findall(r'"([^"]+)":\[', mv_m.group(1))) if mv_m else set()

    es_alt_m = re.search(r"const ES_ALT=\{(.*?)\};", html)
    tables["move_es_alt_keys"] = set(re.findall(r'"([^"]+)":', es_alt_m.group(1))) if es_alt_m else set()

    abil_i18n_m = re.search(r"const ABIL_I18N=\{(.*?)\n\};", html, re.S)
    tables["abilities"] = set(re.findall(r"(\w+):\{en:", abil_i18n_m.group(1))) if abil_i18n_m else set()

    return tables


def check_meta_vs_canonical(meta, tables, dex):
    if meta is None:
        return
    valid_items = tables["items"] | tables["mega_items"]
    valid_moves = tables["moves"] | tables["move_es_alt_keys"]
    dex_moves = set(m["n"] for m in dex["moves"].values()) if dex else set()
    valid_moves |= dex_moves
    valid_abilities = tables["abilities"]

    legal_nums = set(s["dex"] for s in load_json(SPRITE_INDEX, "sprite_index.json").get("sprites", [])) \
        if SPRITE_INDEX.exists() else set()

    for dexnum, entry in meta.get("species", {}).items():
        if legal_nums and int(dexnum) not in legal_nums:
            err(f"meta.json: especie {dexnum} no está en sprite_index.json (no es legal hoy)")
        for name, pct in entry.get("items", []):
            if name not in valid_items:
                err(f"meta.json[{dexnum}]: ítem \"{name}\" no existe en la tabla IT ni en MEGA")
        for name, pct in entry.get("moves", []):
            if name not in valid_moves:
                err(f"meta.json[{dexnum}]: movimiento \"{name}\" no resuelve contra MV, ES_ALT ni dex.json")
        for name, pct in entry.get("abilities", []):
            if name not in valid_abilities:
                err(f"meta.json[{dexnum}]: habilidad \"{name}\" no es un slug de ABIL_I18N")
        for s in entry.get("sets", []):
            for name in s.get("moves", []):
                if name not in valid_moves:
                    err(f"meta.json[{dexnum}]: set con movimiento \"{name}\" que no resuelve contra MV, ES_ALT ni dex.json")


def check_dex_format(dex):
    if dex is None:
        return
    if dex.get("v") != 1:
        warn(f"dex.json: versión de formato inesperada ({dex.get('v')}), el código espera v=1")
    if not dex.get("species") or not dex.get("moves") or not dex.get("learnsets"):
        err("dex.json: faltan claves species/moves/learnsets")


def check_sprite_index_format(idx):
    if idx is None:
        return
    if idx.get("v", 1) < 2:
        err("sprite_index.json: versión de índice vieja (v<2) — SpriteMatcher.kt la rechaza explícitamente")


def check_species_abilities_vs_dex(dex):
    """Cruza SPD/ABIL embebidas en hud.html contra dex.json: detecta el tipo de
    error que motivó regenerar ABIL en esta sesión (ej. Gengar con Levitación,
    retirada desde la gen 8)."""
    if dex is None:
        return
    html = HUD.read_text(encoding="utf-8")
    abil_m = re.search(r"const ABIL=\{(.*?)\n\};", html, re.S)
    if not abil_m:
        warn("hud.html: no se encontró la tabla ABIL embebida para cruzar contra dex.json")
        return
    entries = re.findall(r"(\d+):\[(.*?)\]", abil_m.group(1))

    by_num = {}
    for key, sp in dex["species"].items():
        if "base" in sp:
            continue
        by_num.setdefault(sp["num"], (key, sp))

    for num_s, arr_s in entries:
        num = int(num_s)
        slugs = re.findall(r'"([^"]+)"', arr_s)
        real = by_num.get(num)
        if not real:
            continue  # especie no legal hoy — no es un error de este validador
        _, sp = real
        real_slugs = set(slug(a) for a in sp["a"])
        for s in slugs:
            if s not in real_slugs:
                err(f"hud.html ABIL[{num}] ({sp['n']}): \"{s}\" no es una habilidad real de esta especie según dex.json (reales: {sorted(real_slugs)})")


def main():
    print("Validando datos de Champions HUD...\n")
    html = HUD.read_text(encoding="utf-8") if HUD.exists() else ""
    if not html:
        err(f"hud.html: no existe ({HUD})")

    dex = load_json(DEX, "dex.json")
    meta = load_json(META, "meta.json")
    sprite_idx = load_json(SPRITE_INDEX, "sprite_index.json")

    if html:
        tables = extract_tables(html)
        check_meta_vs_canonical(meta, tables, dex)
        check_species_abilities_vs_dex(dex)

    check_dex_format(dex)
    check_sprite_index_format(sprite_idx)

    if warnings:
        print(f"{len(warnings)} advertencia(s):")
        for w in warnings:
            print(f"  ! {w}")
        print()

    if errors:
        print(f"{len(errors)} error(es):")
        for e in errors:
            print(f"  x {e}")
        print(f"\nFALLÓ: {len(errors)} inconsistencia(s) encontrada(s).")
        return 1

    print("OK: no se encontraron inconsistencias.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
