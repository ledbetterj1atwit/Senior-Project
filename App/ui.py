import sys
import os
from typing import Optional

from PyQt6 import QtWidgets, uic
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QKeySequence, QAction
from PyQt6.QtWidgets import QAbstractButton, QListWidgetItem

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
        self.parent().script_clear()
        super().accept()


class AttackUnsavedDlg(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi("UI/unsaved_dialog.ui", self)
        self.buttonBox.buttons()[0].clicked.connect(self.save)
        self.buttonBox.buttons()[2].clicked.connect(QCoreApplication.quit)
        self.buttonBox.buttons()[1].clicked.connect(self.reject)

    def save(self):
        self.parent().save_attack_as()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dialogs
        self.create_dlg = None
        self.open_dlg = None
        # Load ui from file.
        uic.loadUi("UI/main.ui", self)
        # Attack
        self.atk: Optional[attack.Attack] = None
        self.atk_path = ""
        self.atk_saved = False
        self.prog_version = "0.0.0"
        # Actions
        self.actionNew.triggered.connect(self.new_attack)
        self.actionNew.setShortcut(QKeySequence("Ctrl+N"))
        self.actionOpen.triggered.connect(self.open_attack)
        self.actionOpen.setShortcut(QKeySequence("Ctrl+O"))
        self.actionSave.triggered.connect(self.save_attack)
        self.actionSave.setShortcut(QKeySequence("Ctrl+S"))
        self.actionSave_As.triggered.connect(self.save_attack_as)
        self.actionSave_As.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.actionQuit.triggered.connect(self.app_quit)
        self.actionQuit.setShortcut(QKeySequence("Ctrl+Q"))
        # Buttons
        self.script_section_add.clicked.connect(self.script_section_add_new)
        self.script_section_remove.clicked.connect(self.script_section_remove_selected)

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
            self.script_clear()
            for script_section in self.atk.script.sections:
                self.script_section_add_existing(script_section)
            self.setWindowTitle(f"APT - {self.atk.meta.name}")
            self.atk_saved = True


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
            self.atk_saved = True

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
            self.atk_saved = True
        except AttributeError:  # No file made.
            QtWidgets.QErrorMessage(self).showMessage("Please Open or Make an attack first.")
        except FileNotFoundError:
            pass

    def mark_unsaved_changes(self, filename=""):
        self.atk_saved = False
        if filename == "":
            self.setWindowTitle(f"APT - *{self.windowTitle().removeprefix('APT - ').removeprefix('*')}")
        else:
            self.setWindowTitle(f"APT - *{filename}")

    def script_section_add_new(self):
        if self.atk is None:
            QtWidgets.QErrorMessage(self).showMessage("Please Open or Make an attack first.")
            return
        new_id = 0
        try:
            new_id = self.atk.script.sections[-1].section_id + 1
        except IndexError:
            pass
        self.atk.script.sections.append(attack.SectionScript(new_id,
                                                             "Unnamed Section",
                                                             attack.ScriptSectionType.EMPTY,
                                                             ""))
        self.script_section_list.addItem(f"{new_id}: Unnamed Section")
        self.mark_unsaved_changes()

    def script_section_add_existing(self, section: attack.SectionScript):
        self.script_section_list.addItem(f"{section.section_id}: {section.name}")

    def script_section_remove_selected(self):
        selected_idxs = [self.script_section_list.row(i) for i in self.script_section_list.selectedItems()]
        selected_items = [self.script_section_list.takeItem(i) for i in reversed(selected_idxs)]
        for i in reversed(selected_idxs):
            self.atk.script.sections.pop(i)
        self.mark_unsaved_changes()

    def script_clear(self):
        for i in reversed(range(self.script_section_list.count())):
            self.script_section_list.takeItem(i)

    def app_quit(self):
        if not self.atk_saved:
            AttackUnsavedDlg(self).show()
        else:
            QCoreApplication.quit()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
