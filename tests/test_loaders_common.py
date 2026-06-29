"""
Tests para persistence/loaders/_common.py

Cubre: _parse_coords, haversine_distance, cluster_coordinates,
       _norm_name, _norm_colname, filter_students_with_coords,
       _build_materias_index, _match_student_name, _detect_coords_columns
"""
import pytest
import pandas as pd
from persistence.loaders._common import (
    _parse_coords,
    cluster_coordinates,
    haversine_distance,
    _norm_name,
    _norm_colname,
    filter_students_with_coords,
    _build_materias_index,
    _match_student_name,
    _detect_coords_columns,
)


# ─────────────────────────────────────────────────────────────────────────────
# _parse_coords
# ─────────────────────────────────────────────────────────────────────────────

class TestParseCoords:
    def test_formato_punto(self):
        lat, lon = _parse_coords("40.4168, -3.7038")
        assert lat == pytest.approx(40.4168)
        assert lon == pytest.approx(-3.7038)

    def test_formato_coma_decimal(self):
        lat, lon = _parse_coords("40,4168, -3,7038")
        assert lat == pytest.approx(40.4168)
        assert lon == pytest.approx(-3.7038)

    def test_con_sufijo_auto(self):
        lat, lon = _parse_coords("51.5074, -0.1278 (auto)")
        assert lat == pytest.approx(51.5074)
        assert lon == pytest.approx(-0.1278)

    def test_coordenadas_negativas(self):
        lat, lon = _parse_coords("-33.8688, 151.2093")
        assert lat == pytest.approx(-33.8688)
        assert lon == pytest.approx(151.2093)

    def test_none_devuelve_none(self):
        lat, lon = _parse_coords(None)
        assert lat is None
        assert lon is None

    def test_vacio_devuelve_none(self):
        lat, lon = _parse_coords("")
        assert lat is None
        assert lon is None

    def test_texto_sin_numeros_devuelve_none(self):
        lat, lon = _parse_coords("sin coordenadas")
        assert lat is None
        assert lon is None

    def test_un_solo_numero_devuelve_none(self):
        lat, lon = _parse_coords("40.4168")
        assert lat is None
        assert lon is None

    def test_coordenadas_extremas_validas(self):
        lat, lon = _parse_coords("90.0, 180.0")
        assert lat == pytest.approx(90.0)
        assert lon == pytest.approx(180.0)

    def test_sin_espacio_entre_coordenadas(self):
        lat, lon = _parse_coords("48.8566,2.3522")
        assert lat == pytest.approx(48.8566)
        assert lon == pytest.approx(2.3522)

    def test_no_valida_rangos(self):
        # _parse_coords NO valida rangos, solo extrae números
        lat, lon = _parse_coords("200.0, 400.0")
        assert lat == pytest.approx(200.0)
        assert lon == pytest.approx(400.0)


# ─────────────────────────────────────────────────────────────────────────────
# haversine_distance
# ─────────────────────────────────────────────────────────────────────────────

class TestHaversineDistance:
    def test_mismo_punto_es_cero(self):
        assert haversine_distance(40.0, -3.0, 40.0, -3.0) == pytest.approx(0.0)

    def test_distancia_conocida_madrid_paris(self):
        # Madrid (40.4168, -3.7038) — París (48.8566, 2.3522) ≈ 1054 km
        dist = haversine_distance(40.4168, -3.7038, 48.8566, 2.3522)
        assert 1_050_000 < dist < 1_060_000  # en metros

    def test_distancia_es_simetrica(self):
        d1 = haversine_distance(40.0, -3.0, 48.0, 2.0)
        d2 = haversine_distance(48.0, 2.0, 40.0, -3.0)
        assert d1 == pytest.approx(d2)

    def test_distancia_positiva(self):
        d = haversine_distance(0.0, 0.0, 1.0, 1.0)
        assert d > 0


# ─────────────────────────────────────────────────────────────────────────────
# cluster_coordinates
# ─────────────────────────────────────────────────────────────────────────────

class TestClusterCoordinates:
    def _make_df(self, rows):
        return pd.DataFrame(rows, columns=["latitud", "longitud"])

    def test_df_vacio_devuelve_df_vacio(self):
        df = self._make_df([])
        result = cluster_coordinates(df)
        assert result.empty

    def test_df_sin_columnas_de_coords(self):
        df = pd.DataFrame({"nombre": ["Ana", "Luis"]})
        result = cluster_coordinates(df)
        assert list(result.columns) == ["nombre"]

    def test_puntos_lejanos_no_se_agrupan(self):
        # Madrid y París: > 1000 km → no se agrupan con max_distance_m=150
        df = self._make_df([(40.4168, -3.7038), (48.8566, 2.3522)])
        result = cluster_coordinates(df, max_distance_m=150)
        assert result.iloc[0]["latitud"] == pytest.approx(40.4168)
        assert result.iloc[1]["latitud"] == pytest.approx(48.8566)

    def test_puntos_muy_cercanos_se_agrupan(self):
        # Dos puntos a ~10 m de distancia → se promedian
        df = self._make_df([(40.4168, -3.7038), (40.4169, -3.7038)])
        result = cluster_coordinates(df, max_distance_m=500)
        avg = (40.4168 + 40.4169) / 2
        assert result.iloc[0]["latitud"] == pytest.approx(avg)
        assert result.iloc[1]["latitud"] == pytest.approx(avg)

    def test_nan_no_se_agrupa(self):
        df = self._make_df([(40.4168, -3.7038), (None, None)])
        result = cluster_coordinates(df, max_distance_m=500)
        assert result.iloc[0]["latitud"] == pytest.approx(40.4168)
        assert pd.isna(result.iloc[1]["latitud"])


# ─────────────────────────────────────────────────────────────────────────────
# _norm_name
# ─────────────────────────────────────────────────────────────────────────────

class TestNormName:
    def test_minusculas(self):
        assert _norm_name("ANA") == "ana"

    def test_elimina_acentos(self):
        assert _norm_name("María") == "maria"

    def test_strip_y_colapsa_espacios(self):
        assert _norm_name("  Ana   García  ") == "ana garcia"

    def test_none_devuelve_vacio(self):
        assert _norm_name(None) == ""

    def test_nan_string_devuelve_vacio(self):
        assert _norm_name("nan") == ""

    def test_none_string_devuelve_vacio(self):
        assert _norm_name("None") == ""

    def test_vacio_devuelve_vacio(self):
        assert _norm_name("") == ""

    def test_nombre_normal(self):
        result = _norm_name("Juan Pérez López")
        assert result == "juan perez lopez"

    def test_ñ_normalizada(self):
        result = _norm_name("España")
        assert result == "espana"


# ─────────────────────────────────────────────────────────────────────────────
# _norm_colname
# ─────────────────────────────────────────────────────────────────────────────

class TestNormColname:
    def test_minusculas(self):
        assert _norm_colname("NOMBRE") == "nombre"

    def test_strip_espacios(self):
        assert _norm_colname("  email  ") == "email"

    def test_colapsa_espacios_internos(self):
        assert _norm_colname("nombre   completo") == "nombre completo"

    def test_no_elimina_acentos(self):
        # _norm_colname NO elimina acentos, a diferencia de _norm_name
        result = _norm_colname("País")
        assert "a" in result.lower() or "í" in result or "i" in result

    def test_numeros(self):
        assert _norm_colname("col1") == "col1"


# ─────────────────────────────────────────────────────────────────────────────
# filter_students_with_coords
# ─────────────────────────────────────────────────────────────────────────────

class TestFilterStudentsWithCoords:
    def _make_df(self, rows):
        return pd.DataFrame(rows, columns=["estudiante", "latitud", "longitud"])

    def test_todos_con_coords(self):
        df = self._make_df([("Ana", 40.0, -3.0), ("Luis", 48.0, 2.0)])
        result = filter_students_with_coords(df, "Erasmus OUT")
        assert len(result) == 2

    def test_filtra_filas_sin_coords(self):
        df = self._make_df([("Ana", 40.0, -3.0), ("Luis", None, None)])
        result = filter_students_with_coords(df, "Erasmus OUT")
        assert len(result) == 1
        assert result.iloc[0]["estudiante"] == "Ana"

    def test_mensajes_acumulados_para_alumnos_sin_coords(self):
        df = self._make_df([("Ana", 40.0, -3.0), ("Luis", None, None)])
        msgs = []
        filter_students_with_coords(df, "Erasmus IN", _messages=msgs)
        assert len(msgs) == 1
        assert "Luis" in msgs[0]

    def test_sin_mensajes_cuando_todos_tienen_coords(self):
        df = self._make_df([("Ana", 40.0, -3.0)])
        msgs = []
        filter_students_with_coords(df, "SICUE OUT", _messages=msgs)
        assert msgs == []

    def test_estudiante_nan_no_genera_mensaje(self):
        df = self._make_df([("nan", None, None)])
        msgs = []
        filter_students_with_coords(df, "Erasmus OUT", _messages=msgs)
        assert msgs == []

    def test_df_vacio(self):
        df = self._make_df([])
        result = filter_students_with_coords(df, "Erasmus OUT")
        assert result.empty

    def test_devuelve_copia(self):
        df = self._make_df([("Ana", 40.0, -3.0)])
        result = filter_students_with_coords(df, "Erasmus OUT")
        result.iloc[0, result.columns.get_loc("estudiante")] = "Modificado"
        assert df.iloc[0]["estudiante"] == "Ana"


# ─────────────────────────────────────────────────────────────────────────────
# _build_materias_index / _match_student_name
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildMateriasIndex:
    def test_construye_indice_exacto(self):
        materias = {"Ana García": [], "Luis Pérez": []}
        exact, by_last = _build_materias_index(materias)
        assert "ana garcia" in exact
        assert "luis perez" in exact

    def test_construye_indice_por_ultima_palabra(self):
        materias = {"Ana García": []}
        _, by_last = _build_materias_index(materias)
        assert "garcia" in by_last

    def test_diccionario_vacio(self):
        exact, by_last = _build_materias_index({})
        assert exact == {}
        assert by_last == {}


class TestMatchStudentName:
    def test_coincidencia_exacta(self):
        materias = {"Ana García": [], "Luis Pérez": []}
        exact, by_last = _build_materias_index(materias)
        result = _match_student_name("Ana García", exact, by_last)
        assert result == "Ana García"

    def test_coincidencia_por_apellido(self):
        materias = {"Ana García": []}
        exact, by_last = _build_materias_index(materias)
        result = _match_student_name("Otro García", exact, by_last)
        assert result == "Ana García"

    def test_nombre_vacio_devuelve_none(self):
        exact, by_last = _build_materias_index({"Ana García": []})
        result = _match_student_name("", exact, by_last)
        assert result is None

    def test_nombre_sin_coincidencia_devuelve_none(self):
        exact, by_last = _build_materias_index({"Ana García": []})
        result = _match_student_name("Pedro Martínez", exact, by_last)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# _detect_coords_columns
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectCoordsColumns:
    def test_df_vacio_devuelve_defaults(self):
        df = pd.DataFrame()
        col_pais, col_uni, skip = _detect_coords_columns(df, 0, 1)
        assert col_pais == 0
        assert col_uni == 1
        assert skip is False

    def test_primera_fila_con_cabeceras_universidad_pais(self):
        df = pd.DataFrame([["país", "universidad", "coords"]])
        col_pais, col_uni, skip = _detect_coords_columns(df, 0, 1)
        assert skip is True
        assert col_uni == 1
        assert col_pais == 0

    def test_primera_fila_sin_cabeceras(self):
        df = pd.DataFrame([["España", "Universidad Sevilla", "37.3,-5.9"]])
        col_pais, col_uni, skip = _detect_coords_columns(df, 0, 1)
        assert skip is False

    def test_cabecera_university_en_ingles(self):
        df = pd.DataFrame([["country", "university", "coords"]])
        col_pais, col_uni, skip = _detect_coords_columns(df, 0, 1)
        assert skip is True
        assert col_uni == 1

    def test_solo_cabecera_universidad_sin_pais(self):
        df = pd.DataFrame([["otra", "universidad", "coords"]])
        col_pais, col_uni, skip = _detect_coords_columns(df, 5, 1)
        assert skip is True
        assert col_uni == 1
        # Pais no detectado → usa default
        assert col_pais == 5
