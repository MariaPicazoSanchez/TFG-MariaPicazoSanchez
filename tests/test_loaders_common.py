"""
Tests para persistence/loaders/_common.py

Cubre: _parse_coords, haversine_distance, cluster_coordinates
"""
import pytest
import pandas as pd
from persistence.loaders._common import (
    _parse_coords,
    cluster_coordinates,
    haversine_distance,
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
