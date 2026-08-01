#!/usr/bin/env node
/**
 * Suite de pruebas mínima — Champions HUD (roadmap Fase 0, ítem 6).
 *
 * hud.html no está modularizado todavía (decisions.md #18: decisión
 * deliberada de no hacerlo), así que no se puede hacer `require()` del motor
 * de daño directamente. En cambio, esta suite extrae el tramo del script que
 * va desde el inicio hasta justo antes de `function vPre()` — todo lo que no
 * toca el DOM real (motor de daño, tablas MV/ABIL_I18N, calc(), verdict(),
 * el parser de teamlists, equipos guardados, fullSpeedOrder()/topThreats())
 * — y lo corre en un sandbox de Node con un localStorage falso. Las
 * funciones que sí tocan el DOM (render(), vSheet(), etc.) son
 * *declaraciones*, así que definirlas no ejecuta nada — el corte solo
 * importa para no incluir el `boot();` final del archivo.
 *
 * Cubre exactamente el patrón de bug de la auditoría (audit.md §5.2): que el
 * motor de daño reconozca habilidades por su slug canónico, no por un
 * literal en español que dex.json nunca produce. Si alguien reintroduce una
 * comparación tipo `o.aAb==="Intimidación"`, este test no la va a poder
 * probar en el idioma que rompía en silencio — cae fallando acá.
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

const ROOT = path.join(__dirname, "..");
const HUD_PATH = path.join(ROOT, "app/src/main/assets/hud.html");

let failed = 0;
function check(name, fn) {
  try {
    fn();
    console.log(`  ok  ${name}`);
  } catch (e) {
    failed++;
    console.log(`  FAIL ${name}`);
    console.log(`       ${e.message}`);
  }
}
function assert(cond, msg) {
  if (!cond) throw new Error(msg || "assertion failed");
}
function assertEqual(a, b, msg) {
  if (a !== b) throw new Error(`${msg || "no coinciden"}: esperaba ${JSON.stringify(b)}, salió ${JSON.stringify(a)}`);
}

// ── extraer y correr el motor de daño en sandbox ──
function loadEngine() {
  const html = fs.readFileSync(HUD_PATH, "utf-8");
  const start = html.indexOf("<script>") + "<script>".length;
  const end = html.indexOf("function vPre(){");
  if (start < 0 || end < 0) throw new Error("no se encontraron los marcadores esperados en hud.html — ¿cambió la estructura del archivo?");
  let src = html.slice(start, end);
  // vm.runInContext solo expone declaraciones `function`/`var` como propiedades
  // del sandbox — calc()/parseTeamText() ya quedan expuestas así, pero
  // abilName/slugify/ABIL_I18N/MY son const/let (bindings léxicos, invisibles
  // desde afuera). Este footer corre en el mismo scope léxico que el resto
  // del script extraído, así que puede exponerlos explícitamente.
  src += `
    this.abilName = abilName;
    this.slugify = slugify;
    this.ABIL_I18N = ABIL_I18N;
    this.setLang = function (v) { LANG = v; };
    this.getMY = function () { return MY; };
    this.loadTeams = loadTeams;
    this.getTeams = function () { return TEAMS; };
    this.getActiveId = function () { return ACTIVE_ID; };
    this.setActiveId = function (v) { ACTIVE_ID = v; };
    this.activeTeam = activeTeam;
    this.newTeamId = newTeamId;
    this.fullSpeedOrder = fullSpeedOrder;
    this.topThreats = topThreats;
    this.getB = function () { return B; };
    this.mkFoe = mkFoe;
    this.slot = slot;
    this.broughtFoes = broughtFoes;
    this.clusterCards = clusterCards;
    this.parseMovesCard = parseMovesCard;
    this.parseStatsCard = parseStatsCard;
    this.finishOwnScan = finishOwnScan;
    this.setOcrDraft = function (v) { OCR_DRAFT = v; };
  `;

  const sandbox = {
    localStorage: {
      _data: {},
      getItem(k) { return Object.prototype.hasOwnProperty.call(this._data, k) ? this._data[k] : null; },
      setItem(k, v) { this._data[k] = String(v); },
    },
    console,
  };
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox, { filename: "hud.html (motor de daño, extraído)" });
  return sandbox;
}

console.log("Suite de pruebas — Champions HUD\n");
console.log("motor de daño (extraído de hud.html):");

const E = loadEngine();

check("calc() existe y tiene la forma esperada", () => {
  assert(typeof E.calc === "function", "calc no es una función");
});

// Garchomp (445, atacante) contra Blastoise (9, defensor puro Agua — sin
// ninguna inmunidad de tipo que confunda el resultado; Charizard, la primera
// opción, es Fuego/Volador y ya es inmune a Tierra por tipo, no por habilidad).
check("levitate da inmunidad a movimientos Tierra (no Levitación en español)", () => {
  const sinHabilidad = E.calc({ atk: 445, def: 9, move: "Terremoto" });
  const r = E.calc({ atk: 445, def: 9, move: "Terremoto", dAb: "levitate" });
  assert(sinHabilidad !== null && sinHabilidad.e !== 0, "sin habilidad, Tierra debería pegarle normal a Blastoise");
  assert(r !== null, "calc devolvió null");
  assertEqual(r.e, 0, "efectividad esperada 0 (inmune) con el slug levitate");
});

check("el literal viejo en español ya NO produce inmunidad (confirma que se migró)", () => {
  const r = E.calc({ atk: 445, def: 9, move: "Terremoto", dAb: "Levitación" });
  assert(r !== null, "calc devolvió null");
  assert(r.e !== 0, "\"Levitación\" en español no debería dar inmunidad — si esto falla, alguien revirtió la migración de slugs");
});

check("flashfire da inmunidad a movimientos Fuego", () => {
  const r = E.calc({ atk: 6, def: 445, move: "Envite Ígneo", dAb: "flashfire" });
  assert(r !== null, "calc devolvió null");
  assertEqual(r.e, 0, "efectividad esperada 0 (inmune)");
});

check("guts anula la penalidad de quemado en daño físico", () => {
  const base = E.calc({ atk: 445, def: 9, move: "Terremoto", aSta: "quemado" });
  const withGuts = E.calc({ atk: 445, def: 9, move: "Terremoto", aSta: "quemado", aAb: "guts" });
  assert(base.R[15] < withGuts.R[15], "con guts el daño quemado debería ser mayor que sin guts");
});

check("abilName() traduce el mismo slug distinto según LANG", () => {
  assert(typeof E.abilName === "function", "abilName no es una función");
  E.setLang("en");
  const en = E.abilName("intimidate");
  E.setLang("es");
  const es = E.abilName("intimidate");
  assertEqual(en, "Intimidate", "nombre en inglés incorrecto");
  assertEqual(es, "Intimidación", "nombre en español incorrecto");
});

check("slugify() normaliza nombres de Showdown al mismo formato que ABIL_I18N", () => {
  assertEqual(E.slugify("Flash Fire"), "flashfire");
  assert(E.ABIL_I18N[E.slugify("Flash Fire")] !== undefined, "el slug generado no existe en ABIL_I18N");
});

// ── importación de equipo por texto (roadmap Fase 1) ──
console.log("\nimportación de equipo por texto:");

check("parseTeamText lee un set completo con ítem, habilidad, naturaleza y reparto", () => {
  const { team, errors } = E.parseTeamText(
    "Sinistcha @ Colbur Berry\nAbility: Hospitality\nNature: Calm\nSpread: 31/0/7/0/28/0\n" +
    "- Rage Powder\n- Matcha Gotcha\n- Life Dew\n- Trick Room"
  );
  assertEqual(errors.length, 0, `no debería haber avisos: ${JSON.stringify(errors)}`);
  assertEqual(team.length, 1, "debería leer un Pokémon");
  const s = team[0];
  assertEqual(s.dex, 1013, "dex de Sinistcha incorrecto");
  assertEqual(s.item, "Baya Dillo", "el ítem tiene que resolver a su nombre canónico en español (Colbur Berry)");
  assertEqual(s.abil, "hospitality", "la habilidad tiene que resolver al slug");
  assertEqual(s.up, 4, "Calm sube DefEsp (índice 4)");
  assertEqual(s.dn, 1, "Calm baja Atq (índice 1)");
  assertEqual(s.sp.join(","), "31,0,7,0,28,0", "el reparto no se leyó igual");
  assertEqual(s.moves.filter(Boolean).length, 4, "deberían cargarse los 4 movimientos");
});

check("parseTeamText resuelve nombres en español aunque el set esté en inglés", () => {
  const { team, errors } = E.parseTeamText("Garchomp @ Pañuelo Elección\nAbility: Velo Arena\n- Terremoto");
  assertEqual(errors.length, 0, `no debería haber avisos: ${JSON.stringify(errors)}`);
  assertEqual(team[0].item, "Pañuelo Elección");
  assertEqual(team[0].abil, "sandveil");
});

check("parseTeamText no tira excepción con basura y reporta el error", () => {
  const { team, errors } = E.parseTeamText("Esto no es un Pokémon de verdad\n- tampoco esto es un movimiento");
  assertEqual(team.length, 0, "no debería reconocer ningún Pokémon");
  assert(errors.length > 0, "debería reportar al menos un error");
});

check("parseTeamText corta en 6 Pokémon aunque se peguen más", () => {
  const eight = Array.from({ length: 8 }, () => "Sinistcha").join("\n\n");
  const { team } = E.parseTeamText(eight);
  assertEqual(team.length, 6, "no debería superar 6 Pokémon");
});

// ── equipos guardados (Fase 1) ──
console.log("\nequipos guardados:");

check("loadTeams() sin datos previos crea un equipo por defecto", () => {
  E.loadTeams();
  const teams = E.getTeams();
  assertEqual(teams.length, 1, "debería arrancar con un solo equipo");
  assertEqual(teams[0].name, "Equipo 1");
  assert(E.getMY() === E.activeTeam().team, "MY tiene que ser la MISMA referencia que activeTeam().team");
});

check("newTeamId() nunca choca con un id existente", () => {
  E.loadTeams();
  const id1 = E.newTeamId();
  E.getTeams().push({ id: id1, name: "x", team: [] });
  const id2 = E.newTeamId();
  assert(id2 !== id1, "el segundo id no puede repetir el primero");
  assert(id2 > id1, "los ids nuevos tienen que ser crecientes");
});

check("cambiar de equipo activo mueve MY a la referencia correcta", () => {
  E.loadTeams();
  const teams = E.getTeams();
  const secondTeam = [{ dex: 6, sp: [0, 0, 0, 0, 0, 0], up: 1, dn: 3, item: "—", abil: null, mega: false, moves: ["", "", "", ""] }];
  teams.push({ id: E.newTeamId(), name: "Equipo 2", team: secondTeam });
  E.setActiveId(teams[1].id);
  assert(E.activeTeam().team === secondTeam, "activeTeam() tiene que apuntar al segundo equipo");
});

// ── Previa: orden de velocidad completo y amenazas (Fase 1) ──
console.log("\nprevia — velocidad y amenazas:");

check("fullSpeedOrder() devuelve 12 entradas ordenadas, propios exactos y rivales en rango", () => {
  const B = E.getB();
  B.team = [6, 445, 9, 700, 248, 149].map((d) => E.mkFoe(d, 0.9));
  const order = E.fullSpeedOrder();
  assertEqual(order.length, 12, "6 propios + 6 rivales");
  for (let i = 1; i < order.length; i++) {
    assert(order[i - 1].v >= order[i].v, "tiene que estar ordenado descendente");
  }
  const mine = order.filter((x) => x.me);
  const foes = order.filter((x) => !x.me);
  assertEqual(mine.length, 6);
  assertEqual(foes.length, 6);
  assert(mine.every((x) => x.lo === null && typeof x.v === "number"), "los propios tienen velocidad exacta, no rango");
  assert(foes.every((x) => typeof x.lo === "number" && typeof x.hi === "number" && x.lo <= x.hi), "los rivales tienen que traer un rango lo<=hi");
});

check("topThreats() no tira excepción y devuelve como mucho 4, ordenados por daño", () => {
  const B = E.getB();
  B.team = [6, 445, 9, 700, 248, 149].map((d) => E.mkFoe(d, 0.9));
  const th = E.topThreats();
  assert(th.length <= 4, "no debería devolver más de 4 amenazas");
  for (let i = 1; i < th.length; i++) {
    const pctPrev = th[i - 1].r.R[15] / th[i - 1].r.maxHP, pctCur = th[i].r.R[15] / th[i].r.maxHP;
    assert(pctPrev >= pctCur, "tiene que estar ordenado por % de daño descendente");
  }
});

check("topThreats() con equipo propio vacío no rompe, devuelve []", () => {
  const B = E.getB();
  B.team = [6].map((d) => E.mkFoe(d, 0.9));
  const my = E.getMY(), backup = my.slice();
  my.length = 0; // MY es la misma referencia siempre (ver equipos guardados) — vaciar in-place
  try {
    const th = E.topThreats();
    assertEqual(th.length, 0, "sin propios conocidos no hay con qué comparar");
  } finally {
    my.push(...backup); // no dejar el sandbox en un estado raro para los tests que vengan después
  }
});

// ── Campo: quién entra (Fase 1, Parte C) ──
console.log("\ncampo — quién entra:");

check("broughtFoes() solo cuenta los marcados, en cualquier cantidad", () => {
  const B = E.getB();
  B.team = [6, 445, 9].map((d) => E.mkFoe(d, 0.9));
  assertEqual(E.broughtFoes().join(","), "", "nada marcado todavía");
  B.team[0].brought = true;
  B.team[2].brought = true;
  assertEqual(E.broughtFoes().join(","), "0,2", "solo los índices marcados, en orden");
});

check("mkFoe() arranca con brought:false", () => {
  assertEqual(E.mkFoe(6, 0.9).brought, false);
});

// ── OCR del equipo propio (Fase 1, Parte D) ──
console.log("\nOCR del equipo propio:");

check("clusterCards() agrupa por posición en una grilla de 2x3", () => {
  // imagen de 1000x600: columnas en x<500/x>=500, filas en y<200/200-400/>=400
  const lines = [
    { t: "A", x: 50, y: 50, w: 40, h: 20 }, // card 0 (arriba-izq)
    { t: "B", x: 600, y: 50, w: 40, h: 20 }, // card 1 (arriba-der)
    { t: "C", x: 50, y: 250, w: 40, h: 20 }, // card 2 (medio-izq)
    { t: "D", x: 600, y: 250, w: 40, h: 20 }, // card 3 (medio-der)
    { t: "E", x: 50, y: 450, w: 40, h: 20 }, // card 4 (abajo-izq)
    { t: "F", x: 600, y: 450, w: 40, h: 20 }, // card 5 (abajo-der)
  ];
  const cards = E.clusterCards(lines, 1000, 600);
  assertEqual(cards.length, 6, "siempre 6 cards, tengan líneas o no");
  assertEqual(cards[0][0].t, "A");
  assertEqual(cards[1][0].t, "B");
  assertEqual(cards[2][0].t, "C");
  assertEqual(cards[3][0].t, "D");
  assertEqual(cards[4][0].t, "E");
  assertEqual(cards[5][0].t, "F");
});

check("clusterCards() ordena cada card por Y (orden de lectura)", () => {
  const lines = [
    { t: "segunda", x: 50, y: 80, w: 40, h: 20 },
    { t: "primera", x: 50, y: 10, w: 40, h: 20 },
    { t: "tercera", x: 50, y: 150, w: 40, h: 20 },
  ];
  const cards = E.clusterCards(lines, 1000, 600);
  assertEqual(cards[0].map((l) => l.t).join(","), "primera,segunda,tercera");
});

check("parseMovesCard() lee especie/habilidad/ítem/movimientos en orden, ignora ruido de 1 carácter", () => {
  const lines = ["1", "Sinistcha", "Hospitality", "Colbur Berry", "Rage Powder", "Matcha Gotcha", "Life Dew", "Trick Room"]
    .map((t) => ({ t }));
  const r = E.parseMovesCard(lines);
  assertEqual(r.dexName, "Sinistcha");
  assertEqual(r.abilName, "Hospitality");
  assertEqual(r.itemName, "Colbur Berry");
  assertEqual(r.moveNames.join(","), "Rage Powder,Matcha Gotcha,Life Dew,Trick Room");
});

check("parseStatsCard() separa 2 sub-columnas por X y saca la inversión (último número)", () => {
  // Sinistcha real de la captura de Angel: HP 177-31, Atq 80-0, Def 133-7 / AtqEsp 141-0, DefEsp 140-28, Vel 81-0
  const lines = [
    { t: "177 — 31", x: 10, y: 10 }, { t: "80 — 0", x: 10, y: 40 }, { t: "133 — 7", x: 10, y: 70 },
    { t: "141 — 0", x: 300, y: 10 }, { t: "140 — 28", x: 300, y: 40 }, { t: "81 — 0", x: 300, y: 70 },
  ];
  const sp = E.parseStatsCard(lines);
  assertEqual(sp.join(","), "31,0,7,0,28,0", "orden esperado: HP,Atq,Def,AtqEsp,DefEsp,Vel");
});

check("parseStatsCard() devuelve null si no hay suficientes líneas numéricas", () => {
  assertEqual(E.parseStatsCard([{ t: "algo sin números", x: 10, y: 10 }]), null);
});

check("finishOwnScan() arma un equipo nuevo sin tocar los existentes, y avisa lo que no reconoció", () => {
  E.loadTeams();
  const before = E.getTeams().length;
  E.setOcrDraft([
    [{ dexName: "Sinistcha", abilName: "Hospitality", itemName: "Colbur Berry", moveNames: ["Rage Powder", "Matcha Gotcha", "Life Dew", "Trick Room"] },
     { dexName: "no existe esto", abilName: null, itemName: null, moveNames: [] },
     null, null, null, null],
    [[31, 0, 7, 0, 28, 0], null, null, null, null, null],
  ]);
  const html = E.finishOwnScan();
  assertEqual(E.getTeams().length, before + 1, "tiene que sumar un equipo, no reemplazar");
  assert(/no reconozco la especie/.test(html), "debería avisar sobre la card ilegible");
  assertEqual(E.activeTeam().team.length, 1, "solo Sinistcha se pudo leer");
  assertEqual(E.activeTeam().team[0].sp.join(","), "31,0,7,0,28,0");
});

// ── validador de datos (roadmap Fase 0, ítem 5) ──
console.log("\nvalidador de datos (validate_data.py):");
check("validate_data.py corre limpio contra el estado actual del repo", () => {
  const pythons = ["python3", "python"];
  let ran = false, lastErr;
  for (const py of pythons) {
    try {
      execFileSync(py, [path.join(ROOT, "validate_data.py")], { cwd: ROOT, stdio: "pipe" });
      ran = true;
      break;
    } catch (e) {
      lastErr = e;
      if (e.code === "ENOENT") continue; // ese intérprete no existe, probar el siguiente
      throw new Error(`validate_data.py encontró inconsistencias:\n${e.stdout}`);
    }
  }
  if (!ran) throw new Error(`no se encontró python3 ni python en PATH (${lastErr && lastErr.message})`);
});

console.log(`\n${failed === 0 ? "OK" : "FALLÓ"}: ${failed} test(s) fallando.`);
process.exit(failed === 0 ? 0 : 1);
