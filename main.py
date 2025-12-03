import os
import sys

# Configure environment to force PySide6 usage and block PyQt5 to avoid conflicts
os.environ["QT_API"] = "pyside6"
sys.modules["PyQt5"] = None
sys.modules["PyQt5.QtCore"] = None
sys.modules["PyQt5.QtGui"] = None
sys.modules["PyQt5.QtWidgets"] = None

from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
