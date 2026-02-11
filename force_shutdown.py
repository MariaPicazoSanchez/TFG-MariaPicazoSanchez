"""
Script de utilidad para forzar el cierre de MovilidadESII.

Usa este script si la aplicación no se cierra correctamente:
1. Cierra todos los navegadores con la aplicación abierta
2. Ejecuta este script
3. Espera 5 segundos

El script creará un archivo de señal que el launcher leerá para cerrarse.
También intentará matar los procesos de Python de Streamlit y Flask.
"""
import os
import subprocess
import time
from pathlib import Path


def get_appdata_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
    return Path(base) / "MovilidadESII"


def main():
    appdata = get_appdata_dir()
    shutdown_file = appdata / ".shutdown"
    
    print("MovilidadESII - Cierre Forzado")
    print("=" * 50)
    print(f"Directorio de datos: {appdata}")
    print()
    
    # Crear archivo de señal
    try:
        shutdown_file.touch()
        print(f"✓ Archivo de señal creado: {shutdown_file}")
    except Exception as e:
        print(f"✗ Error creando archivo de señal: {e}")
        return 1
    
    print()
    print("Esperando 5 segundos para que el launcher cierre gracefully...")
    time.sleep(5)
    
    # Intentar matar procesos de Python relacionados
    if os.name == "nt":
        print()
        print("Buscando procesos de Python relacionados con la aplicación...")
        try:
            # Buscar procesos de Python ejecutando streamlit o api.py
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split("\n")[1:]  # Skip header
                if lines and lines[0]:
                    print(f"Encontrados {len(lines)} procesos de python.exe")
                    print()
                    print("Para matar manualmente todos los procesos de Python, ejecuta:")
                    print('  taskkill /F /IM python.exe')
                    print()
                    print("ADVERTENCIA: Esto cerrará TODOS los procesos de Python en tu sistema.")
                    print("Solo hazlo si estás seguro de que no hay otros scripts de Python importantes corriendo.")
                else:
                    print("No se encontraron procesos de python.exe")
            
        except Exception as e:
            print(f"Error buscando procesos: {e}")
    
    # Limpiar archivo shutdown
    try:
        if shutdown_file.exists():
            shutdown_file.unlink()
            print()
            print("✓ Archivo de señal limpiado")
    except Exception:
        pass
    
    print()
    print("=" * 50)
    print("Proceso completado.")
    print()
    print("Si la aplicación sigue sin cerrarse:")
    print("1. Abre el Administrador de Tareas (Ctrl+Shift+Esc)")
    print("2. Busca procesos llamados 'python.exe' o 'MovilidadESII.exe'")
    print("3. Haz clic derecho → Finalizar tarea")
    print()
    input("Presiona Enter para salir...")
    return 0


if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n\nCancelado por el usuario.")
        exit(1)
