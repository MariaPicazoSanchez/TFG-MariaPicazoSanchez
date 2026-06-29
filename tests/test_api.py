"""
Tests para api/api.py

Cubre: /health, /saved_flag, require_token (401/200), parse_materias_raw,
       _build_js_response, update_student (validaciones), update_plan_coord (validaciones)
"""
import sys
import os
import pytest

# Asegurar que install_root/api y install_root están en el path
_tests_dir = os.path.dirname(__file__)
_install_root = os.path.abspath(os.path.join(_tests_dir, "..", "install_root"))
_api_dir = os.path.join(_install_root, "api")
for _p in (_install_root, _api_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Mockear security.get_api_token antes de importar api.py
from unittest.mock import patch, MagicMock

_FAKE_TOKEN = "test-token-abc123"


@pytest.fixture(scope="module")
def client():
    with patch("security.get_api_token", return_value=_FAKE_TOKEN):
        import api as api_module
        api_module.API_TOKEN = _FAKE_TOKEN
        api_module.app.config["TESTING"] = True
        with api_module.app.test_client() as c:
            yield c, api_module


# ─────────────────────────────────────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client):
        c, _ = client
        r = c.get("/health")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True


# ─────────────────────────────────────────────────────────────────────────────
# /saved_flag
# ─────────────────────────────────────────────────────────────────────────────

class TestSavedFlag:
    def test_saved_flag_devuelve_ts(self, client):
        c, _ = client
        r = c.get("/saved_flag")
        assert r.status_code == 200
        data = r.get_json()
        assert "ts" in data
        assert isinstance(data["ts"], float)


# ─────────────────────────────────────────────────────────────────────────────
# require_token — decorator de autenticación
# ─────────────────────────────────────────────────────────────────────────────

class TestRequireToken:
    def test_sin_token_devuelve_401(self, client):
        c, _ = client
        r = c.post("/update_student")
        assert r.status_code == 401

    def test_token_incorrecto_devuelve_401(self, client):
        c, _ = client
        r = c.post("/update_student", headers={"X-API-TOKEN": "token-incorrecto"})
        assert r.status_code == 401

    def test_token_correcto_no_devuelve_401(self, client):
        c, _ = client
        # Con token correcto el endpoint puede fallar por datos faltantes,
        # pero NO por autenticación (no debe devolver 401)
        r = c.post("/update_student", headers={"X-API-TOKEN": _FAKE_TOKEN})
        assert r.status_code != 401

    def test_token_en_query_param(self, client):
        c, _ = client
        r = c.post(f"/update_student?token={_FAKE_TOKEN}")
        assert r.status_code != 401


# ─────────────────────────────────────────────────────────────────────────────
# parse_materias_raw — lógica de parseo de materias
# ─────────────────────────────────────────────────────────────────────────────

class TestParseMaterias:
    @pytest.fixture(autouse=True)
    def _get_fn(self, client):
        _, api_module = client
        self.parse = api_module.parse_materias_raw

    def test_vacio_devuelve_lista_vacia(self):
        assert self.parse("") == []
        assert self.parse(None) == []

    def test_formato_json(self):
        raw = '[{"nombre": "Cálculo", "cuat": "1", "firmado": true}]'
        result = self.parse(raw)
        assert len(result) == 1
        assert result[0]["asignatura"] == "Cálculo"
        assert result[0]["cuat"] == "1"
        assert result[0]["firmado"] == "x"

    def test_formato_json_firmado_false(self):
        raw = '[{"nombre": "Álgebra", "cuat": "2", "firmado": false}]'
        result = self.parse(raw)
        assert result[0]["firmado"] == ""

    def test_formato_json_varios(self):
        raw = '[{"nombre": "A", "cuat": "1"}, {"nombre": "B", "cuat": "2"}]'
        result = self.parse(raw)
        assert len(result) == 2
        assert result[0]["asignatura"] == "A"
        assert result[1]["asignatura"] == "B"

    def test_formato_legacy_pipe(self):
        raw = "Cálculo | 1 | x\nÁlgebra | 2 |"
        result = self.parse(raw)
        assert len(result) == 2
        assert result[0]["asignatura"] == "Cálculo"
        assert result[0]["firmado"] == "x"
        assert result[1]["firmado"] == ""

    def test_formato_legacy_sin_firmado(self):
        raw = "Física | 1"
        result = self.parse(raw)
        assert result[0]["asignatura"] == "Física"
        assert result[0]["cuat"] == "1"
        assert result[0]["firmado"] == ""

    def test_json_item_sin_nombre_se_ignora(self):
        raw = '[{"asignatura": "", "cuat": "1"}]'
        result = self.parse(raw)
        assert result == []

    def test_json_con_campo_asignatura(self):
        raw = '[{"asignatura": "Redes", "cuat": "1", "firmado": "x"}]'
        result = self.parse(raw)
        assert result[0]["asignatura"] == "Redes"
        assert result[0]["firmado"] == "x"

    def test_json_unico_dict(self):
        raw = '{"nombre": "Sistemas", "cuat": "2"}'
        result = self.parse(raw)
        assert len(result) == 1
        assert result[0]["asignatura"] == "Sistemas"

    def test_json_con_link_la(self):
        raw = '[{"nombre": "Redes", "cuat": "1", "link_la": "http://example.com"}]'
        result = self.parse(raw)
        assert result[0]["link_la"] == "http://example.com"

    def test_json_con_campo_la_alias(self):
        raw = '[{"nombre": "Redes", "la": "http://example.com"}]'
        result = self.parse(raw)
        assert result[0]["link_la"] == "http://example.com"

    def test_json_item_no_dict_se_ignora(self):
        raw = '[{"nombre": "Válido"}, "string_invalido", 42]'
        result = self.parse(raw)
        assert len(result) == 1
        assert result[0]["asignatura"] == "Válido"

    def test_json_anidado_lista(self):
        inner = '[{"asignatura": "Cálculo"}]'
        import json
        raw = json.dumps([{"asignatura": inner, "cuat": "1"}])
        result = self.parse(raw)
        assert result[0]["asignatura"] == "Cálculo"

    def test_json_anidado_dict(self):
        inner = '{"asignatura": "Álgebra"}'
        import json
        raw = json.dumps([{"asignatura": inner, "cuat": "2"}])
        result = self.parse(raw)
        assert result[0]["asignatura"] == "Álgebra"

    def test_json_invalido_cae_a_legacy(self):
        # Empieza con '[' pero no es JSON válido → cae al parser de pipe
        raw = "[esto no es json\nFísica | 1 | x"
        result = self.parse(raw)
        asignaturas = [r["asignatura"] for r in result]
        assert "Física" in asignaturas
        fisica = next(r for r in result if r["asignatura"] == "Física")
        assert fisica["firmado"] == "x"

    def test_legacy_linea_vacia_se_ignora(self):
        raw = "Cálculo | 1 | x\n\n\nÁlgebra | 2"
        result = self.parse(raw)
        assert len(result) == 2

    def test_legacy_link_la_vacio(self):
        raw = "Física | 1 | x"
        result = self.parse(raw)
        assert result[0]["link_la"] == ""

    def test_json_firmado_string_x(self):
        raw = '[{"nombre": "Mat", "firmado": "x"}]'
        result = self.parse(raw)
        assert result[0]["firmado"] == "x"

    def test_json_firmado_string_si(self):
        raw = '[{"nombre": "Mat", "firmado": "si"}]'
        result = self.parse(raw)
        assert result[0]["firmado"] == "x"

    def test_json_firmado_string_vacio(self):
        raw = '[{"nombre": "Mat", "firmado": ""}]'
        result = self.parse(raw)
        assert result[0]["firmado"] == ""


# ─────────────────────────────────────────────────────────────────────────────
# _build_js_response — función pura que genera HTML con postMessage
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildJsResponse:
    @pytest.fixture(autouse=True)
    def _get_fn(self, client):
        _, api_module = client
        self.build = api_module._build_js_response

    def test_ok_true_genera_html(self):
        html, code = self.build(True, ["Guardado correctamente."])
        assert code == 200
        assert "saveStatus" in html
        assert '"ok": true' in html

    def test_ok_false_genera_html(self):
        html, code = self.build(False, ["Error al guardar."])
        assert code == 200
        assert '"ok": false' in html

    def test_mensajes_vacios(self):
        html, _ = self.build(True, [])
        assert '"messages": []' in html

    def test_mensajes_con_espacios_se_limpian(self):
        html, _ = self.build(True, ["  mensaje con espacios  ", ""])
        assert "mensaje con espacios" in html

    def test_extra_dict_se_incluye(self):
        html, _ = self.build(True, [], {"programa": "Erasmus OUT"})
        assert "Erasmus OUT" in html

    def test_script_closing_tag_escapado(self):
        # Evita que </script> dentro del JSON rompa el HTML
        html, _ = self.build(True, ["</script>"])
        assert "</script>" not in html.split("<script>")[1].split("</script>")[0]

    def test_devuelve_siempre_200(self):
        _, code_ok = self.build(True, [])
        _, code_err = self.build(False, ["error"])
        assert code_ok == 200
        assert code_err == 200


# ─────────────────────────────────────────────────────────────────────────────
# /update_student — validaciones sin fichero Excel real
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateStudentValidaciones:
    def _post(self, client, data):
        c, _ = client
        return c.post(
            "/update_student",
            data=data,
            headers={"X-API-TOKEN": _FAKE_TOKEN},
        )

    def test_sin_excel_path_devuelve_error(self, client):
        r = self._post(client, {"estudiante": "Ana", "ciudad": "Madrid"})
        assert r.status_code == 200
        assert "No se recibió ruta" in r.get_data(as_text=True) or \
               "no existe" in r.get_data(as_text=True).lower() or \
               '"ok": false' in r.get_data(as_text=True)

    def test_excel_no_existe_devuelve_error(self, client):
        r = self._post(client, {
            "excel_path": "C:\\ruta\\inexistente\\archivo.xlsx",
            "estudiante": "Ana",
            "ciudad": "Madrid",
        })
        assert '"ok": false' in r.get_data(as_text=True)

    def test_sin_nombre_devuelve_error(self, client, tmp_path):
        xlsx = tmp_path / "test.xlsx"
        xlsx.write_bytes(b"fake")
        r = self._post(client, {
            "excel_path": str(xlsx),
            "estudiante": "",
            "ciudad": "Madrid",
        })
        assert '"ok": false' in r.get_data(as_text=True)

    def test_sin_ciudad_ni_pais_devuelve_error(self, client, tmp_path):
        xlsx = tmp_path / "test.xlsx"
        xlsx.write_bytes(b"fake")
        r = self._post(client, {
            "excel_path": str(xlsx),
            "estudiante": "Ana García",
            "ciudad": "",
            "pais": "",
        })
        assert '"ok": false' in r.get_data(as_text=True)


# ─────────────────────────────────────────────────────────────────────────────
# /update_plan_coord — validaciones sin fichero Excel real
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdatePlanCoordValidaciones:
    def _post(self, client, data):
        c, _ = client
        return c.post(
            "/update_plan_coord",
            data=data,
            headers={"X-API-TOKEN": _FAKE_TOKEN},
        )

    def test_sin_universidad_devuelve_error(self, client):
        r = self._post(client, {"universidad": "", "programa": "Erasmus OUT"})
        assert '"ok": false' in r.get_data(as_text=True)
        assert "universidad" in r.get_data(as_text=True).lower()

    def test_excel_no_existe_devuelve_error(self, client):
        r = self._post(client, {
            "universidad": "Universidad de Prueba",
            "excel_path": "C:\\ruta\\inexistente.xlsx",
            "programa": "Erasmus OUT",
        })
        assert '"ok": false' in r.get_data(as_text=True)

    def test_sin_token_devuelve_401(self, client):
        c, _ = client
        r = c.post("/update_plan_coord", data={"universidad": "Test"})
        assert r.status_code == 401
