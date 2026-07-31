#!/usr/bin/env node
/**
 * Suite de pruebas mínima — Champions HUD (roadmap Fase 0, ítem 6).
 *
 * hud.html no está modularizado todavía (decisions.md #18: decisión
 * deliberada de no hacerlo), así que no se puede hacer `require()` del motor
 * de daño directamente. En cambio, esta suite extrae el tramo del script que
 * va desde el inicio hasta el cierre de la sección IMPORTACIÓN DE EQUIPO POR
 * TEXTO, justo antes de VISTAS — todo lo que no toca el DOM real (motor de
 * daño, tablas MV/ABIL_I18N, calc(), verdict(), el parser de teamlists) — y
 * lo corre en un sandbox de Node con un localStorage falso.
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
  const end = html.indexOf("/* ═════ VISTAS ═════ */");
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
