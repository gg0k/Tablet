import os
from PyQt6.QtCore import QStandardPaths

# Constantes Globales
ANCHO_LIENZO = 794  # A4 aprox a 96dpi (210mm)
ALTO_LIENZO = 1123  # A4 aprox a 96dpi (297mm)

class Herramienta:
    LAPIZ = 1
    BORRADOR = 2
    TEXTO = 3
    IMAGEN = 4
    SELECCION = 5
    ZOOM = 6
    MOVER_CANVAS = 7

# Rutas Dinámicas
docs_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
ROOT_DIR = os.path.join(docs_path, "MiEscuelaNotebook")

if not os.path.exists(ROOT_DIR):
    try:
        os.makedirs(ROOT_DIR)
    except OSError as e:
        print(f"Error creando directorio raíz: {e}")