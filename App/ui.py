import sys
import os
from typing import Optional

from PyQt6 import QtWidgets, uic
from PyQt6.QtCore import QUrl

import attack


class CreateAttackDlg(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi("UI/create_attack_dialog.ui", self)

    def accept(self) -> None:
        main_window = self.parent()
        meta = attack.Meta(self.a_name.text(), self.a_auth.text(), self.a_ver.text(), main_window.prog_version)
        scr = attack.Script([], [])
        doc = attack.Document([])
        main_window.atk = attack.Attack(meta, scr, doc, {})
        main_window.atk_path = ""
        main_window.setWindowTitle(f"APT - *{main_window.atk.meta.name}")
        main_window.update_from_atk()
        super().accept()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.create_dlg = None
        self.open_dlg = None
        uic.loadUi("UI/main.ui", self)
        self.atk: Optional[attack.Attack] = None
        self.atk_path = ""
        self.prog_version = "0.0.0"
        self.actionNew.triggered.connect(self.new_attack)
        self.actionOpen.triggered.connect(self.open_attack)
        self.actionSave.triggered.connect(self.save_attack)
        self.actionSave_As.triggered.connect(self.save_attack_as)

    def new_attack(self):
        self.create_dlg = CreateAttackDlg(self)
        self.create_dlg.show()

    def open_attack(self):
        new_path = QtWidgets.QFileDialog.getOpenFileName(self,
                                                         "Open Attack",
                                                         os.path.expanduser("~"),
                                                         "Attack Files (*.atk)")[0]
        try:
            self.atk = attack.Attack.load(new_path)
            self.atk_path = new_path
            self.setWindowTitle(f"APT - {self.atk.meta.name}")
            self.update_from_atk()
        except KeyError:
            err = QtWidgets.QErrorMessage(self)
            err.finished.connect(self.open_attack)
            err.showMessage("Attack was invalid.")

    def save_attack(self):
        if self.atk_path == "":
            self.save_attack_as()
        else:
            self.atk.save(self.atk_path)
            self.setWindowTitle(
                f"APT - {self.windowTitle().removeprefix('APT - ').removeprefix('*')}")  # Remove unsaved *

    def save_attack_as(self):
        sav = QtWidgets.QFileDialog.getSaveFileName(self,
                                                    "Save As",
                                                    f"{os.path.expanduser('~')}\\untitled.atk",
                                                    "Attack Files(*.atk)")[0]
        self.atk_path = sav
        try:
            self.atk.save(sav)
            self.setWindowTitle(
                f"APT - {self.windowTitle().removeprefix('APT - ').removeprefix('*')}")  # Remove unsaved *
        except AttributeError:  # No file made.
            QtWidgets.QErrorMessage(self).showMessage("Please Open or Make an attack first.")
        except FileNotFoundError:
            pass

    def update_from_atk(self):
        pass


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
