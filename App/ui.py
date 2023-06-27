import re
import sys
import os
from typing import Optional

from PyQt6 import uic
from PyQt6.QtCore import QCoreApplication, QRunnable, QThreadPool, pyqtSlot
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QDialog, QFileDialog, QErrorMessage, QApplication, QMainWindow

import attack
import subprocess

prefix, postfix = "", ""


class CreateAttackDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi("UI/create_attack_dialog.ui", self)

    def accept(self) -> None:
        main_window = self.parent()
        meta = attack.Meta(self.a_name.text(), self.a_auth.text(), self.a_ver.text(), main_window.prog_version)
        scr = attack.Script([], [])
        doc = attack.Document([])
        out = attack.Output([])
        main_window.atk = attack.Attack(meta, scr, doc, {}, out)
        main_window.atk_path = ""
        main_window.setWindowTitle(f"APT - *{main_window.atk.meta.name}")
        self.parent().script_clear()
        super().accept()


class AttackUnsavedDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi("UI/unsaved_dialog.ui", self)
        self.buttonBox.buttons()[0].clicked.connect(self.save)
        self.buttonBox.buttons()[2].clicked.connect(QCoreApplication.quit)
        self.buttonBox.buttons()[1].clicked.connect(self.reject)

    def save(self):
        self.parent().save_attack_as()


class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Thread Pool
        self.pool = QThreadPool()
        print(f"Using up to {self.pool.maxThreadCount()} thread(s)")
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
        self.actionRun_Attack.triggered.connect(self.run_start_attack)
        self.actionRun_Attack.setShortcut(QKeySequence("F5"))
        # Buttons
        self.script_section_add.clicked.connect(self.script_section_add_new)
        self.script_section_remove.clicked.connect(self.script_section_remove_selected)
        self.run_button.clicked.connect(self.actionRun_Attack.trigger)
        # Combo Boxes
        self.script_section_type.currentIndexChanged.connect(self.script_update_current)
        # Text Edits
        self.script_section_name.textChanged.connect(self.script_update_current)
        self.script_section_content.textChanged.connect(self.script_update_current)
        # Item Lists
        self.script_section_list.itemSelectionChanged.connect(self.script_read_current)

    def new_attack(self):
        self.create_dlg = CreateAttackDlg(self)
        self.create_dlg.show()

    def open_attack(self):
        new_path = QFileDialog.getOpenFileName(self,
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
            err = QErrorMessage(self)
            err.finished.connect(self.open_attack)
            err.showMessage("Attack was invalid.")
        except FileNotFoundError:
            pass

    def save_attack(self):
        if self.atk_path == "":
            self.save_attack_as()
        else:
            self.atk.save(self.atk_path)
            self.setWindowTitle(
                f"APT - {self.windowTitle().removeprefix('APT - ').removeprefix('*')}")  # Remove unsaved *
            self.atk_saved = True

    def save_attack_as(self):
        sav = QFileDialog.getSaveFileName(self,
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
            self.dlg_no_attack_open()
        except FileNotFoundError:
            pass

    def dlg_no_attack_open(self):
        QErrorMessage(self).showMessage("Please Open or Make an attack first.")

    def mark_unsaved_changes(self, filename=""):
        self.atk_saved = False
        if filename == "":
            self.setWindowTitle(f"APT - *{self.windowTitle().removeprefix('APT - ').removeprefix('*')}")
        else:
            self.setWindowTitle(f"APT - *{filename}")

    def script_section_add_new(self):
        if self.atk is None:
            QErrorMessage(self).showMessage("Please Open or Make an attack first.")
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
        try:
            selected_indexes = [self.script_section_list.row(i) for i in self.script_section_list.selectedItems()]
            for i in reversed(selected_indexes):
                self.atk.script.sections.pop(i)
                self.script_section_list.takeItem(i)
                self.script_section_list.setCurrentRow(selected_indexes[0] - 1)
                self.mark_unsaved_changes()
        except IndexError:
            return

    def script_clear(self):
        for i in reversed(range(self.script_section_list.count())):
            self.script_section_list.takeItem(i)

    def script_update_current(self):
        current_idx = [self.script_section_list.row(i) for i in self.script_section_list.selectedItems()][0]
        current: attack.SectionScript = self.atk.script.sections[current_idx]
        current.name = self.script_section_name.text()
        self.script_section_list.item(current_idx).setText(f"{current.section_id}: {current.name}")
        current.content = self.script_section_content.document().toPlainText()
        if self.script_section_type.currentIndex() == 0:
            current.section_type = attack.ScriptSectionType.EMPTY
        elif self.script_section_type.currentIndex() == 1:
            current.section_type = attack.ScriptSectionType.EMBEDDED
        elif self.script_section_type.currentIndex() == 2:
            current.section_type = attack.ScriptSectionType.REFERENCE
        self.mark_unsaved_changes()

    def script_read_current(self):
        try:
            current_idx = [self.script_section_list.row(i) for i in self.script_section_list.selectedItems()][0]
            current: attack.SectionScript = self.atk.script.sections[current_idx]
            name = current.name
            content = current.content
            current_type = current.section_type
            self.script_section_name.setText(name)
            self.script_section_content.document().setPlainText(content)
            if current_type is attack.ScriptSectionType.EMPTY:
                self.script_section_type.setCurrentIndex(0)
            elif current_type is attack.ScriptSectionType.EMBEDDED:
                self.script_section_type.setCurrentIndex(1)
            elif current_type is attack.ScriptSectionType.REFERENCE:
                self.script_section_type.setCurrentIndex(2)
            current.name = name
            current.section_type = current_type
            current.content = content
        except IndexError:
            return

    def run_start_attack(self):
        worker = ScriptWorker(self)
        self.pool.start(worker)

    def app_quit(self):
        if not self.atk_saved:
            AttackUnsavedDlg(self).show()
        else:
            QCoreApplication.quit()


class ScriptWorker(QRunnable):
    def __init__(self, main_window: MainWindow = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.main = main_window

    @staticmethod
    def clean_stderr(stderr: str) -> str:
        err_lines = stderr.split("\r\n")
        for i in reversed(range(len(err_lines))):
            if re.match("^Could Not Find.*nv$", err_lines[i]):
                err_lines.pop(i)
            elif "The system cannot find the file nv." == err_lines[i]:
                err_lines.pop(i)
        return "\r\n".join(err_lines)

    def append_to_scriptout(self, text: str):
        doc = self.main.run_scriptout.document()
        doc.setPlainText(f"{doc.toPlainText()}\n{text}")

    def set_statusline(self, text: str):
        self.main.run_statusline.setText(text)

    @pyqtSlot()
    def run(self):
        global prefix, postfix
        self.main.run_scriptout.document().setPlainText("")
        self.main.run_button.setDisabled(True)
        self.main.run_pause_button.setEnabled(True)
        self.main.run_stop_button.setEnabled(True)
        try:
            for section in self.main.atk.script.sections:
                self.set_statusline(f"Running section: {section.name}")
                scr_path = f"{self.main.atk.meta.name}_{section.section_id}.bat"
                with open(scr_path, "w") as f:
                    f.write(prefix + section.content + postfix)
                shell_out = subprocess.run([scr_path], shell=False, capture_output=True)
                self.main.atk.output.sections.append(attack.SectionOutput(
                    section.section_id,
                    shell_out.stdout.decode("ascii"),
                    self.clean_stderr(shell_out.stderr.decode("ascii"))
                ))
                self.append_to_scriptout(self.main.atk.output.sections[-1].content)

                os.remove(scr_path)
            os.remove("nv")
            self.main.mark_unsaved_changes()
        except AttributeError:
            return
        finally:
            self.main.run_button.setEnabled(True)
            self.main.run_pause_button.setDisabled(True)
            self.main.run_stop_button.setDisabled(True)
            self.set_statusline("Done")


if __name__ == "__main__":
    with open("prefix.bat", 'r') as p:
        prefix = p.read()
    with open("postfix.bat", 'r') as p:
        postfix = p.read()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
