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
    this.syncActiveFoe = syncActiveFoe;
    this.syncActiveMine = syncActiveMine;
    this.stripIconPrefix = stripIconPrefix;
    this.splitColumns = splitColumns;
    this.foeMovePool = foeMovePool;
    this.best = best;
    this.topThreats = topThreats;
    this.setOcrTarget = function (v) { OCR_TARGET = v; };
    this.statIndexOf = statIndexOf;
    this.megaTargetsMissing = function () {
      return Object.keys(MEGA).filter(function (k) { return !SPD[MEGA[k][0]]; });
    };
    this.megaAlias = megaAlias;
    this.canMega = canMega;
    this.S = S;
    this.clusterCards = clusterCards;
    this.parseMovesCard = parseMovesCard;
    this.parseStatsCard = parseStatsCard;
    this.finishOwnScan = finishOwnScan;
    this.setOcrDraft = function (v) { OCR_DRAFT = v; };
    this.editDistance = editDistance;
    this.closestMatch = closestMatch;
    this.findSpecies = findSpecies;
    this.findAbility = findAbility;
    this.findItem = findItem;
    this.findMove = findMove;
    this.megaSpeed = megaSpeed;
    this.canMega = canMega;
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

check("syncActiveFoe() lleva a los activos el rival recién marcado, sin pisar al que ya estaba confirmado", () => {
  // bug real reportado por Angel: marcar los rivales en "Quién entra" no
  // cambiaba "Rivales" (B.foe) — se quedaba en el default [0,1] aunque el
  // usuario hubiera marcado otros dos.
  const B = E.getB();
  B.doubles = true;
  B.team = [6, 445, 9, 700].map((d) => E.mkFoe(d, 0.9));
  B.foe = [0, 1]; // default, ninguno marcado todavía
  B.team[2].brought = true;
  B.team[3].brought = true;
  E.syncActiveFoe();
  assertEqual(B.foe.slice().sort().join(","), "2,3", "los 2 activos tienen que pasar a ser los recién marcados");

  // si ahora se marca un tercero (revelado más tarde en el combate), no
  // debería desplazar a los 2 que ya están activos y confirmados.
  B.team[0].brought = true;
  E.syncActiveFoe();
  assertEqual(B.foe.slice().sort().join(","), "2,3", "no pisa un activo que ya era un rival confirmado");
});

check("syncActiveMine() lleva a los activos los propios recién marcados en 'Quién entra'", () => {
  const B = E.getB();
  B.doubles = true;
  B.mine = [0, 1];
  B.myBrought = [2, 3];
  E.syncActiveMine();
  assertEqual(B.mine.slice().sort().join(","), "2,3");
});

check("syncActiveFoe() en individual solo sincroniza 1 activo, no 2", () => {
  const B = E.getB();
  B.doubles = false;
  B.team = [6, 445].map((d) => E.mkFoe(d, 0.9));
  B.foe = [0, 1];
  B.team[1].brought = true;
  E.syncActiveFoe();
  assertEqual(B.foe[0], 1, "el único activo pasa a ser el rival marcado");
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
  // Grilla 2x3 completa: las 3 líneas de la card 0 llegan desordenadas y
  // tienen que salir en orden de lectura. Las otras cards existen para que
  // la detección de filas tenga bandas reales que separar.
  const lines = [
    { t: "segunda", x: 50, y: 80, w: 40, h: 20 },
    { t: "primera", x: 50, y: 10, w: 40, h: 20 },
    { t: "tercera", x: 50, y: 150, w: 40, h: 20 },
    { t: "b", x: 600, y: 10, w: 40, h: 20 },
    { t: "c", x: 50, y: 400, w: 40, h: 20 }, { t: "d", x: 600, y: 400, w: 40, h: 20 },
    { t: "e", x: 50, y: 800, w: 40, h: 20 }, { t: "f", x: 600, y: 800, w: 40, h: 20 },
  ];
  const cards = E.clusterCards(lines, 1000, 1000);
  assertEqual(cards[0].map((l) => l.t).join(","), "primera,segunda,tercera");
  assertEqual(cards[4].map((l) => l.t).join(","), "e", "la fila de abajo no se mezcla con la del medio");
});

check("clusterCards() manda la fila 3 a las cards 5 y 6 aunque la grilla no ocupe toda la altura", () => {
  // Bug real: con tercios fijos de la ALTURA DE LA IMAGEN, Archaludon
  // (y=412 en un contenido que va de 175 a 496) caía en la banda del medio,
  // y la card 5 se quedaba con su ítem "Leftovers" como primera línea.
  // Coordenadas tomadas de la captura real de Angel.
  const card = (name, abil, item, x, y) => [
    { t: name, x, y, w: 90, h: 18 },
    { t: abil, x, y: y + 25, w: 90, h: 18 },
    { t: item, x, y: y + 51, w: 90, h: 18 },
  ];
  const lines = [
    { t: "Team 9", x: 480, y: 62, w: 80, h: 20 },
    { t: "Wayne6", x: 770, y: 62, w: 80, h: 20 },
    { t: "Moves & More", x: 495, y: 124, w: 150, h: 20 },
    { t: "Stats", x: 715, y: 124, w: 60, h: 20 },
    ...card("Venusaur", "Chlorophyll", "Venusaurite", 245, 175),
    ...card("Swampert", "Damp", "Swampertite", 705, 175),
    ...card("Grimmsnarl", "Prankster", "Light Clay", 245, 293),
    ...card("Pelipper", "Drizzle", "Damp Rock", 705, 293),
    ...card("Archaludon", "Stamina", "Leftovers", 245, 412),
    ...card("Hydreigon", "Levitate", "Choice Scarf", 705, 412),
  ];
  const cards = E.clusterCards(lines, 1280, 591);
  const first = (i) => (cards[i][0] ? cards[i][0].t : "(vacía)");
  assertEqual(first(0), "Venusaur");
  assertEqual(first(1), "Swampert");
  assertEqual(first(2), "Grimmsnarl");
  assertEqual(first(3), "Pelipper");
  assertEqual(first(4), "Archaludon", "la card 5 tomaba 'Leftovers' (su ítem) como especie");
  assertEqual(first(5), "Hydreigon", "la card 6 tomaba 'Choice Scarf' (su ítem) como especie");
});

check("clusterCards() no confunde el nombre de equipo/entrenador con la especie de la tarjeta 1/2", () => {
  // bug real reportado por Angel: "Team 9" (nombre de su equipo) y "Wayne6"
  // (su nombre de entrenador) — texto del header, arriba de la grilla —
  // se leyeron como si fueran la especie de las tarjetas 1 y 2. El header
  // vive arriba de las pestañas "Moves & More"/"Stats"; usarlas de ancla
  // saca el header del cálculo en vez de asumir que la grilla ocupa toda
  // la altura de la imagen (1000x2000, mismo aspecto que una captura real).
  const lines = [
    { t: "Team 9", x: 100, y: 20, w: 80, h: 20 },
    { t: "Wayne6", x: 700, y: 20, w: 80, h: 20 },
    { t: "Moves & More", x: 350, y: 60, w: 150, h: 20 },
    { t: "Stats", x: 550, y: 60, w: 60, h: 20 },
    { t: "Venusaur", x: 50, y: 200, w: 100, h: 20 },
    { t: "Swampert", x: 600, y: 200, w: 100, h: 20 },
    { t: "Grimmsnarl", x: 50, y: 900, w: 100, h: 20 },
    { t: "Pelipper", x: 600, y: 900, w: 100, h: 20 },
    { t: "Archaludon", x: 50, y: 1600, w: 100, h: 20 },
    { t: "Hydreigon", x: 600, y: 1600, w: 100, h: 20 },
  ];
  const cards = E.clusterCards(lines, 1000, 2000);
  assertEqual(cards[0].map((l) => l.t).join(","), "Venusaur", "tarjeta 1: solo la especie, sin el header");
  assertEqual(cards[1].map((l) => l.t).join(","), "Swampert", "tarjeta 2: solo la especie, sin el header");
  assert(!cards.flat().some((l) => l.t === "Team 9" || l.t === "Wayne6"),
    "el nombre de equipo/entrenador no debería caer en ninguna tarjeta");
});

check("clusterCards() cae al comportamiento anterior si no reconoce las pestañas", () => {
  const lines = [
    { t: "A", x: 50, y: 50, w: 40, h: 20 },
    { t: "B", x: 600, y: 50, w: 40, h: 20 },
  ];
  const cards = E.clusterCards(lines, 1000, 600);
  assertEqual(cards[0][0].t, "A", "sin pestañas reconocidas, sigue agrupando por tercios de toda la imagen");
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

check("parseMovesCard() separa las 2 columnas de la tarjeta (bug real: campos corridos un lugar)", () => {
  // Layout real de "Moves & More" (captura de Angel):
  //   Venusaur     | Sludge Bomb
  //   Chlorophyll  | Protect
  //   Venusaurite  | Earth Power
  //                | Giga Drain
  // Las dos columnas comparten las mismas alturas. Ordenar todo por Y las
  // intercalaba y corría cada campo un lugar.
  const lines = [
    { t: "Venusaur", x: 60, y: 175, w: 90, h: 18 },
    { t: "Sludge Bomb", x: 470, y: 175, w: 110, h: 18 },
    { t: "Chlorophyll", x: 60, y: 200, w: 90, h: 18 },
    { t: "Protect", x: 470, y: 200, w: 70, h: 18 },
    { t: "Venusaurite", x: 60, y: 226, w: 95, h: 18 },
    { t: "Earth Power", x: 470, y: 226, w: 105, h: 18 },
    { t: "Giga Drain", x: 470, y: 250, w: 100, h: 18 },
  ];
  const r = E.parseMovesCard(lines);
  assertEqual(r.dexName, "Venusaur");
  assertEqual(r.abilName, "Chlorophyll", "la habilidad está bajo la especie, no en la columna de movimientos");
  assertEqual(r.itemName, "Venusaurite", "el ítem es el tercero de la columna izquierda");
  assertEqual(r.moveNames.join(","), "Sludge Bomb,Protect,Earth Power,Giga Drain");
});

check("parseMovesCard() reproduce el caso Aegislash del diagnóstico real de Angel", () => {
  // Lo que salió mal en el dispositivo: habilidad "9 Iron Head" (un
  // movimiento con el número de tarjeta pegado), ítem "Stance Change" (la
  // habilidad) y movimiento "5 Spell Tag" (el ítem) — el patrón exacto de
  // dos columnas intercaladas por Y.
  const lines = [
    { t: "Aegislash", x: 60, y: 175, w: 90, h: 18 },
    { t: "Iron Head", x: 470, y: 175, w: 90, h: 18 },
    { t: "Stance Change", x: 60, y: 200, w: 110, h: 18 },
    { t: "Shadow Ball", x: 470, y: 200, w: 100, h: 18 },
    { t: "Spell Tag", x: 60, y: 226, w: 85, h: 18 },
    { t: "Wide Guard", x: 470, y: 226, w: 95, h: 18 },
  ];
  const r = E.parseMovesCard(lines);
  assertEqual(r.dexName, "Aegislash");
  assertEqual(r.abilName, "Stance Change", "Stance Change es la habilidad, no el ítem");
  assertEqual(r.itemName, "Spell Tag", "Spell Tag es el ítem, no un movimiento");
  assertEqual(r.moveNames.join(","), "Iron Head,Shadow Ball,Wide Guard");
});

// Construye la pantalla "Moves & More" real de Angel a una escala dada.
// La captura del dispositivo NO viene a 1280 px (la del chat está reducida),
// así que todo el pipeline tiene que ser independiente de la resolución.
function pantallaMovesReal(k) {
  const S = (v) => Math.round(v * k);
  const LX = 245, LM = 470, RX = 705, RM = 930;
  const card = (x, xm, y, name, abil, item, moves) => {
    const out = [
      { t: name, x: S(x), y: S(y), w: S(100), h: S(18) },
      { t: abil, x: S(x), y: S(y + 25), w: S(100), h: S(18) },
      { t: item, x: S(x), y: S(y + 51), w: S(100), h: S(18) },
    ];
    moves.forEach((m, i) => out.push({ t: m, x: S(xm), y: S(y + i * 25), w: S(110), h: S(18) }));
    return out;
  };
  return [
    { t: "Team 9", x: S(480), y: S(62), w: S(80), h: S(20) },
    { t: "Wayne6", x: S(770), y: S(62), w: S(80), h: S(20) },
    { t: "Moves & More", x: S(495), y: S(124), w: S(150), h: S(20) },
    { t: "Stats", x: S(715), y: S(124), w: S(60), h: S(20) },
    ...card(LX, LM, 175, "Venusaur", "Chlorophyll", "Venusaurite",
      ["Sludge Bomb", "Protect", "Earth Power", "Giga Drain"]),
    ...card(RX, RM, 175, "Swampert", "Damp", "Swampertite",
      ["Wave Crash", "High Horsepower", "Ice Punch", "Protect"]),
    ...card(LX, LM, 293, "Grimmsnarl", "Prankster", "Light Clay",
      ["Light Screen", "Reflect", "Scary Face", "Spirit Break"]),
    ...card(RX, RM, 293, "Pelipper", "Drizzle", "Damp Rock",
      ["Weather Ball", "Hurricane", "Tailwind", "Wide Guard"]),
    ...card(LX, LM, 412, "Archaludon", "Stamina", "Leftovers",
      ["Dragon Pulse", "Flash Cannon", "Electro Shot", "Protect"]),
    ...card(RX, RM, 412, "Hydreigon", "Levitate", "Choice Scarf",
      ["Draco Meteor", "Dark Pulse", "Flamethrower", "Earth Power"]),
  ];
}
const EQUIPO_REAL = [
  ["Venusaur", "Chlorophyll", "Venusaurite", "Sludge Bomb,Protect,Earth Power,Giga Drain"],
  ["Swampert", "Damp", "Swampertite", "Wave Crash,High Horsepower,Ice Punch,Protect"],
  ["Grimmsnarl", "Prankster", "Light Clay", "Light Screen,Reflect,Scary Face,Spirit Break"],
  ["Pelipper", "Drizzle", "Damp Rock", "Weather Ball,Hurricane,Tailwind,Wide Guard"],
  ["Archaludon", "Stamina", "Leftovers", "Dragon Pulse,Flash Cannon,Electro Shot,Protect"],
  ["Hydreigon", "Levitate", "Choice Scarf", "Draco Meteor,Dark Pulse,Flamethrower,Earth Power"],
];
function verificarEquipoReal(k, w, h, etiqueta) {
  const cards = E.clusterCards(pantallaMovesReal(k), Math.round(w * k), Math.round(h * k));
  cards.forEach((c, i) => {
    const r = E.parseMovesCard(c);
    const [dex, abil, item, moves] = EQUIPO_REAL[i];
    assertEqual(r.dexName, dex, `${etiqueta} tarjeta ${i + 1}: especie`);
    assertEqual(r.abilName, abil, `${etiqueta} tarjeta ${i + 1}: habilidad`);
    assertEqual(r.itemName, item, `${etiqueta} tarjeta ${i + 1}: ítem`);
    assertEqual(r.moveNames.join(","), moves, `${etiqueta} tarjeta ${i + 1}: movimientos`);
  });
}

check("pipeline completo, independiente de la resolución de la captura", () => {
  // El dispositivo de Angel no captura a 1280: la del chat viene reducida.
  // Si algún umbral quedara en píxeles absolutos, esto lo delata.
  verificarEquipoReal(1, 1280, 591, "1280:");
  verificarEquipoReal(1.875, 1280, 591, "2400:");
  verificarEquipoReal(3.375, 1280, 591, "4320:");
  verificarEquipoReal(0.6, 1280, 591, "768:");
});

check("pipeline completo: una tarjeta vacía no descoloca a las otras cinco", () => {
  // Si el OCR no lee nada de una tarjeta, las demás tienen que seguir
  // cayendo en su lugar: la tarjeta vacía se reporta y se corrige a mano.
  const lines = pantallaMovesReal(1).filter((l) =>
    !["Grimmsnarl", "Prankster", "Light Clay", "Light Screen", "Reflect", "Scary Face", "Spirit Break"]
      .includes(l.t));
  const cards = E.clusterCards(lines, 1280, 591);
  assertEqual(E.parseMovesCard(cards[0]).dexName, "Venusaur");
  assertEqual(E.parseMovesCard(cards[2]).dexName, null, "la tarjeta ilegible queda vacía, no toma datos de otra");
  assertEqual(E.parseMovesCard(cards[3]).dexName, "Pelipper");
  assertEqual(E.parseMovesCard(cards[4]).dexName, "Archaludon");
  assertEqual(E.parseMovesCard(cards[5]).dexName, "Hydreigon");
});

check("parseMovesCard() cae al orden secuencial si la tarjeta tiene una sola columna", () => {
  const lines = ["Sinistcha", "Hospitality", "Colbur Berry", "Rage Powder"].map((t, i) =>
    ({ t, x: 60, y: 100 + i * 25, w: 90, h: 18 }));
  const r = E.parseMovesCard(lines);
  assertEqual(r.dexName, "Sinistcha");
  assertEqual(r.abilName, "Hospitality");
  assertEqual(r.itemName, "Colbur Berry");
});

check("parseMovesCard() no confunde una indentación chica con una separación de columnas", () => {
  // El ícono del ítem corre su línea unos píxeles. Sin un piso para el
  // hueco, ese desplazamiento se tomaba como borde de columna y partía la
  // columna izquierda: el ítem terminaba como movimiento.
  const lines = [
    { t: "Sinistcha", x: 245, y: 175, w: 90, h: 18 },
    { t: "Hospitality", x: 252, y: 200, w: 90, h: 18 },
    { t: "Colbur Berry", x: 264, y: 226, w: 95, h: 18 },
  ];
  const r = E.parseMovesCard(lines);
  assertEqual(r.dexName, "Sinistcha");
  assertEqual(r.abilName, "Hospitality");
  assertEqual(r.itemName, "Colbur Berry", "el ítem no debe irse a la columna de movimientos");
  assertEqual(r.moveNames.length, 0);
});

check("stripIconPrefix() también saca un dígito suelto (el número de tarjeta pegado)", () => {
  assertEqual(E.findMove("9 Iron Head"), E.findMove("Iron Head"), "el número de tarjeta no debería romper el match");
  assertEqual(E.findItem("5 Spell Tag"), E.findItem("Spell Tag"));
});

check("parseStatsCard() se ancla en las etiquetas, con la etiqueta y los números en líneas separadas", () => {
  // Layout real de la pestaña Stats: etiqueta a la izquierda, stat calculado
  // y la inversión a su derecha, en dos sub-columnas.
  const row = (label, val, inv, x, y) => [
    { t: label, x, y, w: 70, h: 18 },
    { t: String(val), x: x + 110, y, w: 40, h: 18 },
    { t: "— " + inv, x: x + 170, y, w: 40, h: 18 },
  ];
  const lines = [
    ...row("HP", 202, 32, 250, 300), ...row("Sp. Atk", 105, 0, 700, 300),
    ...row("Attack", 128, 32, 250, 326), ...row("Sp. Def", 111, 1, 700, 326),
    ...row("Defense", 110, 0, 250, 352), ...row("Speed", 121, 30, 700, 352),
  ];
  const sp = E.parseStatsCard(lines);
  assert(sp !== null, "no debería devolver null con el layout real");
  assertEqual(sp.join(","), "32,32,0,0,1,30", "orden [PS,Atq,Def,AtqEsp,DefEsp,Vel]");
});

check("parseStatsCard() también lee la etiqueta y los números en una sola línea", () => {
  const lines = [
    { t: "HP 202 32", x: 250, y: 300, w: 200, h: 18 },
    { t: "Sp. Atk 105 0", x: 700, y: 300, w: 200, h: 18 },
    { t: "Attack 128 32", x: 250, y: 326, w: 200, h: 18 },
    { t: "Sp. Def 111 1", x: 700, y: 326, w: 200, h: 18 },
    { t: "Defense 110 0", x: 250, y: 352, w: 200, h: 18 },
    { t: "Speed 121 30", x: 700, y: 352, w: 200, h: 18 },
  ];
  assertEqual(E.parseStatsCard(lines).join(","), "32,32,0,0,1,30");
});

check("parseStatsCard() no confunde 'Attack' con 'Sp. Atk' ni 'Defense' con 'Sp. Def'", () => {
  assertEqual(E.statIndexOf("Attack"), 1);
  assertEqual(E.statIndexOf("Sp. Atk"), 3);
  assertEqual(E.statIndexOf("Defense"), 2);
  assertEqual(E.statIndexOf("Sp. Def"), 4);
  assertEqual(E.statIndexOf("Ataque"), 1, "también en español");
  assertEqual(E.statIndexOf("Ataque Esp."), 3, "'Ataque' no debe comerse 'Ataque Esp.'");
  assertEqual(E.statIndexOf("Giga Drain"), -1, "un movimiento no es una etiqueta de stat");
});

check("parseStatsCard() devuelve null si un valor no es una inversión válida (0–32)", () => {
  // Si se lee el stat calculado en vez de la inversión, tiene que fallar
  // ruidosamente en vez de guardar 202 como reparto.
  const lines = [
    { t: "HP 202", x: 250, y: 300, w: 100, h: 18 },
    { t: "Sp. Atk 105", x: 700, y: 300, w: 100, h: 18 },
    { t: "Attack 128", x: 250, y: 326, w: 100, h: 18 },
    { t: "Sp. Def 111", x: 700, y: 326, w: 100, h: 18 },
    { t: "Defense 110", x: 250, y: 352, w: 100, h: 18 },
    { t: "Speed 121", x: 700, y: 352, w: 100, h: 18 },
  ];
  assertEqual(E.parseStatsCard(lines), null);
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

check("parseStatsCard() tolera que ML Kit parta \"155 — 0\" en 2 líneas separadas", () => {
  // mismo Sinistcha, pero cada valor viene partido en "número" + "— inversión"
  // como 2 líneas distintas a la misma altura (y), en vez de una sola.
  const lines = [
    { t: "177", x: 10, y: 10, h: 14 }, { t: "— 31", x: 50, y: 11, h: 14 },
    { t: "80", x: 10, y: 40, h: 14 }, { t: "— 0", x: 50, y: 41, h: 14 },
    { t: "133", x: 10, y: 70, h: 14 }, { t: "— 7", x: 50, y: 70, h: 14 },
    { t: "141", x: 300, y: 10, h: 14 }, { t: "— 0", x: 340, y: 11, h: 14 },
    { t: "140", x: 300, y: 40, h: 14 }, { t: "— 28", x: 340, y: 41, h: 14 },
    { t: "81", x: 300, y: 70, h: 14 }, { t: "— 0", x: 340, y: 70, h: 14 },
  ];
  const sp = E.parseStatsCard(lines);
  assert(sp !== null, "no debería devolver null con líneas fragmentadas");
  assertEqual(sp.join(","), "31,0,7,0,28,0", "mismo resultado que si viniera en una sola línea por stat");
});

check("parseStatsCard() usa el mayor salto en X, no la mediana, si un lado se fragmenta más que el otro", () => {
  // columna izquierda: las 3 filas partidas en 2 líneas (6 líneas). columna
  // derecha: sin fragmentar (3 líneas). Con mediana esto corta mal (9 líneas
  // totales, mediana cae en la 5ta, que todavía es de la izquierda); con el
  // mayor salto en X, el hueco real entre columnas (50 a 300) sigue siendo
  // el más grande sin importar cuántas líneas haya de cada lado.
  const lines = [
    { t: "177", x: 10, y: 10, h: 14 }, { t: "— 31", x: 50, y: 11, h: 14 },
    { t: "80", x: 10, y: 40, h: 14 }, { t: "— 0", x: 50, y: 41, h: 14 },
    { t: "133", x: 10, y: 70, h: 14 }, { t: "— 7", x: 50, y: 70, h: 14 },
    { t: "141 — 0", x: 300, y: 10 }, { t: "140 — 28", x: 300, y: 40 }, { t: "81 — 0", x: 300, y: 70 },
  ];
  const sp = E.parseStatsCard(lines);
  assert(sp !== null, "no debería devolver null con fragmentación asimétrica");
  assertEqual(sp.join(","), "31,0,7,0,28,0", "misma inversión esperada, sin importar la fragmentación");
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
  assert(/1 de 6/.test(html), "el resumen cuenta cuántas se leyeron de verdad");
  assertEqual(E.activeTeam().team.length, 6,
    "el equipo queda con 6 slots aunque solo se leyera 1: si no, los que fallan no se pueden corregir a mano");
  assertEqual(E.activeTeam().team[0].sp.join(","), "31,0,7,0,28,0");
});

check("finishOwnScan() con OCR_TARGET='active' actualiza el equipo activo en vez de crear otro", () => {
  // Angel llegó a 5 equipos guardados reintentando una lectura que fallaba.
  E.loadTeams();
  const before = E.getTeams().length;
  const activeId = E.getActiveId();
  E.setOcrTarget("active");
  E.setOcrDraft([
    [{ dexName: "Sinistcha", abilName: "Hospitality", itemName: "Colbur Berry", moveNames: ["Rage Powder"] },
     null, null, null, null, null],
    [[31, 0, 7, 0, 28, 0], null, null, null, null, null],
  ]);
  E.finishOwnScan();
  assertEqual(E.getTeams().length, before, "no debería sumar un equipo");
  assertEqual(E.getActiveId(), activeId, "el equipo activo sigue siendo el mismo");
  assertEqual(E.activeTeam().team.length, 6, "sigue teniendo 6 slots");
  assertEqual(E.S(E.activeTeam().team[0].dex).n, "Sinistcha", "pero el slot 1 se reemplazó por lo escaneado");
  E.setOcrTarget("new"); // no dejar el sandbox en un estado raro
});

// ── amenazas: de dónde salen los movimientos del rival (bug real de Angel) ──
console.log("\namenazas y pool de movimientos del rival:");

check("best() con pool vacío devuelve null, no el movimiento más fuerte del juego", () => {
  // Este era el bug: sin datos del rival caía a la lista global y mostraba
  // Electro Shot como amenaza en Blaziken, Mimikyu, Ditto y Sneasler por
  // igual — ninguno de los cuales lo aprende.
  assertEqual(E.best(6, 445, { doubles: true }, []), null, "pool vacío = no sabemos, no 'el más fuerte'");
  assert(E.best(6, 445, { doubles: true }) !== null, "sin pool (consulta libre) sí puede usar la lista global");
});

check("foeMovePool() etiqueta la procedencia y nunca devuelve la lista global", () => {
  const foe = E.mkFoe(445, 0.9);
  const sinDatos = E.foeMovePool(foe);
  assert(["meta", "posible", "sin datos"].includes(sinDatos.src), "sin movimientos vistos no puede decir 'visto'");
  assert(sinDatos.moves.length < 50, "nunca la lista global de movimientos del juego");
  foe.moves = ["Terremoto"];
  const visto = E.foeMovePool(foe);
  assertEqual(visto.src, "visto");
  assertEqual(visto.moves.join(","), "Terremoto", "lo observado gana sobre cualquier estimación");
});

check("topThreats() no inventa una amenaza cuando no hay datos del rival", () => {
  const B = E.getB();
  B.team = [6, 445].map((d) => E.mkFoe(d, 0.9));
  const th = E.topThreats();
  // Sin meta ni learnset cargados en el sandbox, lo correcto es no reportar
  // nada — antes reportaba el movimiento más fuerte del juego para cada uno.
  th.forEach((t) => assert(t.src !== undefined, "cada amenaza declara de dónde salió su movimiento"));
});

// ── matcher difuso para OCR con typos (Fase 1, endurecido tras feedback real) ──
console.log("\nmatch difuso (tolerancia a typos de OCR):");

check("findSpecies() tolera un carácter mal leído", () => {
  assertEqual(E.findSpecies("Swanpert"), E.findSpecies("Swampert"), "un typo de 1 letra tiene que resolver igual");
  assertEqual(E.findSpecies("Swampert"), 260);
});

check("findAbility() tolera un carácter mal leído", () => {
  assertEqual(E.findAbility("Intimidat"), "intimidate");
  assertEqual(E.findAbility("Intimidación"), "intimidate");
});

check("findMove() tolera un carácter mal leído en el nombre en inglés", () => {
  assertEqual(E.findMove("Wave Crush"), "Wave Crash", "typo de 1 letra en un nombre en inglés");
});

check("findMove() ignora un carácter suelto pegado adelante (ícono de tipo leído como letra)", () => {
  // caso real de Angel: el ícono de tipo Normal (un círculo liso) al lado
  // de "Protect" se leyó como "O Protect".
  assertEqual(E.findMove("O Protect"), E.findMove("Protect"), "el prefijo del ícono no debería cambiar el resultado");
  assertEqual(E.findMove("Protect"), "Protección");
});

check("findItem() ignora un carácter suelto pegado adelante (ícono de objeto leído como letra)", () => {
  // caso real de Angel: el ícono de objeto al lado de "Choice Scarf" se
  // leyó como "T Choice Scarf".
  assertEqual(E.findItem("T Choice Scarf"), E.findItem("Choice Scarf"), "el prefijo del ícono no debería cambiar el resultado");
  assertEqual(E.findItem("Choice Scarf"), "Pañuelo Elección");
});

check("findMove() tolera un prefijo de 2 caracteres (ícono + número de tarjeta pegados)", () => {
  // Caso real del diagnóstico de Angel: "W2 Sludge Bomb". Se testea con
  // Protect porque Sludge Bomb solo existe con dex.json cargado, y el
  // sandbox corre con las tablas embebidas — el mecanismo es el mismo.
  assertEqual(E.findMove("W2 Protect"), E.findMove("Protect"));
  assertEqual(E.findMove("Protect"), "Protección");
});

check("findItem() reconoce las piedras mega en inglés aunque la clave esté en español", () => {
  // Las claves de MEGA son mezcla ("Blastoisita" pero "Swampertite"); el
  // juego en inglés siempre muestra "-ite".
  assertEqual(E.megaAlias("Venusaurite"), "Venusaurita");
  assertEqual(E.megaAlias("Charizardite Y"), "Charizardita Y");
  assert(E.findItem("Blastoisite") !== null, "debería resolver a la clave en español");
  assert(E.findItem("Gengarite") !== null);
});

check("Venusaurite existe y su forma mega es resoluble (faltaba entera en las tablas)", () => {
  // Venusaur (dex 3) solo está en dex.json, no en la tabla embebida de 56
  // especies que usa el sandbox — por eso se pasa el dex a mano.
  const it = E.findItem("Venusaurite");
  assert(it !== null, "el ítem tiene que existir");
  const megaDex = E.canMega({ item: it, dex: 3 });
  assert(megaDex, "Venusaur con Venusaurite tiene que poder megaevolucionar");
  assert(E.S(megaDex) !== null, "y su forma mega tiene que existir en SPD");
  assertEqual(E.S(megaDex).n, "Venusaur-Mega");
});

check("toda entrada de MEGA apunta a una forma que existe en SPD", () => {
  // Tres entradas (Swampertite, Sablenita, Mawilita) apuntaban a claves
  // inexistentes: tocar "Megaevolucionado" reventaba en myStat().
  const faltantes = E.megaTargetsMissing();
  assertEqual(faltantes.join(", "), "", "estas piedras apuntan a una forma que no existe");
});

check("stripIconPrefix() no altera nombres reales de una sola palabra", () => {
  assertEqual(E.stripIconPrefix("Protect"), null, "sin espacio, no hay nada que sacar");
  assertEqual(E.stripIconPrefix("Choice Scarf"), null, "ya empieza con una palabra real, no con una letra suelta");
});

check("closestMatch() no matchea cualquier cosa con nombres cortos", () => {
  const entries = [{ key: "cut", label: "Cut" }, { key: "rest", label: "Rest" }];
  assertEqual(E.closestMatch("Xyz", entries), null, "3 letras totalmente distintas no debería matchear");
});

check("closestMatch() devuelve null con texto vacío, no explota", () => {
  assertEqual(E.closestMatch("", [{ key: "a", label: "Algo" }]), null);
  assertEqual(E.closestMatch("algo", []), null);
});

// ── velocidad post-mega en Previa (feedback real de Angel) ──
console.log("\nvelocidad post-mega:");

check("megaSpeed() da un valor mayor que la base cuando lleva la piedra y no mega-evolucionó todavía", () => {
  const m = E.slot(260); // Swampert
  m.item = "Swampertite";
  assert(E.canMega(m), "tiene que poder mega-evolucionar con la piedra puesta");
  const mv = E.megaSpeed(m);
  assert(mv !== null, "no debería ser null si lleva la piedra y no mega-evolucionó");
  assert(mv > 0, "tiene que ser un valor de velocidad real");
});

check("megaSpeed() es null si ya está mega-evolucionado (myStat ya lo refleja solo)", () => {
  const m = E.slot(260);
  m.item = "Swampertite"; m.mega = true;
  assertEqual(E.megaSpeed(m), null);
});

check("megaSpeed() es null si no lleva piedra de mega", () => {
  const m = E.slot(260);
  assertEqual(E.megaSpeed(m), null);
});

check("fullSpeedOrder() incluye megaV solo para el propio con piedra sin mega-evolucionar", () => {
  const B = E.getB();
  B.team = [6].map((d) => E.mkFoe(d, 0.9));
  const my = E.getMY();
  my[0].item = "Swampertite"; my[0].dex = 260; my[0].mega = false;
  const order = E.fullSpeedOrder();
  const swampert = order.find((x) => x.me && x.n === "Swampert");
  assert(swampert, "tiene que estar Swampert en el orden");
  assert(swampert.megaV > swampert.v, "la velocidad mega tiene que ser mayor a la base para Swampert");
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
