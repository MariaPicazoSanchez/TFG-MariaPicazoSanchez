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
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("movilidad_launcher")

# Debe coincidir con <Application Id="..."> del AppxManifest.xml.
APP_ID = "MovilidadESII"
SHORTCUT_NAME = "MovilidadESII.lnk"
ICON_FILENAME = "MovilidadESII.ico"
_APPMODEL_ERROR_NO_PACKAGE = 15700
_ERROR_INSUFFICIENT_BUFFER = 122
_CREATE_NO_WINDOW = 0x08000000


def _find_app_icon(hint: Path | None) -> Path | None:
    """
    Localiza MovilidadESII.ico probando primero la pista del caller y luego
    rutas habituales de PyInstaller. En PyInstaller 6.x onedir los datafiles
    viven en `_internal/` junto al EXE, no en el mismo directorio que él, así
    que un único candidato no basta.
    """
    candidates: list[Path] = []
    if hint is not None:
        candidates.append(hint)
    exe_dir = Path(sys.executable).parent
    candidates.append(exe_dir / ICON_FILENAME)
    candidates.append(exe_dir / "_internal" / ICON_FILENAME)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / ICON_FILENAME)
    for c in candidates:
        try:
            if c.exists():
                return c
        except OSError:
            continue
    return None


def _devirtualize_msix_path(p: Path, pfn: str) -> Path:
    """
    Traduce una ruta bajo %LOCALAPPDATA% (la vista *virtual* que ve el proceso
    empaquetado) a su ruta *física* real dentro del contenedor MSIX.

    Dentro de un paquete MSIX, las escrituras a %LOCALAPPDATA% se redirigen de
    forma transparente a:
        %LOCALAPPDATA%\\Packages\\<PFN>\\LocalCache\\Local
    El proceso empaquetado sigue *viendo* la ruta original (p. ej.
    C:\\Users\\x\\AppData\\Local\\MovilidadESII), pero el fichero acaba en el
    contenedor. Un acceso directo (.lnk) que guarde la ruta virtual en su
    IconLocation no funciona, porque Explorer corre FUERA del paquete y no ve
    esa redirección: encuentra una ruta inexistente y pinta un icono en blanco.

    Esta función devuelve la ruta del contenedor, que sí es legible desde fuera
    y además es estable entre actualizaciones de la Store (a diferencia de la
    ruta de instalación del paquete, que incluye versión + hash).
    """
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return p
    local_root = Path(local)
    # Si ya apunta dentro del contenedor, no la toques.
    if pfn in p.parts and "Packages" in p.parts:
        return p
    try:
        rel = p.relative_to(local_root)
    except ValueError:
        return p  # No está bajo %LOCALAPPDATA%: la redirección no aplica.
    return local_root / "Packages" / pfn / "LocalCache" / "Local" / rel


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
        # v3: la IconLocation ahora apunta a la ruta física del contenedor MSIX
        # (antes guardaba la ruta virtual de %LOCALAPPDATA%, que Explorer no ve y
        # mostraba un icono en blanco). Subimos la versión para que las
        # instalaciones existentes regeneren el acceso directo con el icono ya
        # corregido.
        marker = marker_dir / ".desktop_shortcut_msix_v3"
        if marker.exists():
            return
    except OSError as exc:
        logger.debug("No se pudo preparar marcador de shortcut: %s", exc)
        return

    aumid = f"{pfn}!{APP_ID}"
    icon_line = ""
    resolved_icon = _find_app_icon(icon_path)
    if resolved_icon is not None:
        # Copiamos el .ico a marker_dir (LocalAppData) y apuntamos ahí la
        # IconLocation: la ruta de instalación de un paquete MSIX cambia en
        # cada actualización (versión + hash en WindowsApps\...), lo que
        # rompería un IconLocation que apuntase dentro del propio paquete.
        # El .lnk lo lee Explorer (FUERA del paquete), así que IconLocation debe
        # ser una ruta física real, no la vista virtual de %LOCALAPPDATA%. La
        # redirección de MSIX no es uniforme (p. ej. el token de la API acaba en
        # la ruta sin redirigir, pero los datos del launcher van al contenedor),
        # así que no nos fiamos de ella: copiamos al contenedor y VERIFICAMOS.
        # La carpeta del contenedor es además estable entre actualizaciones de la
        # Store, a diferencia de la ruta de instalación (versión + hash).
        persistent_virtual = marker_dir / ICON_FILENAME
        persistent_real = _devirtualize_msix_path(persistent_virtual, pfn)
        target_icon = resolved_icon  # último recurso: icono dentro del paquete
        try:
            persistent_virtual.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resolved_icon, persistent_virtual)
            if persistent_real.exists():
                # La escritura virtual se redirigió al contenedor (caso normal).
                target_icon = persistent_real
            else:
                # El runtime no redirigió como esperábamos: copia directa a la
                # ruta real del contenedor.
                persistent_real.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(resolved_icon, persistent_real)
                if persistent_real.exists():
                    target_icon = persistent_real
        except OSError as exc:
            logger.debug("No se pudo persistir el icono del shortcut: %s", exc)
        # Las comillas dobles en PowerShell permiten rutas con caracteres
        # especiales; escapamos comillas dobles del path con backtick.
        safe_icon = str(target_icon).replace('"', '`"')
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
