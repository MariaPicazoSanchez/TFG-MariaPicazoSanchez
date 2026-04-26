# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# pystray carga su backend específico de SO (pystray._win32 en Windows) de forma
# dinámica vía importlib, así que PyInstaller no lo detecta por análisis estático.
# Recolectamos todos sus submódulos + los de PIL para que la bandeja del sistema
# funcione en el bundle (MSIX / Inno) aunque solo se importen condicionalmente.
_hidden = collect_submodules('pystray') + collect_submodules('PIL')
_datas  = collect_data_files('pystray') + collect_data_files('PIL')

# El código del launcher abre MovilidadESII.ico desde `sys.executable.parent`
# para pintar el icono de bandeja; Inno lo copia por su cuenta, pero MSIX no.
# Incluirlo como data asegura que esté junto al EXE en cualquier empaquetado.
_datas.append(('install_root/MovilidadESII.ico', '.'))

a = Analysis(
    ['launcher_system.py'],
    pathex=[],
    binaries=[],
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MovilidadESII',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['install_root\\MovilidadESII.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MovilidadESII',
)
