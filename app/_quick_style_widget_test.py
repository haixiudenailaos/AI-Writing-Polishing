from PyQt5 import QtWidgets
from app.config_manager import ConfigManager, PolishStyle
from app.style_manager import StyleManager
from app.widgets.settings_dialog import SettingsDialog


def run():
    app = QtWidgets.QApplication([])
    cm = ConfigManager()
    sm = StyleManager(cm)
    dlg = SettingsDialog(cm, sm)
    style = PolishStyle(id="test-style", name="测试风格", prompt="提示", is_preset=False, parameters={})
    w = dlg._create_custom_style_widget(style, True)
    print("Widget:", type(w).__name__)


if __name__ == "__main__":
    run()