import json
import os
from typing import Dict, Iterable, Tuple

from PyQt5 import QtCore

THEME_CATALOG: Dict[str, Dict[str, str]] = {
    "dark": {
        "label": "暗色",
        "background": "#1e1e1e",
        "foreground": "#ffffff",
        "editorBackground": "#1e1e1e",
        "editorForeground": "#ffffff",
        "lineNumberBackground": "#252526",
        "lineNumberForeground": "#858585",
        "selection": "#264f78",
        "accent": "#0e639c",
        "panelBackground": "#252526",
        "outputForeground": "#ffffff",
        "originalBackground": "#5a1f1a",
        "polishedBackground": "#094124",
        "buttonBackground": "#3a3d41",
        "buttonForeground": "#ffffff",
        "borderColor": "#3c3c3c",
        "overlayBackground": "rgba(0, 0, 0, 0.72)",
        "mutedForeground": "#9c9c9c",
        "titleBarBackground": "#2d2d30",
        "titleBarForeground": "#ffffff",
        "sidebarBackground": "#252526",
        "sidebarForeground": "#ffffff",
        "listActiveSelectionBackground": "#094771",
        "listActiveSelectionForeground": "#ffffff",
        "inputBackground": "#3c3c3c",
        "inputBorder": "#5a5a5a",
        "inputForeground": "#ffffff",
        "focusBorder": "#007acc",
        "buttonHoverBackground": "#1177bb",
        "buttonActiveBackground": "#0d5a9a",
    },
    "light": {
        "label": "亮色",
        "background": "#ffffff",
        "foreground": "#000000",
        "editorBackground": "#ffffff",
        "editorForeground": "#000000",
        "lineNumberBackground": "#f3f3f3",
        "lineNumberForeground": "#616161",
        "selection": "#add6ff",
        "accent": "#0e639c",
        "panelBackground": "#f3f3f3",
        "outputForeground": "#000000",
        "originalBackground": "#ffe4e1",
        "polishedBackground": "#e5f7ef",
        "buttonBackground": "#e1e4e8",
        "buttonForeground": "#000000",
        "borderColor": "#d4d4d4",
        "overlayBackground": "rgba(255, 255, 255, 0.72)",
        "mutedForeground": "#707070",
        "titleBarBackground": "#f3f3f3",
        "titleBarForeground": "#000000",
        "sidebarBackground": "#f8f8f8",
        "sidebarForeground": "#000000",
        "listActiveSelectionBackground": "#0078d4",
        "listActiveSelectionForeground": "#ffffff",
        "inputBackground": "#ffffff",
        "inputBorder": "#cccccc",
        "inputForeground": "#000000",
        "focusBorder": "#0078d4",
        "buttonHoverBackground": "#d0d7de",
        "buttonActiveBackground": "#b1bac4",
    },
    "teal": {
        "label": "暗青色",
        "background": "#011627",
        "foreground": "#ffffff",
        "editorBackground": "#011627",
        "editorForeground": "#ffffff",
        "lineNumberBackground": "#012840",
        "lineNumberForeground": "#4c8f9d",
        "selection": "#144f71",
        "accent": "#0db9d7",
        "panelBackground": "#012840",
        "outputForeground": "#ffffff",
        "originalBackground": "#3b1e35",
        "polishedBackground": "#0b3d31",
        "buttonBackground": "#024d63",
        "buttonForeground": "#ffffff",
        "borderColor": "#02526f",
        "overlayBackground": "rgba(1, 22, 39, 0.82)",
        "mutedForeground": "#6fb7c7",
        "titleBarBackground": "#012840",
        "titleBarForeground": "#ffffff",
        "sidebarBackground": "#012840",
        "sidebarForeground": "#ffffff",
        "listActiveSelectionBackground": "#144f71",
        "listActiveSelectionForeground": "#ffffff",
        "inputBackground": "#012840",
        "inputBorder": "#02526f",
        "inputForeground": "#ffffff",
        "focusBorder": "#0db9d7",
        "buttonHoverBackground": "#0369a1",
        "buttonActiveBackground": "#0284c7",
    },
    "eyeCare": {
        "label": "护眼",
        "background": "#e7f4ea",
        "foreground": "#0b1f10",
        "editorBackground": "#e7f4ea",
        "editorForeground": "#0b1f10",
        "lineNumberBackground": "#ddefe3",
        "lineNumberForeground": "#5f7b68",
        "selection": "#b7d8c7",
        "accent": "#2f7a5f",
        "panelBackground": "#ddefe3",
        "outputForeground": "#0b1f10",
        "originalBackground": "#f6efe8",
        "polishedBackground": "#d8f2de",
        "buttonBackground": "#d0e9d6",
        "buttonForeground": "#0b1f10",
        "borderColor": "#bcd6c5",
        "overlayBackground": "rgba(231, 244, 234, 0.72)",
        "mutedForeground": "#5f7b68",
        "titleBarBackground": "#ddefe3",
        "titleBarForeground": "#0b1f10",
        "sidebarBackground": "#ddefe3",
        "sidebarForeground": "#0b1f10",
        "listActiveSelectionBackground": "#b7d8c7",
        "listActiveSelectionForeground": "#0b1f10",
        "inputBackground": "#f0f7f3",
        "inputBorder": "#bcd6c5",
        "inputForeground": "#0b1f10",
        "focusBorder": "#2f7a5f",
        "buttonHoverBackground": "#c1e1cc",
        "buttonActiveBackground": "#a8d4b8",
    },
}


def _default_settings_path() -> str:
    base_directory = os.path.join(os.path.expanduser("~"), ".vscode_novel_polisher")
    os.makedirs(base_directory, exist_ok=True)
    return os.path.join(base_directory, "settings.json")


class ThemeManager(QtCore.QObject):
    themeChanged = QtCore.pyqtSignal(dict)

    def __init__(self, settingsFilePath: str | None = None) -> None:
        super().__init__()
        self._settingsFilePath = settingsFilePath or _default_settings_path()
        self._currentThemeKey = "dark"
        self._themes = THEME_CATALOG
        self._load_or_initialize_theme()

    def _load_or_initialize_theme(self) -> None:
        if not os.path.exists(self._settingsFilePath):
            self.saveTheme(self._currentThemeKey)
            return
        try:
            with open(self._settingsFilePath, "r", encoding="utf-8") as settings_file:
                data = json.load(settings_file)
        except (json.JSONDecodeError, OSError):
            self.saveTheme(self._currentThemeKey)
            return
        theme_key = data.get("theme", self._currentThemeKey)
        if theme_key not in self._themes:
            theme_key = self._currentThemeKey
        self._currentThemeKey = theme_key
        self.themeChanged.emit(self.getCurrentTheme())

    def saveTheme(self, themeKey: str) -> None:
        if themeKey not in self._themes:
            raise ValueError(f"未定义主题：{themeKey}")
        self._currentThemeKey = themeKey
        os.makedirs(os.path.dirname(self._settingsFilePath), exist_ok=True)
        with open(self._settingsFilePath, "w", encoding="utf-8") as settings_file:
            json.dump({"theme": themeKey}, settings_file, ensure_ascii=False, indent=2)
        self.themeChanged.emit(self.getCurrentTheme())

    def getCurrentTheme(self) -> Dict[str, str]:
        theme = dict(self._themes[self._currentThemeKey])
        theme["key"] = self._currentThemeKey
        return theme

    def getCurrentThemeKey(self) -> str:
        return self._currentThemeKey

    def getAvailableThemes(self) -> Iterable[Tuple[str, Dict[str, str]]]:
        return tuple(self._themes.items())

    def emitCurrentTheme(self) -> None:
        self.themeChanged.emit(self.getCurrentTheme())
