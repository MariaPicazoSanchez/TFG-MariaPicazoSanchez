"""
Tests para export/map_export.py

Solo testea count_students_by_type, que es pura lógica Python.
add_program_legend y add_export_control requieren folium.Map real → se omiten.
"""
import pytest
import pandas as pd
from export.map_export import count_students_by_type


class TestCountStudentsByType:
    def test_sin_active_names_devuelve_vacio(self):
        dfs = {"Erasmus OUT": pd.DataFrame()}
        result = count_students_by_type(dfs, [])
        assert result == {}

    def test_dfs_no_dict_devuelve_vacio(self):
        result = count_students_by_type(None, ["Erasmus OUT"])
        assert result == {}

    def test_tipo_no_en_dfs_cuenta_cero(self):
        result = count_students_by_type({}, ["Erasmus OUT"])
        assert result == {"Erasmus OUT": 0}

    def test_df_vacio_cuenta_cero(self):
        dfs = {"Erasmus IN": pd.DataFrame({"estudiantes": []})}
        result = count_students_by_type(dfs, ["Erasmus IN"])
        assert result["Erasmus IN"] == 0

    def test_columna_estudiantes_con_listas_de_dicts(self):
        dfs = {
            "Erasmus OUT": pd.DataFrame({
                "estudiantes": [
                    [{"nombre": "Ana"}, {"nombre": "Luis"}],
                    [{"nombre": "Marta"}],
                ]
            })
        }
        result = count_students_by_type(dfs, ["Erasmus OUT"])
        assert result["Erasmus OUT"] == 3

    def test_columna_estudiantes_con_lista_vacia(self):
        dfs = {
            "SICUE OUT": pd.DataFrame({
                "estudiantes": [[], [{"nombre": "Pedro"}]]
            })
        }
        result = count_students_by_type(dfs, ["SICUE OUT"])
        assert result["SICUE OUT"] == 1

    def test_sin_columna_estudiantes_usa_len_df(self):
        dfs = {
            "Erasmus OUT": pd.DataFrame({"lat": [1.0, 2.0, 3.0]})
        }
        result = count_students_by_type(dfs, ["Erasmus OUT"])
        assert result["Erasmus OUT"] == 3

    def test_multiples_tipos(self):
        dfs = {
            "Erasmus OUT": pd.DataFrame({"lat": [1.0, 2.0]}),
            "Erasmus IN":  pd.DataFrame({"lat": [1.0]}),
        }
        result = count_students_by_type(dfs, ["Erasmus OUT", "Erasmus IN"])
        assert result["Erasmus OUT"] == 2
        assert result["Erasmus IN"] == 1

    def test_tipo_con_none_en_df(self):
        dfs = {"Erasmus OUT": None}
        result = count_students_by_type(dfs, ["Erasmus OUT"])
        assert result["Erasmus OUT"] == 0

    def test_columna_estudiantes_con_no_dict_no_cuenta(self):
        # Elementos que no son dict no se cuentan
        dfs = {
            "Erasmus IN": pd.DataFrame({
                "estudiantes": [["string", 42, None], [{"nombre": "Ana"}]]
            })
        }
        result = count_students_by_type(dfs, ["Erasmus IN"])
        assert result["Erasmus IN"] == 1


class TestCountStudentsByTypeExtra:
    """Casos adicionales para aumentar cobertura."""

    def test_columna_estudiantes_con_solo_no_dicts_usa_len(self):
        # Listas sin dicts -> total == 0, fallback usa len(df)
        dfs = {
            "Erasmus OUT": pd.DataFrame({
                "estudiantes": [["solo texto"], ["otro texto"]]
            })
        }
        result = count_students_by_type(dfs, ["Erasmus OUT"])
        # total es 0, fallback usa len(df) = 2
        assert result["Erasmus OUT"] == 2

    def test_multiples_tipos_algunos_ausentes(self):
        dfs = {
            "Erasmus OUT": pd.DataFrame({"lat": [1.0]}),
        }
        result = count_students_by_type(dfs, ["Erasmus OUT", "Erasmus IN", "SICUE OUT"])
        assert result["Erasmus OUT"] == 1
        assert result["Erasmus IN"] == 0
        assert result["SICUE OUT"] == 0

    def test_active_names_con_un_tipo(self):
        dfs = {
            "Erasmus IN": pd.DataFrame({
                "estudiantes": [
                    [{"nombre": "A"}, {"nombre": "B"}]
                ]
            })
        }
        result = count_students_by_type(dfs, ["Erasmus IN"])
        assert result["Erasmus IN"] == 2

    def test_devuelve_ints_no_floats(self):
        dfs = {"Erasmus OUT": pd.DataFrame({"lat": [1.0, 2.0]})}
        result = count_students_by_type(dfs, ["Erasmus OUT"])
        assert isinstance(result["Erasmus OUT"], int)

    def test_dfs_como_lista_devuelve_vacio(self):
        # dfs no es dict -> vacío
        result = count_students_by_type(["no es dict"], ["Erasmus OUT"])
        assert result == {}


class TestMapExportImport:
    """Verifica que el módulo importa y expone la API esperada."""

    def test_importa_map_export(self):
        import export.map_export  # noqa: F401
        assert True

    def test_tiene_count_students_by_type(self):
        from export.map_export import count_students_by_type
        assert callable(count_students_by_type)

    def test_tiene_add_program_legend(self):
        import export.map_export as me
        assert hasattr(me, "add_program_legend")
        assert callable(me.add_program_legend)

    def test_tiene_add_export_control(self):
        import export.map_export as me
        assert hasattr(me, "add_export_control")
        assert callable(me.add_export_control)


class TestCountStudentsByTypeExceptions:
    """Casos que ejercitan los bloques except de count_students_by_type."""

    def test_df_con_empty_que_lanza_devuelve_cero(self):
        """Objeto cuyo .empty lanza excepción -> se captura, total=0."""
        from export.map_export import count_students_by_type
        from unittest.mock import MagicMock, PropertyMock

        bad_df = MagicMock()
        # Hacer que .empty lance excepción
        type(bad_df).empty = PropertyMock(side_effect=RuntimeError("fail"))
        bad_df.__len__ = MagicMock(return_value=0)

        dfs = {"Erasmus OUT": bad_df}
        result = count_students_by_type(dfs, ["Erasmus OUT"])
        assert result["Erasmus OUT"] == 0

    def test_df_con_columns_que_lanza_devuelve_cero(self):
        """Objeto cuyas .columns lanza excepción -> bloque except captura."""
        from export.map_export import count_students_by_type
        from unittest.mock import MagicMock, PropertyMock

        bad_df = MagicMock()
        # empty devuelve False para que no haga continue
        bad_df.empty = False
        # columns lanza excepción
        type(bad_df).columns = PropertyMock(side_effect=RuntimeError("columns fail"))
        bad_df.__len__ = MagicMock(side_effect=TypeError)

        dfs = {"Erasmus IN": bad_df}
        result = count_students_by_type(dfs, ["Erasmus IN"])
        assert result["Erasmus IN"] == 0

    def test_df_sin_columna_estudiantes_len_type_error(self):
        """len(df) lanza TypeError -> total queda en 0."""
        from export.map_export import count_students_by_type
        from unittest.mock import MagicMock, PropertyMock

        bad_df = MagicMock()
        bad_df.empty = False
        # columns no tiene 'estudiantes'
        bad_df.columns = ["lat", "lon"]
        bad_df.__len__ = MagicMock(side_effect=TypeError)

        dfs = {"SICUE OUT": bad_df}
        result = count_students_by_type(dfs, ["SICUE OUT"])
        assert result["SICUE OUT"] == 0
