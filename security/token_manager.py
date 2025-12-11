import secrets
from pathlib import Path

TOKEN_FILE = Path(__file__).parent / ".api_token"


def get_api_token() -> str:
    """
    Devuelve el token de API.
    - Si ya existe .api_token, lo lee.
    - Si no existe, genera uno nuevo, lo guarda y lo devuelve.
    """
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()

    token = secrets.token_hex(32)  # 64 caracteres hex
    TOKEN_FILE.write_text(token)
    return token
