import ctypes
import logging
import os
from sys import argv, exit, stdout

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from Automator.gui.main import MainWindow


def main():
    main_path = os.path.join(os.path.expandvars('%ProgramData%'), '24HS-Automator')
    if not os.path.isdir(main_path):
        os.mkdir(main_path)

    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(name)s/%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.StreamHandler(stdout),
            logging.FileHandler(os.path.join(main_path, 'log.txt'))
        ]
    )

    app = QApplication(argv)
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'icons', '24hs.png')))
    app_id = '24hs.automator'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    window = MainWindow()
    window.show()
    exit(app.exec())


if __name__ == '__main__':
    main()
