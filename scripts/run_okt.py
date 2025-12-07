#!/usr/bin/env python
from oktober import OktoberViewer
from PyQt5.QtWidgets import QApplication
import sys

def main():
    app = QApplication(sys.argv)
    viewer = OktoberViewer()
    viewer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
