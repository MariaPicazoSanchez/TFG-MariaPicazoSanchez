"""
Crea un acceso directo en el escritorio del usuario la primera vez que se
arranca la app desde una instalación MSIX (Microsoft Store).

El instalador Inno ya crea su propio acceso directo en el escritorio vía
[Icons] de installer.iss, por lo que este módulo es inerte en ese caso:
solo actúa cuando detecta que el proceso corre dentro de un paquete MSIX
(GetCurrentPackageFamilyName != APPMODEL_ERROR_NO_PACKAGE).
"""

from __future__ import annotations

import ctypes
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("movilidad_launcher")

# Debe coincidir con <Application Id="..."> del AppxManifest.xml.
APP_ID = "MovilidadESII"
SHORTCUT_NAME = "MovilidadESII.lnk"
_APPMODEL_ERROR_NO_PACKAGE = 15700
_ERROR_INSUFFICIENT_BUFFER = 122
_CREATE_NO_WINDOW = 0x08000000


def _get_package_family_name() -> str | None:
    """
    Devuelve el PackageFamilyName si el proceso corre como MSIX, o None.
    Usa GetCurrentPackageFamilyName (Windows 8+); fuera de un paquete
    devuelve APPMODEL_ERROR_NO_PACKAGE (15700).
    """
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_pfn = kernel32.GetCurrentPackageFamilyName
    except (AttributeError, OSError):
        return None

    get_pfn.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_wchar_p]
    get_pfn.restype = ctypes.c_long

    size = ctypes.c_uint32(0)
    rc = get_pfn(ctypes.byref(size), None)
    if rc == _APPMODEL_ERROR_NO_PACKAGE:
        return None
    if rc != _ERROR_INSUFFICIENT_BUFFER and rc != 0:
        return None

    buf = ctypes.create_unicode_buffer(size.value + 1)
    rc = get_pfn(ctypes.byref(size), buf)
    if rc != 0:
        return None
    return buf.value or None


def ensure_msix_desktop_shortcut(
    marker_dir: Path, icon_path: Path | None = None
) -> None:
    """
    Crea un .lnk en el escritorio del usuario la primera vez que la app se
    ejecuta en modo MSIX. En cualquier otro caso (Inno, ejecución desde
    fuentes, SO no-Windows), no hace nada.

    `marker_dir` se usa para dejar un flag tras crear el icono, de modo que
    si el usuario lo borra luego no se recrea automáticamente.
    """
    try:
        pfn = _get_package_family_name()
    except Exception as exc:
        logger.debug("No se pudo determinar PackageFamilyName: %s", exc)
        return
    if not pfn:
        return  # Instalación no-MSIX: Inno ya tiene su propio shortcut.

    try:
        marker_dir.mkdir(parents=True, exist_ok=True)
        marker = marker_dir / ".desktop_shortcut_msix_v1"
        if marker.exists():
            return
    except OSError as exc:
        logger.debug("No se pudo preparar marcador de shortcut: %s", exc)
        return

    aumid = f"{pfn}!{APP_ID}"
    icon_line = ""
    if icon_path and icon_path.exists():
        # Las comillas dobles en PowerShell permiten rutas con caracteres
        # especiales; escapamos comillas dobles del path con backtick.
        safe_icon = str(icon_path).replace('"', '`"')
        icon_line = f'$s.IconLocation = "{safe_icon}";'

    # [Environment]::GetFolderPath('Desktop') resuelve correctamente los
    # escritorios redirigidos a OneDrive.
    ps_script = (
        "$ErrorActionPreference = 'Stop';"
        "$desktop = [Environment]::GetFolderPath('Desktop');"
        f"$lnk = Join-Path $desktop '{SHORTCUT_NAME}';"
        "$ws = New-Object -ComObject WScript.Shell;"
        "$s = $ws.CreateShortcut($lnk);"
        "$s.TargetPath = 'explorer.exe';"
        f"$s.Arguments = 'shell:AppsFolder\\{aumid}';"
        f"{icon_line}"
        "$s.Description = 'MovilidadESII';"
        "$s.Save();"
    )

    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            creationflags=_CREATE_NO_WINDOW,
            timeout=15,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        logger.warning("Fallo creando shortcut MSIX (rc=%s): %s", exc.returncode, stderr)
        return
    except Exception as exc:
        logger.warning("Fallo creando shortcut MSIX: %s", exc)
        return

    try:
        marker.touch()
    except OSError:
        pass
    logger.info("Shortcut MSIX creado en escritorio (AUMID=%s).", aumid)
