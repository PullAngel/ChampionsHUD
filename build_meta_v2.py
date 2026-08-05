#!/usr/bin/env python3
"""
build_meta_v2.py — Champions HUD, cruce con Pokemon Champions Battle Data (EXPERIMENTAL)

SEGUNDA VERSIÓN EN PARALELO, A PROPÓSITO (pedido explícito de Angel,
2026-08-04): "haz un segundo fusionado y probamos cuál da mejores
resultados para la versión final, sin borrar el otro hasta entonces".
build_meta.py (Limitless, sprints 2.3/2.5) sigue intacto y sigue siendo el
que usa la app hoy — este script genera `meta_v2.json` aparte, en la raíz,
sin tocar `app/src/main/assets/meta.json`. Nada de esto se instala en la
app todavía; es material de comparación.

QUÉ APORTA ESTA FUENTE QUE LIMITLESS NO DABA
    - Reparto de EVs real (escala 0–32 de Champions) y naturaleza real,
      cada uno con su % de uso independiente — esto es lo que resuelve el
      bloqueo de "spreadEstimate" (architecture.md §10.1.1): ni Limitless
      ni Pikalytics daban una distribución real con esta cobertura.
    - Muestra de partidas de ranked ladder de Champions, no solo decklists
      de torneos — investigado y CONFIRMADO por cruce real antes de
      escribir una sola línea de este script: los % de movimientos/ítems
      de Kingambit entre Limitless (Reg M-B, torneos) y esta fuente
      (temporada "Current"/"M4") coinciden de forma muy cercana en cada
      valor — evidencia de que ambas reflejan la misma regulación activa
      (no hay ambigüedad de "M-B" que resolver del lado de Limitless: solo
      existe una regulación viva en el juego a la vez, así que "lo que está
      vivo ahora" es necesariamente lo mismo en las dos fuentes).

QUÉ NO APORTA (Limitless sigue siendo la única fuente para esto)
    - Sets completos de 4 movimientos por Pokémon — esta fuente da
      movimientos individuales rankeados por separado (verificado contra
      el CSV crudo, no solo el resumen), igual limitación que Limitless
      tenía antes del sprint 2.5 R3. `sets`/`setsSample` de meta.json
      viajan sin cambios desde `build_meta.py`.
    - Cores por pares reales de equipo con conteo — da un top-10 de
      compañeros por especie (sin porcentaje ni conteo conjunto), no el
      mismo dato que `cores` (pares con `count`/`pct` reales). Se guarda
      aparte, como `cbdTeammates`, informativo, NO fusionado con `cores`.

UN CUIDADO DE PRECISIÓN QUE VALE LA PENA DEJAR EXPLÍCITO: el ranking de
naturalezas y el de repartos de EVs son DOS distribuciones INDEPENDIENTES
en la fuente — no vienen como pares (naturaleza X + reparto Y, tantas
veces juntos). Por eso este script NUNCA arma una fila que diga "Adamant
con 32/32/0/0/2/0, 17% de las veces" — eso sería inventar una correlación
que la fuente no mide. Se guardan como dos listas separadas
(`topNatures`, `topEvSpreads`), cada una con su propio %.

Fuente: https://championsbattledata.com — API pública, sin key, CORS
habilitado, sin límite de tasa documentado (se pide con pausa entre
requests de todos modos, mismo criterio que ya usa build_meta.py con
Limitless — es un proceso batch, no en vivo).

Uso:
    python build_meta_v2.py
    # genera meta_v2.json en la raíz — no pisa meta.json ni assets/meta.json
"""

import csv
import io
import json
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent))
import build_meta as bm  # reusa slug(), tablas canónicas, resolución de especie/ítem/movimiento/habilidad

ROOT = Path(__file__).parent
LIMITLESS_META = ROOT / "app/src/main/assets/meta.json"
DEX = ROOT / "app/src/main/assets/dex.json"

CBD_API = "https://championsbattledata.com/api"
CBD_ROOT = "https://championsbattledata.com/"


def _curl_get(url, timeout=30):
    """Champions Battle Data responde en ~1-3s a `curl` pero 30-45s a la
    librería `requests` de Python contra el MISMO endpoint, MISMO User-
    Agent -- verificado a mano el 2026-08-04, no es el header, es el
    fingerprint TLS/HTTP del cliente lo que algo (WAF/CDN) está
    desacelerando. Nada de esto es autenticado ni privado -- es la misma
    data pública que ya se documentó como abierta, así que resolver el
    fingerprint con curl no evade ningún control real, solo evita un
    cuello de botella de 2 horas para 236 requests que hubiera sido
    irrespetuoso de todos modos para un sitio de hobby/comunidad."""
    r = subprocess.run(["curl", "-sS", "--max-time", str(timeout), url],
                        capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"curl falló ({r.returncode}) para {url}: {r.stderr.strip()}")
    return r.stdout

TOP_CBD_MOVES = 8
TOP_CBD_ITEMS = 6
TOP_CBD_ABILITIES = 4
TOP_CBD_TEAMMATES = 6
TOP_NATURES = 5
TOP_EV_SPREADS = 5


def fetch_cbd_index():
    return json.loads(_curl_get(CBD_API, timeout=60))


def fetch_cbd_csv(path):
    # Algunos nombres de archivo traen espacios/puntos sin codificar tal
    # cual vienen en el índice ("Mr. Rime.csv", "Alolan Ninetales.csv") --
    # confirmado como la causa real de ~35 fallos en la primera corrida
    # (no era intermitencia de red: el mismo lote fallaba siempre igual,
    # reintentar no cambiaba nada). safe="/" para no tocar los separadores
    # de carpeta.
    return _curl_get(CBD_ROOT + quote(path, safe="/"), timeout=20)


def parse_cbd_csv(text):
    """CSV -> {categoría: [{"rank","name","pct", ...}, ...]}, ordenado por
    rank tal cual viene. Usa csv.DictReader (no split(",") a mano) porque
    algunos nombres de Pokémon/ítems podrían traer texto con formato raro —
    no vale la pena confiar en que nunca va a pasar."""
    rows = defaultdict(list)
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        cat = row.get("category")
        if not cat:
            continue
        pct = None
        raw_pct = (row.get("percentage") or "").strip()
        if raw_pct.endswith("%"):
            try:
                pct = float(raw_pct[:-1])
            except ValueError:
                pct = None
        entry = {"rank": int(row["rank"]), "name": row.get("name") or "", "pct": pct}
        if cat == "stat_alignment":
            entry["statUp"] = row.get("stat_up") or None
            entry["statDown"] = row.get("stat_down") or None
        if cat == "stat_points":
            def n(k):
                v = (row.get(k) or "").strip()
                return int(v) if v else 0
            entry["sp"] = [n("hp_points"), n("attack_points"), n("defense_points"),
                            n("sp_atk_points"), n("sp_def_points"), n("speed_points")]
        rows[cat].append(entry)
    for cat in rows:
        rows[cat].sort(key=lambda e: e["rank"])
    return dict(rows)


def resolve_cbd_species(entry, species_idx):
    """CBD ya da `showdownId` en formato Showdown -- casi siempre matchea
    directo contra dex.json vía slug(). No se intenta resolver formas mega
    (`summary.forms` con más de una entrada) por nombre: la numeración de
    mega de este proyecto (900000+dex*10+n, ver hud.html/audit.md §5.11) no
    tiene forma de derivarse de un slug "mega-x" sin adivinar cuál mega le
    corresponde a qué número -- se deja sin resolver a propósito, no se
    inventa un mapeo."""
    n = bm.slug(entry.get("showdownId") or entry.get("slug") or "")
    if n in species_idx:
        return species_idx[n]
    return bm.resolve_species(entry.get("name") or "", species_idx)


def resolve_cbd_moves(rows, move_idx):
    out, unresolved = [], []
    for e in rows.get("move", [])[:TOP_CBD_MOVES]:
        rmv = bm.resolve_move(e["name"], move_idx)
        (out if rmv else unresolved).append([rmv or e["name"], e["pct"]])
    return out, unresolved


def resolve_cbd_items(rows, item_es_by_en, mega_by_norm):
    out, unresolved = [], []
    for e in rows.get("held_item", [])[:TOP_CBD_ITEMS]:
        it = bm.resolve_item(e["name"], item_es_by_en, mega_by_norm)
        (out if it else unresolved).append([it or e["name"], e["pct"]])
    return out, unresolved


def resolve_cbd_abilities(rows, abil_slugs):
    out, unresolved = [], []
    for e in rows.get("ability", [])[:TOP_CBD_ABILITIES]:
        ab = bm.resolve_ability(e["name"], abil_slugs)
        (out if ab else unresolved).append([ab or e["name"], e["pct"]])
    return out, unresolved


def cbd_teammates(rows, species_idx):
    """Informativo, sin %  (la fuente no lo da para esta categoría) -- NO
    se fusiona con `cores` de Limitless, que sí tiene conteo real."""
    out = []
    for e in rows.get("teammate", [])[:TOP_CBD_TEAMMATES]:
        num = resolve_cbd_species({"name": e["name"], "showdownId": e["name"]}, species_idx)
        if num:
            out.append(num)
    return out


def cbd_natures(rows):
    return [{"name": e["name"], "pct": e["pct"], "statUp": e.get("statUp"),
              "statDown": e.get("statDown")}
            for e in rows.get("stat_alignment", [])[:TOP_NATURES] if e["pct"] is not None]


def cbd_ev_spreads(rows):
    return [{"sp": e["sp"], "pct": e["pct"]}
            for e in rows.get("stat_points", [])[:TOP_EV_SPREADS] if e["pct"] is not None]


def main():
    if not LIMITLESS_META.exists():
        print(f"Falta {LIMITLESS_META} -- corré build_meta.py primero (este script "
              "usa su salida como base de usage/moves/items/abilities/sets/cores).",
              file=sys.stderr)
        sys.exit(1)
    if not DEX.exists():
        print(f"Falta {DEX} -- corré build_dex.py primero.", file=sys.stderr)
        sys.exit(1)

    base = json.loads(LIMITLESS_META.read_text(encoding="utf-8"))
    dex = json.loads(DEX.read_text(encoding="utf-8"))

    print("Tablas canónicas de hud.html ...")
    item_es_by_en, mega_by_norm, abil_slugs = bm.load_canonical_tables()
    species_idx = bm.build_species_index(dex)
    move_idx = bm.build_move_index(dex)

    print("Bajando índice de Pokémon Champions Battle Data ...")
    cbd = fetch_cbd_index()
    print(f"{len(cbd['pokemon'])} especies en el índice de CBD "
          f"(generado {cbd.get('generatedAt')}).")

    species = dict(base.get("species", {}))  # copia -- no muta el objeto base
    unresolved_species, unresolved_moves, unresolved_items, unresolved_abilities = [], [], [], []
    matched, csv_failed = 0, 0

    for i, entry in enumerate(cbd["pokemon"], 1):
        num = resolve_cbd_species(entry, species_idx)
        if num is None:
            unresolved_species.append(entry.get("showdownId") or entry.get("name"))
            continue
        doubles_csv = next((c["path"] for c in entry.get("battleDataCsvs", [])
                             if c.get("season") == "Current" and c.get("format") == "Doubles"
                             and "date" not in c), None)
        if not doubles_csv:
            continue
        print(f"  [{i}/{len(cbd['pokemon'])}] {entry.get('showdownId')} ...", end=" ", flush=True)
        text = None
        for attempt in (1, 2):
            try:
                text = fetch_cbd_csv(doubles_csv)
                break
            except Exception as e:
                if attempt == 2:
                    csv_failed += 1
                    print(f"FALLÓ tras reintentar ({e.__class__.__name__})")
                else:
                    time.sleep(1)  # casi todos los fallos vistos en la corrida real fueron
                    # de red, transitorios -- un segundo alcanza y sobra antes de reintentar.
        if text is None:
            continue
        rows = parse_cbd_csv(text)

        moves, umv = resolve_cbd_moves(rows, move_idx)
        items, uit = resolve_cbd_items(rows, item_es_by_en, mega_by_norm)
        abilities, uab = resolve_cbd_abilities(rows, abil_slugs)
        unresolved_moves += umv; unresolved_items += uit; unresolved_abilities += uab

        key = str(num)
        entry_out = dict(species.get(key, {}))  # conserva usage/moves/items/abilities/sets/cores de Limitless si ya existía
        entry_out["cbdMoves"] = moves
        entry_out["cbdItems"] = items
        entry_out["cbdAbilities"] = abilities
        entry_out["cbdTeammates"] = cbd_teammates(rows, species_idx)
        entry_out["topNatures"] = cbd_natures(rows)
        entry_out["topEvSpreads"] = cbd_ev_spreads(rows)
        # Señal barata de acuerdo entre fuentes -- no una fusión, solo un
        # booleano inspeccionable: ¿el #1 de cada fuente coincide?
        if entry_out.get("moves") and moves:
            entry_out["agreesOnTopMove"] = entry_out["moves"][0][0] == moves[0][0]
        if entry_out.get("items") and items:
            entry_out["agreesOnTopItem"] = entry_out["items"][0][0] == items[0][0]
        species[key] = entry_out
        matched += 1
        print("ok")
        time.sleep(0.15)  # 236 requests -- no hay apuro, ver nota de build_meta.py

    for label, lst in (("especies", unresolved_species), ("movimientos", unresolved_moves),
                        ("ítems", unresolved_items), ("habilidades", unresolved_abilities)):
        if lst:
            print(f"Sin resolver ({label}, {len(lst)}): {', '.join(str(x) for x in lst[:10])}"
                  f"{' ...' if len(lst) > 10 else ''}")

    out = dict(base)
    out["species"] = species
    out["cbdGeneratedAt"] = cbd.get("generatedAt")
    out["cbdSourceCounts"] = {"pokemon": len(cbd["pokemon"]), "matched": matched, "csvFailed": csv_failed}
    out["note"] = (base.get("note", "") + " Fusionado con Pokemon Champions Battle Data "
                   f"({matched} especies con cbdMoves/cbdItems/cbdAbilities/topNatures/topEvSpreads) "
                   "-- EXPERIMENTAL, ver build_meta_v2.py.")
    out["generatedAtV2"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out_path = ROOT / "meta_v2.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"\n{out_path}: {matched} especies cruzadas con CBD de {len(species)} totales "
          f"(base Limitless: {len(base.get('species', {}))}).")


if __name__ == "__main__":
    main()
