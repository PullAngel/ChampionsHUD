#!/usr/bin/env python3
"""
Contrato de los proveedores de sprites (build_sprite_index.py).

Bulbagarden es una wiki de la comunidad: puede cambiar la convención de
nombres, renombrar las categorías, o dejar de publicar los sprites de
Champions. El plan de contingencia es que cambiar de fuente sea escribir una
función, sin tocar nada de lo que sigue río abajo (descarga, huella, formato
del índice que lee SpriteMatcher.kt).

Estos tests blindan ese contrato: los dos proveedores tienen que interpretar
los MISMOS nombres de la MISMA manera. Si divergen, el índice cambia según de
dónde salió — y ahí la contingencia deja de ser una contingencia.

Se corren solos con `node tests/run.js`.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import build_sprite_index as bsi  # noqa: E402


class TestNombresDeBulbagarden(unittest.TestCase):
    """`parse()` — títulos de archivo de la wiki."""

    def test_sin_forma_ni_variocolor(self):
        self.assertEqual(bsi.parse("File:Menu CP 0003.png", False), (3, "", "0003", False))

    def test_variocolor_sin_forma(self):
        # El sufijo « shiny» va al FINAL, no al principio. Cuando el patrón lo
        # esperaba adelante descartaba en silencio dos tercios de la categoría
        # (documentado en el comentario de NAME_RE).
        self.assertEqual(bsi.parse("File:Menu CP 0003 shiny.png", False),
                         (3, "", "0003-shiny", True))

    def test_forma_en_minusculas(self):
        # Normalizado a propósito: es la única forma que el proveedor de
        # carpeta puede recuperar, así que es lo que hace que las dos fuentes
        # produzcan un índice idéntico.
        self.assertEqual(bsi.parse("File:Menu CP 0003-Mega.png", False)[1], "mega")

    def test_forma_con_espacios_y_variocolor(self):
        self.assertEqual(bsi.parse("File:Menu CP 0128-Paldea Aqua shiny.png", False),
                         (128, "paldea aqua", "0128-paldea-aqua-shiny", True))

    def test_nombre_que_no_cuadra_devuelve_none(self):
        # Tiene que devolver None, no adivinar: un nombre no reconocido se
        # reporta, no se mete en el índice con datos inventados.
        self.assertIsNone(bsi.parse("File:Cualquier otra cosa.png", False))


class TestNombresDeCarpeta(unittest.TestCase):
    """`parse_nombre_carpeta()` — el fondo de red, sin depender de ningún sitio."""

    def test_sin_forma_ni_variocolor(self):
        self.assertEqual(bsi.parse_nombre_carpeta("0003"), (3, "", False))

    def test_variocolor_sin_forma_no_se_confunde_con_una_forma(self):
        # El bug que apareció al escribir este proveedor: con un solo regex de
        # dos grupos opcionales, "0003-shiny" se leía como «forma shiny, NO
        # variocolor». Medido en la corrida real: 567 "normales" y 151
        # variocolor, cuando la división verdadera es 359/359.
        self.assertEqual(bsi.parse_nombre_carpeta("0003-shiny"), (3, "", True))

    def test_forma_y_variocolor_juntos(self):
        self.assertEqual(bsi.parse_nombre_carpeta("0128-paldea-aqua-shiny"),
                         (128, "paldea aqua", True))

    def test_nombre_que_no_cuadra_devuelve_none(self):
        self.assertIsNone(bsi.parse_nombre_carpeta("no-empieza-con-numero"))


class TestLosDosProveedoresCoinciden(unittest.TestCase):
    """
    El contrato de contingencia, en un solo test.

    Para el mismo sprite, las dos fuentes tienen que producir el mismo
    (dex, forma, variocolor). Si esto falla, cambiar de fuente cambia el
    artefacto y la contingencia no sirve.
    """

    CASOS = [
        ("File:Menu CP 0003.png", "0003"),
        ("File:Menu CP 0003 shiny.png", "0003-shiny"),
        ("File:Menu CP 0003-Mega.png", "0003-mega"),
        ("File:Menu CP 0003-Mega shiny.png", "0003-mega-shiny"),
        ("File:Menu CP 0128-Paldea Aqua shiny.png", "0128-paldea-aqua-shiny"),
    ]

    def test_mismo_sprite_mismo_resultado_venga_de_donde_venga(self):
        for titulo, slug in self.CASOS:
            with self.subTest(titulo=titulo):
                dex_w, forma_w, slug_w, shiny_w = bsi.parse(titulo, False)
                dex_c, forma_c, shiny_c = bsi.parse_nombre_carpeta(slug)
                self.assertEqual((dex_w, forma_w, shiny_w), (dex_c, forma_c, shiny_c),
                                 f"las dos fuentes discrepan sobre {titulo}")
                self.assertEqual(slug_w, slug,
                                 "el slug de la wiki tiene que ser el nombre de archivo "
                                 "que el proveedor de carpeta espera — así la caché de "
                                 "descargas sirve tal cual como entrada del fondo de red")


class TestRutaSegunOrigen(unittest.TestCase):
    """Un sprite remoto se descarga a la caché; uno local se usa donde está."""

    def test_remoto(self):
        sp = bsi.Sprite("0003", 3, "", False, "https://ejemplo/0003.png")
        self.assertTrue(bsi.es_remoto(sp))
        self.assertEqual(bsi.ruta_de(sp), bsi.OUT_DIR / "0003.png")

    def test_local(self):
        p = Path("/otra/carpeta/0003.png")
        sp = bsi.Sprite("0003", 3, "", False, p)
        self.assertFalse(bsi.es_remoto(sp))
        self.assertEqual(bsi.ruta_de(sp), p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
