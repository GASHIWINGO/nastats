import os

class ThemeManager:
    def __init__(self, app):
        self.app = app
        self.current_theme = "light"

    def apply_theme(self, theme_name: str):
        path = os.path.join("themes", f"{theme_name}.qss")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                qss = f.read()
                self.app.setStyleSheet(qss)
                self.current_theme = theme_name
        else:
            print(f"[ThemeManager] Theme file '{path}' not found.")

    def toggle_theme(self):
        new_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme(new_theme)
