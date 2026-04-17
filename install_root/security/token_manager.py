import secrets
from pathlib import Path

# Usar AppData Local para MSIX (y para desarrollo también)
# En MSIX, __file__ apunta a una carpeta de solo lectura
TOKEN_FILE = Path.home() / "AppData" / "Local" / "MaraPicazoSchez.MovilidadESII" / ".api_token"
TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)


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
