import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from themes.theme_manager import ThemeManager
from db_sync import reflect_db_schema

def handle_navigation(self, page_key: str):
    self.content_label.setText(f"Страница: {page_key.capitalize()}")

if __name__ == "__main__":
    app = QApplication(sys.argv)

    reflect_db_schema()

    theme_manager = ThemeManager(app)
    theme_manager.apply_theme("light")
    
    window = MainWindow(theme_manager)
    window.show()

    sys.exit(app.exec())