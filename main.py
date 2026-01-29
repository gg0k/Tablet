import sys
from PyQt6.QtWidgets import QApplication
from app_styles import STYLESHEET
from main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    ventana = MainWindow()
    ventana.show()

    sys.exit(app.exec())