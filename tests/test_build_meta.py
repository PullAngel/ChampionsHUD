#!/usr/bin/env python3
"""
test_build_meta.py — Champions HUD, Fase 2 sprint 2.3

Pruebas de las funciones puras de build_meta.py: resolución de especie/ítem/
movimiento/habilidad y agregación, con datos fijos (fixtures) en vez de red.
No pega contra Limitless — eso ya se verificó a mano (docs/roadmap.md,
sprint 2.3) y no tiene sentido depender de la red para correr los tests.

Uso:
    python tests/test_build_meta.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import build_meta as bm  # noqa: E402

ROOT = Path(__file__).parent.parent


class TestSlug(unittest.TestCase):
    def test_normaliza_minuscula_y_saca_simbolos(self):
        self.assertEqual(bm.slug("Choice Scarf"), "choicescarf")
        self.assertEqual(bm.slug("King's Rock"), "kingsrock")


class TestTablasCanonicas(unittest.TestCase):
    """Contra el hud.html real del repo — si estas tablas cambian de forma,
    el generador tiene que enterarse acá, no en un run silencioso contra la
    API real que produce un meta.json con menos cobertura de la esperada."""

    @classmethod
    def setUpClass(cls):
        cls.item_es_by_en, cls.mega_by_norm, cls.abil_slugs = bm.load_canonical_tables()

    def test_items_regulares_resuelven_ingles_a_espanol(self):
        self.assertEqual(self.item_es_by_en[bm.slug("Choice Scarf")], "Pañuelo Elección")
        self.assertEqual(self.item_es_by_en[bm.slug("Leftovers")], "Restos")

    def test_piedras_mega_con_ita_a_mitad_de_palabra_resuelven(self):
        # bug real encontrado en el primer run: "Charizardita Y" no termina
        # en "ita" (termina en "Y"), así que el gate viejo (endswith) no la
        # detectaba — quedaba sin resolver "Charizardite Y" pese a que la
        # tabla SÍ tenía la piedra, solo que con nombre en español.
        r = bm.resolve_item("Charizardite Y", self.item_es_by_en, self.mega_by_norm)
        self.assertEqual(r, "Charizardita Y")

    def test_blastoisinite_alias_irregular(self):
        # única piedra clásica de Gen 6 con un sufijo irregular en inglés
        # ("-inite" en vez de "-ite") — alias a mano, no adivinado.
        r = bm.resolve_item("Blastoisinite", self.item_es_by_en, self.mega_by_norm)
        self.assertEqual(r, "Blastoisita")

    def test_piedra_mega_champions_exclusiva_no_resuelve_a_ciegas(self):
        # Staraptor nunca tuvo una mega real en los juegos principales — es
        # una mega exclusiva de Champions. Sin una fuente real del nombre de
        # su piedra, tiene que quedar sin resolver, no inventado.
        r = bm.resolve_item("Staraptite", self.item_es_by_en, self.mega_by_norm)
        self.assertIsNone(r)

    def test_habilidad_resuelve_a_slug_conocido(self):
        self.assertIn("intimidate", self.abil_slugs)
        self.assertEqual(bm.resolve_ability("Intimidate", self.abil_slugs), "intimidate")

    def test_habilidad_desconocida_no_resuelve(self):
        self.assertIsNone(bm.resolve_ability("Not A Real Ability", self.abil_slugs))


class TestEspecies(unittest.TestCase):
    def setUp(self):
        self.idx = {bm.slug("Kingambit"): 983, bm.slug("Ninetales-Alola"): 38,
                    bm.slug("Floette-Eternal"): 670}

    def test_especie_directa(self):
        self.assertEqual(bm.resolve_species("Kingambit", self.idx), 983)

    def test_forma_regional_antepuesta_en_limitless(self):
        self.assertEqual(bm.resolve_species("Alolan Ninetales", self.idx), 38)

    def test_alias_puntual_forma_especial(self):
        self.assertEqual(bm.resolve_species("Eternal Flower Floette", self.idx), 670)

    def test_especie_no_mapeada_devuelve_none_no_inventa(self):
        self.assertIsNone(bm.resolve_species("Paldean Tauros Aqua Breed", self.idx))


class TestMovimientos(unittest.TestCase):
    def test_resuelve_por_nombre_en_ingles_tal_cual_dex_json(self):
        # validate_data.py acepta un movimiento de meta.json si coincide con
        # dex.json (m["n"]) — el generador no necesita convertir a la clave
        # en español, solo devolver el nombre exacto de dex.json.
        dex = {"moves": {"protect": {"n": "Protect"}, "tailwind": {"n": "Tailwind"}}}
        idx = bm.build_move_index(dex)
        self.assertEqual(bm.resolve_move("protect", idx), "Protect")
        self.assertEqual(bm.resolve_move("TAILWIND", idx), "Tailwind")

    def test_movimiento_no_mapeado_no_rompe(self):
        idx = bm.build_move_index({"moves": {}})
        self.assertIsNone(bm.resolve_move("Water Spout", idx))


class TestAgregacion(unittest.TestCase):
    """Fixture chico pero realista: 3 decklists sintéticos, mismo formato que
    trae la API (verificado contra una respuesta real, architecture.md
    §10.1.1) — sin red, así el test corre siempre igual."""

    def setUp(self):
        self.species_idx = {bm.slug("Kingambit"): 983, bm.slug("Whimsicott"): 547}
        self.item_es_by_en = {bm.slug("Life Orb"): "Vidasfera",
                               bm.slug("Focus Sash"): "Banda Aguante"}
        self.mega_by_norm = {}
        self.move_idx = {bm.slug("Tailwind"): "Tailwind", bm.slug("Sucker Punch"): "Sucker Punch"}
        self.abil_slugs = {"defiant", "prankster"}
        self.teams = [
            [{"name": "Kingambit", "item": "Life Orb", "ability": "Defiant",
              "attacks": ["Sucker Punch"]},
             {"name": "Whimsicott", "item": "Focus Sash", "ability": "Prankster",
              "attacks": ["Tailwind"]}],
            [{"name": "Kingambit", "item": "Life Orb", "ability": "Defiant",
              "attacks": ["Sucker Punch"]},
             {"name": "Whimsicott", "item": "Focus Sash", "ability": "Prankster",
              "attacks": ["Tailwind"]}],
            [{"name": "Kingambit", "item": None, "ability": "Defiant", "attacks": []}],
        ]

    def _agg(self):
        return bm.aggregate(self.teams, self.species_idx, self.item_es_by_en,
                             self.mega_by_norm, self.move_idx, self.abil_slugs)

    def test_usage_es_proporcion_de_equipos_con_esa_especie(self):
        agg = self._agg()
        species = bm.build_species_entries(agg, total_teams=3)
        self.assertAlmostEqual(species["983"]["usage"], 100.0)   # 3 de 3
        self.assertAlmostEqual(species["547"]["usage"], round(2 / 3 * 100, 1))

    def test_hecho_sin_item_no_cuenta_como_item_desconocido(self):
        # el 3er equipo trae Kingambit sin ítem (item=None) — no debería
        # aparecer como "sin resolver", porque no HAY nada que resolver.
        agg = self._agg()
        self.assertNotIn(None, agg["unresolved"]["items"])

    def test_cores_solo_cuenta_pares_dentro_del_mismo_equipo(self):
        agg = self._agg()
        self.assertEqual(agg["pair_count"][(547, 983)], 2)  # aparecen juntos en 2 de 3

    def test_speed_control_majority_con_uso_mayoritario_del_movimiento(self):
        agg = self._agg()
        role, ctl = bm.role_in_core(547, dict(agg["move_count"][547]), agg["team_count"][547])
        self.assertIsNotNone(ctl)
        self.assertEqual(ctl["tool"], "tailwind")
        self.assertAlmostEqual(ctl["pct"], 1.0)

    def test_especie_por_debajo_del_piso_minimo_no_entra_al_snapshot(self):
        agg = self._agg()
        # con MIN_TEAMS_PER_SPECIES=2 y una especie que solo aparece 1 vez
        one_off_idx = dict(self.species_idx)
        agg2 = bm.aggregate([[{"name": "Kingambit", "item": None, "ability": None, "attacks": []}]],
                             one_off_idx, self.item_es_by_en, self.mega_by_norm,
                             self.move_idx, self.abil_slugs)
        species = bm.build_species_entries(agg2, total_teams=1)
        self.assertNotIn("983", species)


if __name__ == "__main__":
    unittest.main(verbosity=2)
