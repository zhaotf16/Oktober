import sys
from PyQt5.QtWidgets import QApplication
from oktober.gui.main_window import MRCViewer
from oktober.gui.theme import (
    apply_solarized_light_theme,
    apply_simple_scientific_theme,
    apply_academic_blue_theme,
    apply_lab_theme,
)


def main():
    #QApplication.setStyle("Fusion")
    #QApplication.setStyle("Fusion")
    app = QApplication(sys.argv)
    viewer = MRCViewer()
    apply_academic_blue_theme(viewer)
    viewer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()