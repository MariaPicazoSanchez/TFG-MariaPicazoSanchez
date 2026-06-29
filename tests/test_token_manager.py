"""
Tests para security/token_manager.py

Cubre: get_api_token con un token file temporal.
"""
import pytest
from pathlib import Path
from unittest.mock import patch


class TestGetApiToken:
    def test_genera_token_nuevo_cuando_no_existe(self, tmp_path):
        token_file = tmp_path / ".api_token"
        with patch("security.token_manager.TOKEN_FILE", token_file):
            from security import token_manager
            import importlib
            importlib.reload(token_manager)
            with patch.object(token_manager, "TOKEN_FILE", token_file):
                token = token_manager.get_api_token()
        assert isinstance(token, str)
        assert len(token) == 64

    def test_token_generado_se_guarda_en_disco(self, tmp_path):
        token_file = tmp_path / ".api_token"
        import security.token_manager as tm
        with patch.object(tm, "TOKEN_FILE", token_file):
            token = tm.get_api_token()
        assert token_file.exists()
        assert token_file.read_text().strip() == token

    def test_token_existente_se_reutiliza(self, tmp_path):
        token_file = tmp_path / ".api_token"
        token_file.write_text("abcdef1234567890" * 4)  # 64 chars
        import security.token_manager as tm
        with patch.object(tm, "TOKEN_FILE", token_file):
            token = tm.get_api_token()
        assert token == "abcdef1234567890" * 4

    def test_token_es_hexadecimal(self, tmp_path):
        token_file = tmp_path / ".api_token"
        import security.token_manager as tm
        with patch.object(tm, "TOKEN_FILE", token_file):
            token = tm.get_api_token()
        int(token, 16)  # no lanza si es hex válido

    def test_segunda_llamada_devuelve_mismo_token(self, tmp_path):
        token_file = tmp_path / ".api_token"
        import security.token_manager as tm
        with patch.object(tm, "TOKEN_FILE", token_file):
            token1 = tm.get_api_token()
            token2 = tm.get_api_token()
        assert token1 == token2
