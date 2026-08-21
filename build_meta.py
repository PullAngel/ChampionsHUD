#!/usr/bin/env python3
"""
build_meta.py — Champions HUD, meta real de torneos (Fase 2, sprint 2.3)

Reemplaza el meta.json estimado a mano por un artefacto generado desde
torneos reales. Fuente primaria: la API pública de Limitless TCG (sin clave,
esquema verificado el 2026-08-01 — ver docs/architecture.md §10.1.1).

Que un equipo se haya visto en un torneo real no dice nada de su reparto de
stats (Limitless no lo publica), pero sí dice qué especies, ítems, habilidades
y movimientos se usan juntos de verdad — eso es lo que este script agrega.

Corre en la PC del desarrollador, no en el telefono (docs/architecture.md
§10, principio offline-first: la app nunca depende de red durante el
combate). Nunca rompe la generación entera por la caída de una fuente —
degrada con `partial: true` y sigue con lo que sí pudo obtener
(docs/architecture.md §10.4).

Uso:
    pip install requests
    python build_meta.py --limit 40
    cp meta.json ChampionsHUD/app/src/main/assets/
    python validate_data.py    # confirma que todo lo generado es reconocible

--limit controla cuántos torneos recientes se procesan. Más torneos = más
señal, pero más llamadas a la API — Limitless no exige clave para esto pero
tampoco hay que abusar; 40 torneos recientes de Reg M-B ya cubren varios
cientos de equipos.
"""

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path

import requests

# Los nombres de torneo vienen de internet y traen lo que sea: acentos,
# kanji, emojis. En Windows la consola abre en cp1252 y un solo emoji en un
# nombre de torneo tira UnicodeEncodeError y aborta la generación entera —
# pasó de verdad con un torneo llamado "🍋 ...". El dato no tiene nada de
# malo; el que no lo soporta es el terminal. Se fuerza UTF-8 con reemplazo:
# peor caso, un nombre sale con signos raros en pantalla, pero el JSON
# generado (que se escribe aparte, siempre en UTF-8) no se ve afectado.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).parent
HUD = ROOT / "app/src/main/assets/hud.html"
DEX = ROOT / "app/src/main/assets/dex.json"
SPRITE_INDEX = ROOT / "sprite_index.json"

API = "https://play.limitlesstcg.com/api"
UA = {"User-Agent": "ChampionsHUD/0.5 (proyecto personal no comercial)"}

GAME = "VGC"

# Movimientos de control de velocidad reconocidos para roleInCore/
# speedControlMajority (architecture.md §10.6). Nombres en inglés — así
# llegan en decklist[].attacks.
SPEED_CONTROL_MOVES = {
    "Tailwind": "tailwind",
    "Trick Room": "trickroom",
    "Thunder Wave": "paralysis",
    "Icy Wind": "icywind",
    "Glare": "paralysis",
    "Nuzzle": "paralysis",
}

# Ver el comentario junto a "schema" en main(): es la versión del ESQUEMA y
# solo sube si se rompe la compatibilidad hacia atrás (renombrar/quitar un
# campo). Agregar campos nuevos es aditivo y NO la sube.
META_SCHEMA = 1

MIN_TEAMS_PER_SPECIES = 2   # menos que esto es ruido de una sola lista
TOP_ITEMS = 6
TOP_MOVES = 8
TOP_ABILITIES = 4
CORE_MIN_COUNT = 3          # architecture.md §10.3: piso absoluto anti-ruido
SPEED_CONTROL_THRESHOLD = 0.6  # architecture.md §10.6: "mayoritario"
TOP_SETS = 5                # sprint 2.5, R3: combos de movimientos completos
SET_MIN_COUNT = 2           # mismo piso anti-ruido que CORE_MIN_COUNT


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


# ── Tablas canónicas: se leen de hud.html, no se duplican a mano ──
# (mismo principio que ya usa validate_data.py: una sola fuente de verdad)

def load_canonical_tables():
    html = HUD.read_text(encoding="utf-8")

    it_start = html.index("const IT=[")
    it_end = html.index("]];", it_start) + 2
    it_block = html[it_start:it_end]
    item_es_by_en = {}
    for es, en, _cat in re.findall(r'\["([^"]+)","([^"]+)","(\w+)"\]', it_block):
        item_es_by_en[slug(en)] = es

    mega_start = html.index("const MEGA={")
    mega_end = html.index("};", mega_start) + 1
    mega_block = html[mega_start:mega_end]
    mega_keys = re.findall(r'"([^"]+)":\[', mega_block)
    mega_by_norm = {}
    for k in mega_keys:
        mega_by_norm[slug(k)] = k
        # alias -ita/-ite: el juego en inglés siempre dice "-ite", algunas
        # claves de MEGA están en español ("-ita") — mismo criterio que ya
        # usa megaAlias() en hud.html. "ita" puede aparecer a mitad de
        # palabra ("Charizardita Y", no termina en "ita") — por eso el
        # regex busca el límite de palabra, no el final del string entero.
        if re.search(r"ita\b", k, re.I):
            alias = re.sub(r"ita\b", "ite", k, flags=re.I)
            mega_by_norm.setdefault(slug(alias), k)
    # Irregularidades reales conocidas, no adivinadas: la piedra de Blastoise
    # se llama "Blastoisinite" en inglés (no "Blastoisite" — la única de las
    # megas clásicas de Gen 6 con un sufijo distinto al patrón regular).
    if "Blastoisita" in mega_keys:
        mega_by_norm.setdefault(slug("Blastoisinite"), "Blastoisita")

    abil_start = html.index("const ABIL_I18N={")
    abil_end = html.index("\n};", abil_start)
    abil_slugs = set(re.findall(r"(\w+):\{en:", html[abil_start:abil_end]))

    return item_es_by_en, mega_by_norm, abil_slugs


def load_dex():
    if not DEX.exists():
        print(f"AVISO: no existe {DEX} — corré build_dex.py primero. "
              "Sin él no se puede mapear especie/movimiento.", file=sys.stderr)
        return None
    return json.loads(DEX.read_text(encoding="utf-8"))


def load_legal_dex_nums():
    if not SPRITE_INDEX.exists():
        return None
    data = json.loads(SPRITE_INDEX.read_text(encoding="utf-8"))
    return {s["dex"] for s in data.get("sprites", [])}


def build_species_index(dex):
    """norm(nombre) -> num de Pokédex, para especies base y formas."""
    idx = {}
    for key, sp in dex["species"].items():
        idx.setdefault(slug(sp["n"]), sp["num"])
        idx.setdefault(slug(key), sp["num"])
    return idx


def build_move_index(dex):
    """norm(nombre en inglés) -> nombre EXACTO como aparece en dex.json.
    validate_data.py acepta un movimiento de meta.json si coincide con
    dex.json (m["n"]), no hace falta convertir a la clave en español."""
    idx = {}
    for m in dex["moves"].values():
        idx[slug(m["n"])] = m["n"]
    return idx


# Limitless antepone la forma regional ("Alolan Ninetales", "Hisuian
# Arcanine"); Showdown la pospone abreviada ("Ninetales-Alola",
# "Arcanine-Hisui"). Verificado contra un lote real de 419 equipos — es un
# patrón fijo del sitio, no una adivinanza: se resuelve con una tabla chica
# en vez de heurística de fuzzy match, que arriesgaría un falso positivo con
# una especie distinta.
REGIONAL_PREFIX = {"alolan": "alola", "galarian": "galar",
                    "hisuian": "hisui", "paldean": "paldea"}
# Casos puntuales que ni el prefijo regional ni la inversión resuelven —
# confirmados contra un lote real, se agregan a mano de a uno, nunca a ciegas.
SPECIES_ALIAS = {"eternal flower floette": "floette-eternal"}


def resolve_species(name, species_idx):
    n = slug(name)
    if n in species_idx:
        return species_idx[n]
    alias = SPECIES_ALIAS.get(name.lower())
    if alias and slug(alias) in species_idx:
        return species_idx[slug(alias)]
    words = name.split()
    if len(words) > 1 and words[0].lower() in REGIONAL_PREFIX:
        alt = slug(" ".join(words[1:]) + "-" + REGIONAL_PREFIX[words[0].lower()])
        if alt in species_idx:
            return species_idx[alt]
    # Formas especiales pospuestas al revés ("Eternal Flower Floette" en
    # Limitless vs "Floette-Eternal" en Showdown): probar invertido.
    parts = re.findall(r"[A-Z][a-z]*|[a-z]+", name)
    if len(parts) > 1:
        alt = slug("".join(parts[::-1]))
        if alt in species_idx:
            return species_idx[alt]
    return None


def resolve_item(name, item_es_by_en, mega_by_norm):
    if not name:
        return None
    n = slug(name)
    if n in item_es_by_en:
        return item_es_by_en[n]
    if n in mega_by_norm:
        return mega_by_norm[n]
    return None


def resolve_move(name, move_idx):
    return move_idx.get(slug(name))


def resolve_ability(name, abil_slugs):
    s = slug(name)
    return s if s in abil_slugs else None


# ── Limitless: descarga con degradación explícita ──

def api_get(path, **params):
    r = requests.get(f"{API}/{path}", headers=UA, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def resolve_format(regulation):
    games = api_get("games")
    vgc = next((g for g in games if g.get("id") == GAME), None)
    if not vgc:
        raise RuntimeError(f"Limitless no tiene el juego {GAME!r} en /games")
    if regulation not in vgc.get("formats", {}):
        raise RuntimeError(
            f"Regulación {regulation!r} no está en /games — vigentes: "
            f"{list(vgc['formats'].keys())}")
    return regulation  # el id de formato de Limitless YA es "M-B" tal cual


def fetch_tournaments(fmt, limit, dias=None):
    """
    Los torneos más recientes del formato.

    Por defecto la ventana se define por CANTIDAD (`limit`), que es como venía
    desde el sprint 2.3. Eso tiene un problema medido el 2026-08-21: 40 torneos
    resultaron ser 6 días, pero cuántos días cubren depende de cuántos torneos
    se jueguen esa semana. Si Champions se vuelve más popular, los mismos 40
    torneos pasan a cubrir 3 días; si baja la actividad, un mes. **La ventana
    del meta se corre sola con la popularidad del juego, sin que nada avise.**

    `dias` define la ventana por TIEMPO, que es lo que uno quiere decir de
    verdad con "el meta de las últimas semanas": se pide un lote generoso y se
    recorta por fecha. Es también la forma barata de "agregar lo nuevo y
    descartar lo viejo" sin mantener ningún caché — la API ya devuelve los más
    recientes primero, así que la ventana se recalcula sola en cada corrida.
    """
    if not dias:
        return api_get("tournaments", game=GAME, format=fmt, limit=limit)

    # Se pide de más y se recorta: no hay forma de filtrar por fecha del lado
    # del servidor, y pedir 200 cabeceras de torneo es una sola llamada barata
    # (los equipos, que es lo caro, se bajan después y solo de los que quedan).
    crudos = api_get("tournaments", game=GAME, format=fmt, limit=max(limit, 200))
    corte = datetime.now(timezone.utc) - timedelta(days=dias)
    dentro = []
    for t in crudos:
        f = t.get("date")
        if not f:
            continue
        try:
            cuando = datetime.fromisoformat(f.replace("Z", "+00:00"))
        except ValueError:
            continue
        if cuando >= corte:
            dentro.append(t)
    print(f"  {len(dentro)} torneos en los últimos {dias} días "
          f"(de {len(crudos)} traídos).")
    # Si la ventana pedida se come el lote entero, la ventana real es más chica
    # que la pedida y el número mostrado mentiría. Se avisa en vez de callarlo.
    if len(dentro) == len(crudos):
        print(f"  ATENCION: entraron TODOS los torneos traídos, así que la "
              f"ventana real puede ser menor a {dias} días. Subí el lote.")
    return dentro


def fetch_teams(tournaments, fmt):
    """Devuelve (lista de decklists, cuántos torneos fallaron)."""
    teams = []
    failed = 0
    for i, t in enumerate(tournaments, 1):
        print(f"  [{i}/{len(tournaments)}] {t.get('name', t['id'])} "
              f"({t.get('players', '?')} jug.) ...", end=" ", flush=True)
        try:
            standings = api_get(f"tournaments/{t['id']}/standings")
        except Exception as e:
            failed += 1
            print(f"FALLÓ ({e.__class__.__name__})")
            continue
        n = 0
        for entry in standings:
            deck = entry.get("decklist") or []
            if len(deck) >= 4:  # menos de 4 no es un equipo de VGC real
                teams.append(deck)
                n += 1
        print(f"{n} equipos")
        time.sleep(0.3)  # generación semanal, no en vivo — no hay apuro
    return teams, failed


# ── Agregación ──

def aggregate(teams, species_idx, item_es_by_en, mega_by_norm, move_idx, abil_slugs):
    team_count = Counter()
    item_count = defaultdict(Counter)
    ability_count = defaultdict(Counter)
    move_count = defaultdict(Counter)
    set_count = defaultdict(Counter)  # R3 (roadmap Sprint 2.5): combos completos de 4
    pair_count = Counter()
    unresolved_species = Counter()
    unresolved_items = Counter()
    unresolved_abilities = Counter()
    unresolved_moves = Counter()

    for deck in teams:
        dex_nums = []
        for mon in deck:
            num = resolve_species(mon.get("name") or mon.get("id", ""), species_idx)
            if num is None:
                unresolved_species[mon.get("name") or mon.get("id", "")] += 1
                continue
            dex_nums.append(num)
            team_count[num] += 1

            item = resolve_item(mon.get("item"), item_es_by_en, mega_by_norm)
            if mon.get("item"):
                if item:
                    item_count[num][item] += 1
                else:
                    unresolved_items[mon["item"]] += 1

            ab = resolve_ability(mon.get("ability"), abil_slugs)
            if mon.get("ability"):
                if ab:
                    ability_count[num][ab] += 1
                else:
                    unresolved_abilities[mon["ability"]] += 1

            attacks = mon.get("attacks") or []
            resolved_moves = []
            for mv in attacks:
                rmv = resolve_move(mv, move_idx)
                if rmv:
                    move_count[num][rmv] += 1
                    resolved_moves.append(rmv)
                else:
                    unresolved_moves[mv] += 1

            # Un combo solo cuenta si TODOS los movimientos listados se
            # resolvieron -- un set de 3 producido porque el 4to movimiento
            # no matcheó sería un dato inventado (parecería el set real de
            # otro Pokémon), exactamente el tipo de degradación silenciosa
            # que el proyecto evita (vision.md, "fallo ruidoso").
            if attacks and len(resolved_moves) == len(attacks):
                set_count[num][tuple(sorted(resolved_moves))] += 1

        for a, b in combinations(sorted(set(dex_nums)), 2):
            pair_count[(a, b)] += 1

    return {
        "team_count": team_count, "item_count": item_count,
        "ability_count": ability_count, "move_count": move_count,
        "set_count": set_count, "pair_count": pair_count,
        "unresolved": {
            "species": unresolved_species, "items": unresolved_items,
            "abilities": unresolved_abilities, "moves": unresolved_moves,
        },
    }


def role_in_core(num, move_count_for_num, team_count_for_num):
    """architecture.md §10.6: rol habitual + bandera de control de velocidad
    mayoritario. Prior de meta — nunca se usa para descartar una hipótesis
    (inference.md §1/§7), solo para etiquetar la especie con su patrón de uso."""
    if team_count_for_num < MIN_TEAMS_PER_SPECIES:
        return None, None
    for mv, tag in SPEED_CONTROL_MOVES.items():
        c = move_count_for_num.get(mv, 0)
        pct = c / team_count_for_num
        if pct >= SPEED_CONTROL_THRESHOLD:
            return f"suele traer {mv}", {"tool": tag, "pct": round(pct, 2)}
    return None, None


def build_species_entries(agg, total_teams):
    out = {}
    for num, tc in agg["team_count"].items():
        if tc < MIN_TEAMS_PER_SPECIES:
            continue
        items = agg["item_count"][num].most_common(TOP_ITEMS)
        moves = agg["move_count"][num].most_common(TOP_MOVES)
        abilities = agg["ability_count"][num].most_common(TOP_ABILITIES)
        role, speedctl = role_in_core(num, dict(agg["move_count"][num]), tc)

        entry = {
            "usage": round(tc / total_teams * 100, 1),
            "items": [[name, round(c / tc * 100)] for name, c in items],
            "moves": [[name, round(c / tc * 100)] for name, c in moves],
            "abilities": [[name, round(c / tc * 100)] for name, c in abilities],
            "spreads": [],  # arquitecture.md §10.1.1: ninguna fuente da esto hoy
        }
        if role:
            entry["roleInCore"] = role
        if speedctl:
            entry["speedControlMajority"] = speedctl

        # R3 (roadmap Sprint 2.5): combos de 4 movimientos vistos completos de
        # verdad, no una combinación de los "moves" top por separado -- esto
        # es lo que permite después descartar un set incompleto (inference.md
        # §5) cuando el rival ya mostró un movimiento que ese set no trae.
        # "setsSample" es el denominador real (equipos con TODOS los
        # movimientos resueltos), casi siempre más chico que tc -- se deja
        # explícito en vez de calcular el % contra tc y esconder la
        # diferencia (mismo criterio de "fallo ruidoso" que el resto).
        sample = sum(agg["set_count"][num].values())
        if sample:
            top_sets = agg["set_count"][num].most_common(TOP_SETS)
            sets = [{"moves": list(mv_tuple), "count": c,
                     "pct": round(c / sample * 100)}
                    for mv_tuple, c in top_sets if c >= SET_MIN_COUNT]
            if sets:
                entry["sets"] = sets
                entry["setsSample"] = sample
        out[str(num)] = entry
    return out


def build_cores(agg, total_teams):
    cores = []
    for (a, b), c in agg["pair_count"].most_common(60):
        if c < CORE_MIN_COUNT:
            continue
        cores.append({"pair": [a, b], "count": c,
                       "pct": round(c / total_teams * 100, 1)})
    return cores


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regulation", default="M-B")
    ap.add_argument("--limit", type=int, default=40,
                     help="cuántos torneos recientes procesar (default 40)")
    ap.add_argument("--dias", type=int, default=None,
                     help="ventana por TIEMPO en vez de por cantidad: procesa los "
                          "torneos de los últimos N días. Más estable que --limit, "
                          "que se corre solo si cambia cuántos torneos se juegan "
                          "por semana (medido: 40 torneos = 6 días el 2026-08-21).")
    ap.add_argument("--out", default="meta.json")
    # --dex existe para que update_data.py encadene este paso sobre un dex.json
    # recién generado que todavía NO está instalado. Sin él, una corrida
    # encadenada resolvía los nombres de Limitless contra el dex de la versión
    # anterior: con especies nuevas en el juego, las nuevas quedarían "sin
    # resolver" sin que nada explique por qué. El default no cambia el uso suelto.
    ap.add_argument("--dex", default=None, help="dex.json a usar (default: el instalado)")
    a = ap.parse_args()

    if a.dex:
        global DEX
        DEX = Path(a.dex)

    dex = load_dex()
    if dex is None:
        sys.exit(1)
    legal_nums = load_legal_dex_nums()

    print("Tablas canónicas de hud.html ...")
    item_es_by_en, mega_by_norm, abil_slugs = load_canonical_tables()
    species_idx = build_species_index(dex)
    move_idx = build_move_index(dex)

    print(f"\nFormato: resolviendo {a.regulation!r} contra /games ...")
    fmt = resolve_format(a.regulation)

    ventana = f"últimos {a.dias} días" if a.dias else f"hasta {a.limit} torneos"
    print(f"\nTorneos recientes ({a.regulation}, {ventana}):")
    tournaments = fetch_tournaments(fmt, a.limit, a.dias)
    teams, failed_tournaments = fetch_teams(tournaments, fmt)

    if not teams:
        print("\nNo se pudo traer ningún equipo — se conserva el meta.json existente.",
              file=sys.stderr)
        sys.exit(1)

    print(f"\n{len(teams)} equipos de {len(tournaments) - failed_tournaments}"
          f"/{len(tournaments)} torneos. Agregando ...")
    agg = aggregate(teams, species_idx, item_es_by_en, mega_by_norm, move_idx, abil_slugs)

    species = build_species_entries(agg, len(teams))
    if legal_nums:
        antes = len(species)
        species = {k: v for k, v in species.items() if int(k) in legal_nums}
        podadas = antes - len(species)
        if podadas:
            print(f"Podadas {podadas} especies no legales según sprite_index.json.")

    cores = build_cores(agg, len(teams))

    u = agg["unresolved"]
    for label, counter in (("especies", u["species"]), ("ítems", u["items"]),
                            ("habilidades", u["abilities"]), ("movimientos", u["moves"])):
        if counter:
            top = ", ".join(f"{k} ({v})" for k, v in counter.most_common(8))
            print(f"Sin resolver ({label}, {sum(counter.values())} veces): {top}")

    out = {
        # Versión del ESQUEMA, no del contenido (`updated` es el contenido).
        # Contrato, documentado en docs/architecture.md §10.2: los cambios son
        # ADITIVOS. Agregar un campo nuevo NO sube este número — el motor lee
        # todo con `?.`/`||` y simplemente ignora lo que no conoce, así que un
        # meta nuevo funciona en una app vieja y viceversa. Solo se sube si
        # alguna vez se RENOMBRA o se QUITA un campo existente, que es lo único
        # que puede romper a un lector viejo. Hay un test que lo verifica
        # (tests/run.js, "contrato de esquema de meta.json").
        "schema": META_SCHEMA,
        "regulation": a.regulation,
        "format": "doubles",
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated": datetime.now(timezone.utc).date().isoformat(),
        "source": "limitless",
        "sourceCounts": {"tournaments": len(tournaments) - failed_tournaments,
                          "teams": len(teams)},
        # Con qué criterio se eligieron esos torneos. Va en el archivo porque
        # dos meta.json con el mismo número de torneos pueden cubrir ventanas
        # de tiempo muy distintas (medido: 40 torneos = 6 días), y sin esto no
        # hay forma de saber cuál se está mirando.
        "window": ({"tipo": "dias", "dias": a.dias} if a.dias
                   else {"tipo": "cantidad", "torneos": a.limit}),
        "partial": failed_tournaments > 0,
        "note": (f"Generado desde {len(teams)} equipos reales de "
                 f"{len(tournaments) - failed_tournaments} torneos de Limitless TCG "
                 f"(Reg {a.regulation}). Reparto de stats sigue sin fuente real "
                 f"(architecture.md §10.1.1) — no incluido."),
        "species": species,
        "cores": cores,
    }
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                            encoding="utf-8")
    print(f"\n{a.out}: {len(species)} especies, {len(cores)} cores, "
          f"regulación {a.regulation}{' (parcial)' if out['partial'] else ''}.")


if __name__ == "__main__":
    main()
