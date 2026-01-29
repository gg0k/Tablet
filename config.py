import os
from PyQt6.QtCore import QStandardPaths

# Constantes Globales
ANCHO_LIENZO = 720
ALTO_LIENZO = 1280

class Herramienta:
    LAPIZ = 1
    BORRADOR = 2
    TEXTO = 3
    IMAGEN = 4
    SELECCION = 5
    ZOOM = 6
    MOVER_CANVAS = 7

# --- MEJORA: Rutas Dinámicas ---
# Obtenemos la carpeta de Documentos del usuario de forma segura
docs_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
# Creamos una subcarpeta específica para la app
ROOT_DIR = os.path.join(docs_path, "MiEscuelaNotebook")

# Aseguramos que exista al iniciar
if not os.path.exists(ROOT_DIR):
    try:
        os.makedirs(ROOT_DIR)
    except OSError as e:
        print(f"Error creando directorio raíz: {e}")