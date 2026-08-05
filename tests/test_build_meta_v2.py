#!/usr/bin/env python3
"""
test_build_meta_v2.py — Champions HUD, cruce experimental con Champions Battle Data

Pruebas de las funciones puras de build_meta_v2.py: parseo del CSV real
(fixture fijo, sacado de una respuesta real de Kingambit) y resolución
contra las tablas canónicas. Sin red -- el fixture ya está guardado acá.

Uso:
    python tests/test_build_meta_v2.py
"""

import sys
import unittest
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent.parent))
import build_meta as bm  # noqa: E402
import build_meta_v2 as bm2  # noqa: E402

# Fixture real: recorte del CSV que devuelve championsbattledata.com para
# Kingambit (Doubles, temporada Current), verificado a mano contra la
# respuesta en vivo el 2026-08-04 antes de escribir el generador.
KINGAMBIT_CSV = """pokemon,column_position,category,rank,name,percentage,stat_up,stat_down,hp_points,attack_points,defense_points,sp_atk_points,sp_def_points,speed_points
Kingambit,2,move,1,Sucker Punch,98.7%,,,,,,,,
Kingambit,2,move,2,Kowtow Cleave,97.0%,,,,,,,,
Kingambit,2,move,3,Iron Head,77.2%,,,,,,,,
Kingambit,2,held_item,1,Black Glasses,35.9%,,,,,,,,
Kingambit,2,held_item,2,Chople Berry,25.3%,,,,,,,,
Kingambit,2,teammate,1,Garchomp,,,,,,,,,
Kingambit,2,teammate,2,Charizard,,,,,,,,,
Kingambit,2,stat_alignment,1,Adamant,82.5%,Attack,Sp. Atk,,,,,,
Kingambit,2,stat_alignment,2,Brave,13.3%,Attack,Speed,,,,,,
Kingambit,2,stat_points,1,,17.2%,,,32,32,0,0,2,0
Kingambit,2,stat_points,2,,9.3%,,,32,32,2,0,0,0
Kingambit,2,ability,1,Defiant,91.9%,,,,,,,,
Kingambit,2,ability,2,Supreme Overlord,7.9%,,,,,,,,
"""


class TestParseCbdCsv(unittest.TestCase):
    def setUp(self):
        self.rows = bm2.parse_cbd_csv(KINGAMBIT_CSV)

    def test_categorias_presentes(self):
        self.assertEqual(set(self.rows.keys()),
                          {"move", "held_item", "teammate", "stat_alignment", "stat_points", "ability"})

    def test_movimientos_en_orden_con_porcentaje_real(self):
        moves = self.rows["move"]
        self.assertEqual([m["name"] for m in moves], ["Sucker Punch", "Kowtow Cleave", "Iron Head"])
        self.assertAlmostEqual(moves[0]["pct"], 98.7)

    def test_naturaleza_trae_stat_up_y_down(self):
        nat = self.rows["stat_alignment"][0]
        self.assertEqual(nat["name"], "Adamant")
        self.assertEqual(nat["statUp"], "Attack")
        self.assertEqual(nat["statDown"], "Sp. Atk")

    def test_reparto_de_evs_es_un_array_de_6(self):
        sp = self.rows["stat_points"][0]
        self.assertEqual(sp["sp"], [32, 32, 0, 0, 2, 0])
        self.assertAlmostEqual(sp["pct"], 17.2)

    def test_teammate_no_tiene_porcentaje_la_fuente_no_lo_da(self):
        tm = self.rows["teammate"][0]
        self.assertIsNone(tm["pct"], "la fuente no publica % de compañero -- no hay que inventarlo")


class TestNoFusionaNaturalezaConReparto(unittest.TestCase):
    """La razón de ser de este chequeo: la fuente mide naturaleza y reparto
    de EVs como DOS distribuciones independientes -- nunca hay que arma
    una fila que diga "naturaleza X con reparto Y, Z% de las veces" porque
    esa combinación conjunta no existe en el dato real."""

    def setUp(self):
        self.rows = bm2.parse_cbd_csv(KINGAMBIT_CSV)

    def test_topNatures_y_topEvSpreads_son_estructuras_separadas(self):
        nats = bm2.cbd_natures(self.rows)
        spreads = bm2.cbd_ev_spreads(self.rows)
        for n in nats:
            self.assertNotIn("sp", n, "una naturaleza no debería traer pegado un reparto de EVs")
        for s in spreads:
            self.assertNotIn("statUp", s, "un reparto de EVs no debería traer pegada una naturaleza")

    def test_topNatures_respeta_el_porcentaje_real(self):
        nats = bm2.cbd_natures(self.rows)
        self.assertEqual(nats[0]["name"], "Adamant")
        self.assertAlmostEqual(nats[0]["pct"], 82.5)

    def test_topEvSpreads_respeta_el_porcentaje_real(self):
        spreads = bm2.cbd_ev_spreads(self.rows)
        self.assertEqual(spreads[0]["sp"], [32, 32, 0, 0, 2, 0])
        self.assertAlmostEqual(spreads[0]["pct"], 17.2)


class TestResolucion(unittest.TestCase):
    def setUp(self):
        self.species_idx = {bm.slug("Kingambit"): 983, bm.slug("Ninetales-Alola"): 38}
        self.move_idx = {bm.slug("Sucker Punch"): "Sucker Punch"}
        self.item_es_by_en = {bm.slug("Black Glasses"): "Anteojos de Sol"}
        self.abil_slugs = {"defiant"}

    def test_resolve_cbd_species_via_showdownId(self):
        num = bm2.resolve_cbd_species({"showdownId": "kingambit", "name": "Kingambit"}, self.species_idx)
        self.assertEqual(num, 983)

    def test_resolve_cbd_species_forma_regional_concatenada(self):
        # CBD entrega el showdownId ya concatenado ("ninetalesalola"), sin
        # guión -- slug() de los dos lados tiene que converger igual.
        num = bm2.resolve_cbd_species({"showdownId": "ninetalesalola", "name": "Ninetales-Alola"}, self.species_idx)
        self.assertEqual(num, 38)

    def test_resolve_cbd_species_desconocida_no_inventa(self):
        num = bm2.resolve_cbd_species({"showdownId": "totalmenteinventado", "name": "Totalmente Inventado"}, self.species_idx)
        self.assertIsNone(num)

    def test_resolve_cbd_moves_separa_resueltos_de_no_resueltos(self):
        rows = {"move": [{"rank": 1, "name": "Sucker Punch", "pct": 98.7},
                          {"rank": 2, "name": "Movimiento Que No Existe", "pct": 1.0}]}
        out, unresolved = bm2.resolve_cbd_moves(rows, self.move_idx)
        self.assertEqual(out, [["Sucker Punch", 98.7]])
        self.assertEqual(unresolved, [["Movimiento Que No Existe", 1.0]])


class TestUrlEncodingDeRutasConEspacios(unittest.TestCase):
    """Bug real, encontrado corriendo contra el sitio en vivo (2026-08-04):
    35 de 236 especies fallaban siempre igual (no era intermitencia de red
    -- reintentar no cambiaba nada). La causa: el índice de CBD trae rutas
    con espacios y puntos sin codificar ("Mr. Rime.csv", "Alolan
    Ninetales.csv", "Aegislash Shield Forme.csv") -- pasadas tal cual a
    curl, rompen la URL. fetch_cbd_csv() las codifica con
    urllib.parse.quote(path, safe="/") antes de pedirlas. Este test fija
    ese comportamiento con los nombres reales que fallaron, para que no
    vuelva a pasar en silencio."""

    def test_rutas_reales_que_fallaban_quedan_bien_codificadas(self):
        casos = [
            "pokemon_champions_assets/battle_data/Doubles/Mr. Rime.csv",
            "pokemon_champions_assets/battle_data/Doubles/Alolan Ninetales.csv",
            "pokemon_champions_assets/battle_data/Doubles/Aegislash Shield Forme.csv",
            "pokemon_champions_assets/battle_data/Doubles/Vivillon Fancy Pattern.csv",
        ]
        for path in casos:
            encoded = quote(path, safe="/")
            self.assertNotIn(" ", encoded, f"quedó un espacio sin codificar en {encoded!r}")
            self.assertIn("/", encoded, "los separadores de carpeta no deberían tocarse")

    def test_rutas_sin_caracteres_especiales_no_cambian(self):
        path = "pokemon_champions_assets/battle_data/Doubles/Kingambit.csv"
        self.assertEqual(quote(path, safe="/"), path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
