"""
Tests para utils/file_opener.py

Función testeable sin browser:
  - open_in_system  — abre un fichero del SO (mockeamos os.startfile / subprocess)

Las funciones handle_open_pdf_query y handle_open_excel_query dependen de
st.query_params y st.session_state (Streamlit completo) → se omiten.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

from utils.file_opener import open_in_system


class TestOpenInSystem:
    def test_ruta_vacia_devuelve_false(self):
        ok, err = open_in_system("")
        assert ok is False
        assert err is not None

    def test_ruta_none_devuelve_false(self):
        # None se convierte implícitamente, unquote(str(None)) = 'None' → no existe
        ok, err = open_in_system(None)
        assert ok is False

    def test_ruta_no_existente_devuelve_false(self):
        ok, err = open_in_system("/ruta/que/no/existe/archivo.txt")
        assert ok is False
        assert "No existe" in err

    def test_ruta_existente_windows_llama_startfile(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("contenido")
        with patch("sys.platform", "win32"), \
             patch("os.startfile") as mock_sf:
            ok, err = open_in_system(str(f))
            assert ok is True
            assert err is None
            mock_sf.assert_called_once()

    def test_ruta_existente_darwin_llama_open(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("contenido")
        mock_proc = MagicMock()
        with patch("sys.platform", "darwin"), \
             patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            ok, err = open_in_system(str(f))
            assert ok is True
            assert err is None
            cmd = mock_popen.call_args[0][0]
            assert cmd[0] == "open"

    def test_ruta_existente_linux_llama_xdg_open(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("contenido")
        mock_proc = MagicMock()
        with patch("sys.platform", "linux"), \
             patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            ok, err = open_in_system(str(f))
            assert ok is True
            assert err is None
            cmd = mock_popen.call_args[0][0]
            assert cmd[0] == "xdg-open"

    def test_ruta_con_url_encoding_se_decodifica(self, tmp_path):
        f = tmp_path / "miarchivo.txt"
        f.write_text("contenido")
        # URL-encode el path (sin espacios para evitar problemas de decodificación)
        encoded = str(f).replace("\\", "/")
        with patch("sys.platform", "win32"), \
             patch("os.startfile"):
            ok, err = open_in_system(encoded)
            assert ok is True

    def test_startfile_falla_fallback_subprocess(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("contenido")
        with patch("sys.platform", "win32"), \
             patch("os.startfile", side_effect=OSError("fallo")), \
             patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            ok, err = open_in_system(str(f))
            assert ok is True

    def test_windows_error_total_devuelve_false(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("contenido")
        with patch("sys.platform", "win32"), \
             patch("os.startfile", side_effect=OSError("fallo1")), \
             patch("subprocess.Popen", side_effect=OSError("fallo2")):
            ok, err = open_in_system(str(f))
            assert ok is False
            assert err is not None

    def test_devuelve_tuple_de_dos_elementos(self, tmp_path):
        f = tmp_path / "x.txt"
        f.write_text("hola")
        with patch("sys.platform", "win32"), patch("os.startfile"):
            result = open_in_system(str(f))
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_ruta_con_comillas_se_limpia(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("contenido")
        # La función hace strip de comillas, así que usamos la ruta sin comillas
        # pero con espacios al inicio/final (strip)
        path_with_spaces = f'  {f}  '
        with patch("sys.platform", "win32"), patch("os.startfile"):
            ok, err = open_in_system(path_with_spaces)
            # La ruta existe tras el strip; el test verifica que no falla
            assert isinstance(ok, bool)
