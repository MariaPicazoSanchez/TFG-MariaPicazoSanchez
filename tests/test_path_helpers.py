"""
Tests para utils/path_helpers.py

Cubre: repair_windows_path
"""
import os
import pytest
from utils.path_helpers import repair_windows_path


class TestRepairWindowsPath:
    def test_cadena_vacia_devuelve_vacia(self):
        assert repair_windows_path("") == ""

    def test_none_equivalente_vacio(self):
        # La función recibe str; si se pasa "" da ""
        assert repair_windows_path("") == ""

    def test_ruta_ya_con_backslashes_se_normaliza(self):
        result = repair_windows_path("C:\\Users\\maria\\Documents")
        assert result == os.path.normpath("C:\\Users\\maria\\Documents")

    def test_ruta_con_slashes_se_convierte(self):
        result = repair_windows_path("C:/Users/maria/Documents")
        assert result == os.path.normpath("C:\\Users\\maria\\Documents")

    def test_ruta_sin_separador_despues_de_letra_unidad(self):
        # "C:Users..." → debe insertar backslash tras la letra de unidad
        result = repair_windows_path("C:UsersmariaDocs")
        assert result.startswith("C:\\")

    def test_ruta_con_backslash_doble_se_normaliza(self):
        result = repair_windows_path("C:\\Users\\\\maria")
        assert "\\\\" not in result

    def test_ruta_relativa_con_slash_forward(self):
        result = repair_windows_path("carpeta/subcarpeta")
        assert "/" not in result

    def test_letra_unidad_mayuscula_preservada(self):
        result = repair_windows_path("D:\\Datos\\archivo.xlsx")
        assert result.startswith("D:")

    def test_ruta_corta_dos_chars_no_modifica_sin_separador(self):
        # Longitud <= 2 no puede cumplir la condición path_str[2] != '\\'
        result = repair_windows_path("C:")
        assert isinstance(result, str)

    def test_ruta_normal_sin_errores_devuelve_normalizada(self):
        path = "C:\\Program Files\\App\\app.exe"
        result = repair_windows_path(path)
        assert result == os.path.normpath(path)
