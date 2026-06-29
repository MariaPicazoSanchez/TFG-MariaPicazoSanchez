"""
Tests para persistence/_excel_tables.py

Cubre: normalize_str, _norm_header, _row_is_empty_ws (via mock de ws),
       _find_col_in_ws_by_aliases, _sheet_priority
"""
import pytest
from unittest.mock import MagicMock
from persistence._excel_tables import (
    normalize_str,
    _norm_header,
    _find_col_in_ws_by_aliases,
    _sheet_priority,
)


# ─────────────────────────────────────────────────────────────────────────────
# normalize_str / _norm_header
# ─────────────────────────────────────────────────────────────────────────────

class TestNormHeader:
    def test_minusculas(self):
        assert _norm_header("NOMBRE") == "nombre"

    def test_elimina_acentos(self):
        assert _norm_header("País") == "pais"

    def test_strip_espacios_laterales(self):
        assert _norm_header("  email  ") == "email"

    def test_colapsa_espacios_internos(self):
        assert _norm_header("nombre  completo") == "nombre completo"

    def test_none_devuelve_vacio(self):
        assert _norm_header(None) == ""

    def test_string_vacio(self):
        assert _norm_header("") == ""

    def test_tildes_multiples(self):
        assert _norm_header("Código Área") == "codigo area"

    def test_ñ_se_normaliza(self):
        result = _norm_header("España")
        assert result == "espana"


class TestNormalizeStr:
    def test_equivale_a_norm_header(self):
        casos = ["Email", "País", "  Ciudad  ", "Universidad Origen"]
        for s in casos:
            assert normalize_str(s) == _norm_header(s)

    def test_string_numerico(self):
        assert normalize_str("123") == "123"


# ─────────────────────────────────────────────────────────────────────────────
# _find_col_in_ws_by_aliases
# ─────────────────────────────────────────────────────────────────────────────

class TestFindColInWsByAliases:
    def test_encuentra_alias_exacto(self):
        norm_map = {"email": 3, "nombre": 1}
        result = _find_col_in_ws_by_aliases(norm_map, ["email"])
        assert result == 3

    def test_primer_alias_que_coincide(self):
        norm_map = {"correo": 2, "email": 3}
        result = _find_col_in_ws_by_aliases(norm_map, ["email", "correo"])
        assert result == 3

    def test_ninguno_coincide_devuelve_none(self):
        norm_map = {"nombre": 1}
        result = _find_col_in_ws_by_aliases(norm_map, ["email", "correo"])
        assert result is None

    def test_alias_con_acento_normalizado(self):
        # El mapa tiene la clave ya normalizada (sin acento)
        norm_map = {"pais": 4}
        result = _find_col_in_ws_by_aliases(norm_map, ["País"])
        assert result == 4

    def test_lista_vacia_devuelve_none(self):
        norm_map = {"email": 3}
        result = _find_col_in_ws_by_aliases(norm_map, [])
        assert result is None

    def test_mapa_vacio_devuelve_none(self):
        result = _find_col_in_ws_by_aliases({}, ["email"])
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# _sheet_priority
# ─────────────────────────────────────────────────────────────────────────────

class TestSheetPriority:
    def test_hoja_llamada_curso_tiene_prioridad(self):
        p_curso = _sheet_priority("Curso")
        p_otro = _sheet_priority("2023/2024")
        assert p_curso < p_otro

    def test_hojas_no_curso_orden_alfabetico_normalizado(self):
        p_a = _sheet_priority("Datos A")
        p_b = _sheet_priority("Datos B")
        assert p_a < p_b

    def test_curso_case_insensitive(self):
        p1 = _sheet_priority("CURSO")
        p2 = _sheet_priority("curso")
        assert p1 == p2


# ─────────────────────────────────────────────────────────────────────────────
# _row_is_empty_ws (via mock de worksheet openpyxl)
# ─────────────────────────────────────────────────────────────────────────────

class TestRowIsEmptyWs:
    def _make_ws(self, values: list):
        """Crea un mock de worksheet donde la fila 1 tiene `values`."""
        from persistence._excel_tables import _row_is_empty_ws
        ws = MagicMock()
        ws.max_column = len(values)

        def cell_side_effect(row, column):
            cell = MagicMock()
            cell.value = values[column - 1]
            return cell

        ws.cell.side_effect = cell_side_effect
        return ws

    def test_fila_completamente_vacia(self):
        from persistence._excel_tables import _row_is_empty_ws
        ws = self._make_ws([None, None, None])
        assert _row_is_empty_ws(ws, 1) is True

    def test_fila_con_espacios_en_blanco(self):
        from persistence._excel_tables import _row_is_empty_ws
        ws = self._make_ws(["   ", "", None])
        assert _row_is_empty_ws(ws, 1) is True

    def test_fila_con_datos(self):
        from persistence._excel_tables import _row_is_empty_ws
        ws = self._make_ws([None, "valor", None])
        assert _row_is_empty_ws(ws, 1) is False

    def test_fila_con_cero_no_vacia(self):
        from persistence._excel_tables import _row_is_empty_ws
        ws = self._make_ws([0, None])
        assert _row_is_empty_ws(ws, 1) is False


# ─────────────────────────────────────────────────────────────────────────────
# _match_header_row
# ─────────────────────────────────────────────────────────────────────────────

class TestMatchHeaderRow:
    """Tests de _match_header_row usando mocks de worksheet."""

    def _make_ws(self, header_values: list):
        ws = MagicMock()
        ws.max_column = len(header_values)

        def cell_side_effect(row, column):
            cell = MagicMock()
            cell.value = header_values[column - 1]
            return cell

        ws.cell.side_effect = cell_side_effect
        return ws

    def test_sin_required_fields_devuelve_none(self):
        from persistence._excel_tables import _match_header_row, MATERIAS_HEADER_ALIASES, MATERIAS_REQUIRED
        ws = self._make_ws(["origen", "firmado"])
        result = _match_header_row(ws, 1, MATERIAS_HEADER_ALIASES, MATERIAS_REQUIRED)
        assert result is None  # falta "asignatura" y "estudiante"

    def test_con_required_fields_devuelve_dict(self):
        from persistence._excel_tables import _match_header_row, STUDENTS_HEADER_ALIASES, STUDENTS_REQUIRED
        # "nombre" es el único campo required
        ws = self._make_ws(["Nombre", "Email", "País"])
        result = _match_header_row(ws, 1, STUDENTS_HEADER_ALIASES, STUDENTS_REQUIRED)
        assert result is not None
        assert "nombre" in result

    def test_cabecera_vacia_devuelve_none(self):
        from persistence._excel_tables import _match_header_row, STUDENTS_HEADER_ALIASES, STUDENTS_REQUIRED
        ws = self._make_ws([None, None])
        result = _match_header_row(ws, 1, STUDENTS_HEADER_ALIASES, STUDENTS_REQUIRED)
        assert result is None

    def test_detecta_multiples_campos(self):
        from persistence._excel_tables import _match_header_row, STUDENTS_HEADER_ALIASES, STUDENTS_REQUIRED
        ws = self._make_ws(["nombre", "email", "país", "ciudad"])
        result = _match_header_row(ws, 1, STUDENTS_HEADER_ALIASES, STUDENTS_REQUIRED)
        assert result is not None
        assert "nombre" in result
        assert "email" in result
        assert "pais" in result
        assert "ciudad" in result

    def test_alias_normalizado(self):
        from persistence._excel_tables import _match_header_row, STUDENTS_HEADER_ALIASES, STUDENTS_REQUIRED
        # "Correo Electrónico" debe mapear a "email"
        ws = self._make_ws(["nombre", "Correo Electrónico"])
        result = _match_header_row(ws, 1, STUDENTS_HEADER_ALIASES, STUDENTS_REQUIRED)
        assert result is not None
        assert "email" in result


# ─────────────────────────────────────────────────────────────────────────────
# _iter_sheets_preferred
# ─────────────────────────────────────────────────────────────────────────────

class TestIterSheetsPreferred:
    def test_hoja_curso_primero(self):
        from persistence._excel_tables import _iter_sheets_preferred

        ws_curso = MagicMock()
        ws_curso.title = "Curso"
        ws_otro = MagicMock()
        ws_otro.title = "2023/2024"
        ws_otro2 = MagicMock()
        ws_otro2.title = "AAAA"

        wb = MagicMock()
        wb.worksheets = [ws_otro, ws_otro2, ws_curso]

        result = list(_iter_sheets_preferred(wb))
        assert result[0].title == "Curso"

    def test_orden_alfabetico_el_resto(self):
        from persistence._excel_tables import _iter_sheets_preferred

        ws_b = MagicMock(); ws_b.title = "Beta"
        ws_a = MagicMock(); ws_a.title = "Alfa"

        wb = MagicMock()
        wb.worksheets = [ws_b, ws_a]

        result = list(_iter_sheets_preferred(wb))
        assert result[0].title == "Alfa"
        assert result[1].title == "Beta"


# ─────────────────────────────────────────────────────────────────────────────
# _build_header_maps_from_ws
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildHeaderMapsFromWs:
    def _make_ws(self, row_values: list):
        ws = MagicMock()
        ws.max_column = len(row_values)

        def cell_side_effect(row, column):
            cell = MagicMock()
            cell.value = row_values[column - 1]
            return cell

        ws.cell.side_effect = cell_side_effect
        return ws

    def test_devuelve_dos_dicts(self):
        from persistence._excel_tables import _build_header_maps_from_ws
        ws = self._make_ws(["Nombre", "Email"])
        norm_to_col, raw_headers = _build_header_maps_from_ws(ws, 0)
        assert isinstance(norm_to_col, dict)
        assert isinstance(raw_headers, dict)

    def test_norm_to_col_normaliza_claves(self):
        from persistence._excel_tables import _build_header_maps_from_ws
        ws = self._make_ws(["País", "Ciudad"])
        norm_to_col, _ = _build_header_maps_from_ws(ws, 0)
        assert "pais" in norm_to_col
        assert "ciudad" in norm_to_col

    def test_raw_headers_preserva_original(self):
        from persistence._excel_tables import _build_header_maps_from_ws
        ws = self._make_ws(["Nombre Completo", "E-Mail"])
        _, raw_headers = _build_header_maps_from_ws(ws, 0)
        assert raw_headers[1] == "Nombre Completo"
        assert raw_headers[2] == "E-Mail"

    def test_celda_none_ignorada(self):
        from persistence._excel_tables import _build_header_maps_from_ws
        ws = self._make_ws([None, "Ciudad", None])
        norm_to_col, raw_headers = _build_header_maps_from_ws(ws, 0)
        assert "ciudad" in norm_to_col
        # None no debe estar en raw_headers
        assert 1 not in raw_headers

    def test_celda_vacia_ignorada(self):
        from persistence._excel_tables import _build_header_maps_from_ws
        ws = self._make_ws(["", "Email"])
        norm_to_col, raw_headers = _build_header_maps_from_ws(ws, 0)
        assert "" not in norm_to_col
        assert "email" in norm_to_col


# ─────────────────────────────────────────────────────────────────────────────
# TableInfo dataclass
# ─────────────────────────────────────────────────────────────────────────────

class TestTableInfo:
    def test_crea_instancia(self):
        from persistence._excel_tables import TableInfo
        ti = TableInfo(
            sheet_name="Hoja1",
            header_row=1,
            data_start=2,
            data_end=10,
            cols={"nombre": 1, "email": 2},
        )
        assert ti.sheet_name == "Hoja1"
        assert ti.header_row == 1
        assert ti.data_start == 2
        assert ti.data_end == 10
        assert ti.cols["nombre"] == 1

    def test_campos_accesibles(self):
        from persistence._excel_tables import TableInfo
        ti = TableInfo("s", 3, 4, 8, {"a": 1})
        assert ti.data_end - ti.data_start == 4  # 8-4=4 filas de datos
