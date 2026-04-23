"""
Tests para utils/map_processing.py

Cubre: calculate_auto_zoom_bounds, check_dataframes_have_data,
       _filter_students_without_la, filter_out_no_la
"""
import pytest

pd = pytest.importorskip("pandas")

from utils.map_processing import (
    calculate_auto_zoom_bounds,
    check_dataframes_have_data,
    _filter_students_without_la,
    filter_out_no_la,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def df_con_coords():
    return pd.DataFrame({
        "latitud":  [40.0, 48.0, 51.0],
        "longitud": [-3.0,  2.0,  0.0],
        "estudiantes": [[], [], []],
    })


@pytest.fixture
def df_sin_coords():
    return pd.DataFrame({"nombre": ["Ana", "Luis"]})


@pytest.fixture
def dfs_mixto(df_con_coords, df_sin_coords):
    return {
        "Erasmus OUT": df_con_coords,
        "SICUE OUT":   df_sin_coords,
    }


# ─────────────────────────────────────────────────────────────────────────────
# calculate_auto_zoom_bounds
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateAutoZoomBounds:
    def test_devuelve_bounds_correctos(self, df_con_coords):
        bounds = calculate_auto_zoom_bounds({"p": df_con_coords})
        assert bounds is not None
        (min_lat, min_lon), (max_lat, max_lon) = bounds
        assert min_lat < 40.0     # con margen
        assert max_lat > 51.0
        assert min_lon < -3.0
        assert max_lon > 2.0

    def test_un_solo_punto_devuelve_margen_fijo(self):
        df = pd.DataFrame({"latitud": [40.0], "longitud": [-3.0]})
        bounds = calculate_auto_zoom_bounds({"p": df})
        assert bounds is not None
        (min_lat, _), (max_lat, _) = bounds
        # margen fijo de 2.0 cuando min==max
        assert max_lat - min_lat == pytest.approx(4.0)

    def test_sin_datos_devuelve_none(self, df_sin_coords):
        result = calculate_auto_zoom_bounds({"p": df_sin_coords})
        assert result is None

    def test_dict_vacio_devuelve_none(self):
        assert calculate_auto_zoom_bounds({}) is None

    def test_input_no_dict_devuelve_none(self):
        assert calculate_auto_zoom_bounds(None) is None
        assert calculate_auto_zoom_bounds([]) is None

    def test_margen_busqueda_mayor_que_filtro(self, df_con_coords):
        dfs = {"p": df_con_coords}
        (s_min, _), (s_max, _) = calculate_auto_zoom_bounds(dfs, has_search=True)
        (f_min, _), (f_max, _) = calculate_auto_zoom_bounds(dfs, has_search=False)
        assert (s_max - s_min) > (f_max - f_min)

    def test_df_vacio_ignorado(self):
        dfs = {"p": pd.DataFrame()}
        assert calculate_auto_zoom_bounds(dfs) is None

    def test_multiples_programas_combinados(self):
        dfs = {
            "Erasmus OUT": pd.DataFrame({"latitud": [40.0], "longitud": [-3.0]}),
            "Erasmus IN":  pd.DataFrame({"latitud": [51.0], "longitud": [0.0]}),
        }
        bounds = calculate_auto_zoom_bounds(dfs)
        (min_lat, _), (max_lat, _) = bounds
        assert min_lat < 40.0
        assert max_lat > 51.0


# ─────────────────────────────────────────────────────────────────────────────
# check_dataframes_have_data
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckDataframesHaveData:
    def test_con_datos(self, df_con_coords):
        assert check_dataframes_have_data({"p": df_con_coords}) is True

    def test_todos_vacios(self):
        dfs = {"p": pd.DataFrame(), "q": pd.DataFrame()}
        assert check_dataframes_have_data(dfs) is False

    def test_dict_vacio(self):
        assert check_dataframes_have_data({}) is False

    def test_input_invalido(self):
        assert check_dataframes_have_data(None) is False

    def test_mezcla_vacio_y_con_datos(self, df_con_coords):
        dfs = {"p": pd.DataFrame(), "q": df_con_coords}
        assert check_dataframes_have_data(dfs) is True

    def test_df_none_ignorado(self, df_con_coords):
        dfs = {"p": None, "q": df_con_coords}
        assert check_dataframes_have_data(dfs) is True


# ─────────────────────────────────────────────────────────────────────────────
# _filter_students_without_la
# ─────────────────────────────────────────────────────────────────────────────

class TestFilterStudentsWithoutLa:
    def test_sin_la_se_mantiene(self):
        students = [{"nombre": "Ana", "link_LA": None}]
        result = _filter_students_without_la(students)
        assert len(result) == 1

    def test_con_la_se_elimina(self):
        students = [{"nombre": "Ana", "link_LA": "https://la.pdf"}]
        result = _filter_students_without_la(students)
        assert len(result) == 0

    def test_la_vacio_se_mantiene(self):
        students = [{"nombre": "Ana", "link_LA": ""}]
        result = _filter_students_without_la(students)
        assert len(result) == 1

    def test_la_nan_se_mantiene(self):
        students = [{"nombre": "Ana", "link_LA": "nan"}]
        result = _filter_students_without_la(students)
        assert len(result) == 1

    def test_mezcla(self):
        students = [
            {"nombre": "Ana",  "link_LA": "https://la.pdf"},
            {"nombre": "Luis", "link_LA": ""},
            {"nombre": "Mar",  "link_LA": None},
        ]
        result = _filter_students_without_la(students)
        nombres = [s["nombre"] for s in result]
        assert "Ana" not in nombres
        assert "Luis" in nombres
        assert "Mar" in nombres

    def test_lista_vacia(self):
        assert _filter_students_without_la([]) == []

    def test_input_no_lista(self):
        assert _filter_students_without_la(None) == []
        assert _filter_students_without_la("texto") == []


# ─────────────────────────────────────────────────────────────────────────────
# filter_out_no_la
# ─────────────────────────────────────────────────────────────────────────────

class TestFilterOutNoLa:
    def _make_dfs(self, rows):
        """Crea un dict de DataFrames con columna 'estudiantes'."""
        return {"Erasmus OUT": pd.DataFrame(rows)}

    def test_programa_no_existente_devuelve_igual(self):
        dfs = {"Erasmus IN": pd.DataFrame()}
        result = filter_out_no_la(dfs, "Erasmus OUT")
        assert "Erasmus OUT" not in result

    def test_filtra_por_link_la_directo(self):
        df = pd.DataFrame({
            "link_LA": ["https://la.pdf", "", None],
            "nombre":  ["Ana", "Luis", "Mar"],
        })
        dfs = {"Erasmus OUT": df}
        result = filter_out_no_la(dfs, "Erasmus OUT")
        out = result["Erasmus OUT"]
        # Solo los que NO tienen link_LA deben quedar
        assert len(out) == 2
        assert "Ana" not in out["nombre"].tolist()

    def test_filtra_columna_estudiantes(self):
        rows = [
            {"latitud": 40.0, "longitud": -3.0, "estudiantes": [
                {"nombre": "Ana",  "link_LA": "https://la.pdf"},
                {"nombre": "Luis", "link_LA": ""},
            ]},
            {"latitud": 48.0, "longitud": 2.0, "estudiantes": [
                {"nombre": "Mar",  "link_LA": "https://la2.pdf"},
            ]},
        ]
        dfs = self._make_dfs(rows)
        result = filter_out_no_la(dfs, "Erasmus OUT")
        out = result["Erasmus OUT"]
        # Solo la primera fila tiene algún alumno sin LA
        assert len(out) == 1
        assert out.iloc[0]["estudiantes"][0]["nombre"] == "Luis"

    def test_todos_con_la_devuelve_vacio(self):
        rows = [
            {"estudiantes": [{"nombre": "Ana", "link_LA": "https://la.pdf"}]},
        ]
        dfs = self._make_dfs(rows)
        result = filter_out_no_la(dfs, "Erasmus OUT")
        assert result["Erasmus OUT"].empty

    def test_df_vacio_devuelve_vacio(self):
        dfs = {"Erasmus OUT": pd.DataFrame()}
        result = filter_out_no_la(dfs, "Erasmus OUT")
        assert result["Erasmus OUT"].empty
