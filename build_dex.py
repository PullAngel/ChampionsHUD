#!/usr/bin/env python3
"""
build_dex.py — Champions HUD, datos completos

Descarga los datos de Pokemon Showdown y arma un dex.json compacto con TODO lo
que la app necesita: stats base, tipos, habilidades, movimientos completos y
—lo mas importante— los learnsets, para que cada Pokemon solo ofrezca los
movimientos que de verdad puede aprender.

Que especies entran: las que existen en Champions. Eso no hay que adivinarlo —
sprite_index.json ya lo dice, porque se genero desde la categoria de sprites del
propio juego. Corre build_sprite_index.py primero.

Uso:
    pip install requests
    python build_sprite_index.py      # si todavia no lo corriste
    python build_dex.py
    cp dex.json ChampionsHUD/app/src/main/assets/

Salida tipica: ~400 KB. Datos de Pokemon Showdown (smogon), uso no comercial.
"""

import json
import re
import sys
from pathlib import Path

import requests

BASE = "https://play.pokemonshowdown.com/data"
UA = {"User-Agent": "ChampionsHUD/0.4 (proyecto personal no comercial)"}

SPRITE_INDEX = Path("sprite_index.json")
OUT = Path("dex.json")

# Categorias que el HUD entiende. El resto de los movimientos de estado entran
# igual, pero sin efecto modelado en el calculo.
TARGET_MAP = {
    "normal": 0, "any": 0, "adjacentFoe": 0, "randomNormal": 0,
    "allAdjacentFoes": 1, "allAdjacent": 2,
    "self": 3, "allySide": 3, "allyTeam": 3, "adjacentAlly": 3,
    "adjacentAllyOrSelf": 3, "all": 3, "foeSide": 1, "scripted": 0,
}


def get(name):
    print(f"  bajando {name} ...", end=" ", flush=True)
    r = requests.get(f"{BASE}/{name}", headers=UA, timeout=90)
    r.raise_for_status()
    print(f"{len(r.content)//1024} KB")
    return r.json()


def slug(s):
    """'Charizard-Mega-Y' -> 'charizardmegay' (formato interno de Showdown)."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def champions_dex_numbers():
    """Numeros de la Pokedex presentes en Champions, segun los sprites."""
    if not SPRITE_INDEX.exists():
        print("Falta sprite_index.json. Corre build_sprite_index.py primero.",
              file=sys.stderr)
        sys.exit(1)
    data = json.loads(SPRITE_INDEX.read_text(encoding="utf-8"))
    return {s["dex"] for s in data.get("sprites", [])}


def main():
    dex_nums = champions_dex_numbers()
    print(f"Champions tiene {len(dex_nums)} especies segun los sprites.\n")

    print("Datos de Pokemon Showdown:")
    pokedex = get("pokedex.json")
    moves = get("moves.json")
    learnsets = get("learnsets.json")

    # ── especies ──
    species = {}
    keep_slugs = {}
    for key, p in pokedex.items():
        num = p.get("num", 0)
        if num not in dex_nums or num <= 0:
            continue
        if p.get("isNonstandard") in ("CAP", "Custom"):
            continue
        bs = p.get("baseStats", {})
        species[key] = {
            "n": p.get("name", key),
            "num": num,
            "s": [bs.get("hp", 1), bs.get("atk", 1), bs.get("def", 1),
                  bs.get("spa", 1), bs.get("spd", 1), bs.get("spe", 1)],
            "t": p.get("types", []),
            "a": sorted(set(p.get("abilities", {}).values())),
            "w": p.get("weightkg", 0),
        }
        if p.get("baseSpecies"):
            species[key]["base"] = slug(p["baseSpecies"])
        keep_slugs[key] = True
    print(f"\nEspecies: {len(species)}")

    # ── movimientos: solo los que alguna de esas especies puede aprender ──
    used = set()
    for key in species:
        # las formas alternativas heredan el learnset de la base
        for k in (key, slug(species[key].get("base", ""))):
            if k and k in learnsets:
                used.update(learnsets[k].get("learnset", {}).keys())

    mv = {}
    for key, m in moves.items():
        if key not in used:
            continue
        if m.get("isNonstandard") in ("CAP", "Custom", "Future"):
            continue
        cat = {"Physical": "F", "Special": "S", "Status": "E"}.get(m.get("category"), "E")
        acc = m.get("accuracy", True)
        mv[key] = {
            "n": m.get("name", key),
            "p": m.get("basePower", 0),
            "t": (m.get("type") or "Normal")[:3].upper(),
            "c": cat,
            "r": TARGET_MAP.get(m.get("target", "normal"), 0),
            "pr": m.get("priority", 0),
            "ac": 100 if acc is True else int(acc or 100),
            "d": (m.get("shortDesc") or m.get("desc") or "")[:110],
        }
    print(f"Movimientos: {len(mv)}")

    # ── learnsets, ya resueltos con la herencia de formas ──
    ls = {}
    for key in species:
        pool = set()
        for k in (key, slug(species[key].get("base", ""))):
            if k and k in learnsets:
                pool.update(learnsets[k].get("learnset", {}).keys())
        ls[key] = sorted(pool & set(mv.keys()))
    total = sum(len(v) for v in ls.values())
    print(f"Learnsets: {total} pares especie-movimiento "
          f"(promedio {total//max(1,len(ls))} por especie)")

    # tipos de 3 letras, como los usa el HUD
    TY3 = {"NOR": "Normal", "FIR": "Fire", "WAT": "Water", "ELE": "Electric",
           "GRA": "Grass", "ICE": "Ice", "FIG": "Fighting", "POI": "Poison",
           "GRO": "Ground", "FLY": "Flying", "PSY": "Psychic", "BUG": "Bug",
           "ROC": "Rock", "GHO": "Ghost", "DRA": "Dragon", "DAR": "Dark",
           "STE": "Steel", "FAI": "Fairy"}
    inv = {v.upper()[:3]: k for k, v in TY3.items()}
    for s in species.values():
        s["t"] = [inv.get(t.upper()[:3], "NOR") for t in s["t"]]
    for m in mv.values():
        m["t"] = inv.get(m["t"], "NOR")

    out = {"v": 1, "source": "pokemon-showdown",
           "species": species, "moves": mv, "learnsets": ls}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    kb = OUT.stat().st_size // 1024
    print(f"\nListo: {OUT} ({kb} KB)")
    print("Copialo a ChampionsHUD/app/src/main/assets/ y recompila.")


if __name__ == "__main__":
    main()
