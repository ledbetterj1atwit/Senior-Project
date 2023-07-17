import re
import sys
import os
import pylatex
import webbrowser
from typing import Optional, Union

from PyQt6 import uic
from PyQt6.QtCore import QCoreApplication, QRunnable, QThreadPool, pyqtSlot, QSize, QObject, pyqtSignal
from PyQt6.QtGui import QKeySequence, QMovie
from PyQt6.QtWidgets import QDialog, QFileDialog, QErrorMessage, QApplication, QMainWindow, QTableWidgetItem
from pylatex import NoEscape

import attack
import subprocess


class EndDocumentException(Exception):
    def __init__(self, message="Document generation is ending early. Likely due to a pattern with END behavior."):
        self.message = message


class PatternErrorException(Exception):
    def __init__(self,
                 message="Document generation failed because an ERROR pattern matched, check your attack output."):
        self.message = message


class LatexException(Exception):
    def __init__(self, message="Document generation failed, the LaTeX was invalid.", invalid_latex: str = ""):
        self.message = message
        self.invalid_latex = invalid_latex


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
        self.parent().var_load()
        self.parent().doc_clear()
        self.parent().gen_clear()
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


class ScriptWorkerSignals(QObject):
    # Signals
    change_statusline: pyqtSignal = pyqtSignal(str)
    append_scriptout: pyqtSignal = pyqtSignal(str)
    append_output: pyqtSignal = pyqtSignal(attack.SectionOutput)
    append_scriptout_from_section: pyqtSignal = pyqtSignal()
    finished: pyqtSignal = pyqtSignal()


# noinspection PyUnresolvedReferences
class ScriptWorker(QRunnable):
    def __init__(self, app_dir: str,
                 atk_path: str,
                 atk_name: str,
                 sections: list[attack.SectionScript],
                 prefix: str,
                 postfix: str,
                 variables: dict,
                 *args, **kwargs):
        super(ScriptWorker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.args = args
        self.kwargs = kwargs
        self.app_dir = app_dir
        self.atk_path = atk_path
        self.atk_name = atk_name
        self.prefix = prefix
        self.postfix = postfix
        self.sections = sections
        self.vars = variables
        self.signals = ScriptWorkerSignals()
        self.paused = False
        self.killed = False

    @staticmethod
    def clean_stderr(stderr: str) -> str:
        err_lines = stderr.split("\r\n")
        for i in reversed(range(len(err_lines))):
            if re.match("^Could Not Find.*nv$", err_lines[i]):
                err_lines.pop(i)
            elif "The system cannot find the file nv." == err_lines[i]:
                err_lines.pop(i)
        return "\r\n".join(err_lines)

    @pyqtSlot()
    def run(self):
        try:
            for section in self.sections:
                self.signals.change_statusline.emit(f"Running section: {section.name}")
                atk_dir = os.path.dirname(os.path.abspath(self.atk_path))
                os.chdir(atk_dir)  # Operating from atk dir.
                vars_str = self.from_vars()
                scr_path = ""
                if section.section_type is attack.ScriptSectionType.EMPTY:
                    continue
                elif section.section_type is attack.ScriptSectionType.EMBEDDED:
                    scr_path = f"{self.atk_name}_{section.section_id}.bat"
                    with open(scr_path, "w") as f:
                        if section.section_id == 0:
                            f.write(self.prefix +
                                    vars_str +
                                    section.content +
                                    self.postfix.replace("diff.exe", f"{self.app_dir}\\diff.exe")
                                    )
                        else:
                            f.write(self.prefix +
                                    section.content +
                                    self.postfix.replace("diff.exe", f"{self.app_dir}\\diff.exe")
                                    )
                elif section.section_type is attack.ScriptSectionType.REFERENCE:
                    org_scr_path = f"{section.content}"
                    scr_path = f"{self.atk_name}_{section.section_id}.bat"
                    with open(org_scr_path, "r") as o:
                        with open(scr_path, "w") as f:
                            if section.section_id == 0:
                                f.write(self.prefix +
                                        vars_str +
                                        o.read() +
                                        self.postfix.replace("diff.exe", f"{self.app_dir}\\diff.exe")
                                        )
                            else:
                                f.write(self.prefix +
                                        o.read() +
                                        self.postfix.replace("diff.exe", f"{self.app_dir}\\diff.exe")
                                        )
                if self.killed:  # Exit-point
                    return
                shell_out = subprocess.run([scr_path], shell=False, capture_output=True)
                if self.killed:  # Exit-point
                    return
                self.signals.append_scriptout.emit(f"{'=' * 10}\nSection: {section.name}\n{'=' * 10}")
                self.signals.append_output.emit(attack.SectionOutput(
                    section.section_id,
                    shell_out.stdout.decode("UTF-8"),
                    self.clean_stderr(shell_out.stderr.decode("UTF-8"))
                ))
                self.signals.append_scriptout_from_section.emit()
                if section.section_type is attack.ScriptSectionType.EMBEDDED:
                    os.remove(scr_path)
                while self.paused:
                    pass  # Sit and wait.
            os.remove("nv")
        except AttributeError:
            return
        except FileNotFoundError:
            pass
        finally:
            os.chdir(self.app_dir)
            self.signals.finished.emit()

    @pyqtSlot()
    def pause(self):
        self.paused = True

    @pyqtSlot()
    def unpause(self):
        self.paused = False

    @pyqtSlot()
    def kill(self):
        self.killed = True

    def from_vars(self):
        content = ""
        for i in self.vars.keys():
            if " " in self.vars[i]:
                content += f"set {i}=\"{self.vars[i]}\"\n"
            else:
                content += f"set {i}={self.vars[i]}\n"
        return content


class DocumentWorkerSignals(QObject):
    change_statusline: pyqtSignal = pyqtSignal(str)
    finished: pyqtSignal = pyqtSignal(int)


class DocumentWorker(QRunnable):
    def __init__(self, section: int, filename: str, atk_path: str, atk: attack.Attack, app_dir: str):
        self.signals = DocumentWorkerSignals()
        self.section = section  # -1 for full document, positive int for specific section.
        self.filename = filename
        self.atk_path = atk_path
        self.atk = atk
        self.app_dir = app_dir
        super(DocumentWorker, self).__init__()

    def get_matching_patterns(self, doc_section_id: int) -> list[attack.Pattern]:
        output_section = None
        doc_section = None
        matching = []
        for o_s in self.atk.output.sections:
            if o_s.section_id == doc_section_id:
                output_section = o_s
                break
        for d_s in self.atk.document.sections:
            if d_s.section_id == doc_section_id:
                doc_section = d_s
                break
        for pattern in doc_section.patterns:
            if re.match(pattern.pattern_str, output_section.stdout):
                matching.append(pattern)
        return matching

    def create_section(self, doc: pylatex.Document, document_section_id: int):
        section = None
        remove_section = False
        for d_s in self.atk.document.sections:
            if d_s.section_id == document_section_id:
                section = d_s
                break

        with doc.create(pylatex.Section(section.name)):
            if section.section_type is attack.DocumentSectionType.REFERENCE:
                with open(section.content, "r") as f:
                    doc.append(NoEscape(f.read()))
            elif section.section_type is attack.DocumentSectionType.LITERAL:
                doc.append(NoEscape(section.content))
            elif section.section_type is attack.DocumentSectionType.PATTERN:
                matching = self.get_matching_patterns(document_section_id)
                to_add = NoEscape(section.content)  # I want a copy of the content string.
                for match in matching:
                    if match.behavior is attack.PatternBehavior.ADD:
                        to_add += NoEscape(match.match_content)
                    elif match.behavior is attack.PatternBehavior.REPLACE:
                        to_add = NoEscape(match.match_content)
                    elif match.behavior is attack.PatternBehavior.REMOVE:
                        remove_section = True
                    elif match.behavior is attack.PatternBehavior.END:
                        raise EndDocumentException()
                    elif match.behavior is attack.PatternBehavior.ERROR:
                        raise PatternErrorException()
                doc.append(to_add)
            elif section.section_type is attack.DocumentSectionType.COMBINED:
                pass  # This one is complicated, might work on it later.
        if remove_section:
            doc.pop(-1)

    @staticmethod
    def create_document() -> pylatex.Document:
        document = pylatex.Document()
        pkgs = [pylatex.Package("listings")]
        [document.packages.append(x) for x in pkgs]
        return document

    def create_section_preview(self, path: str):
        document = self.create_document()
        self.create_section(document, self.section)
        try:
            document.generate_pdf(path, clean_tex=True)
        except subprocess.CalledProcessError as e:
            print(e.stdout, str(e.stderr))
            raise LatexException()

    def create_report(self, path: str):
        document = self.create_document()
        for section in self.atk.document.sections:
            self.create_section(document, section.section_id)
        try:
            document.generate_pdf(path, clean_tex=True)
        except subprocess.CalledProcessError as e:
            print(e.stdout, e.stderr)
            raise LatexException()

    def run(self):
        self.signals.change_statusline.emit("Starting.")
        atk_dir = os.path.dirname(os.path.abspath(self.atk_path))
        os.chdir(atk_dir)
        try:
            if self.section >= 0:
                self.signals.change_statusline.emit(
                    f"Generating preview for section: {self.atk.document.sections[self.section].name}."
                )
                self.create_section_preview(self.filename)
            else:
                self.signals.change_statusline.emit("Generating report.")
                self.create_report(self.filename)
            self.signals.change_statusline.emit("Done.")
        except LatexException as e:
            self.signals.change_statusline.emit(e.message)
        except PatternErrorException as e:
            self.signals.change_statusline.emit(e.message)
        except EndDocumentException as e:
            self.signals.change_statusline.emit(e.message)
        os.chdir(self.app_dir)
        self.signals.finished.emit(self.section)


# noinspection PyUnresolvedReferences
class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # So pycharm doesn't complain...
        self.var_old_content = None
        self.loading: bool = False
        # Thread Pool
        self.pool = QThreadPool()
        self.workers: list[Union[ScriptWorker, DocumentWorker]] = []
        self.run_paused = False
        print(f"Using up to {self.pool.maxThreadCount()} thread(s)")
        # Dialogs
        self.create_dlg = None
        self.open_dlg = None
        # Load ui from file.
        uic.loadUi("UI/main.ui", self)
        # Attack
        self.atk: Optional[attack.Attack] = None
        self.atk_saved = False
        self.prog_version = "0.0.0"
        # Paths
        self.atk_path = ""
        self.app_dir = ""
        # Hardcoded Batch
        self.prefix = ""
        self.postfix = ""
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
        self.actionManual.triggered.connect(self.open_manual)
        self.actionManual.setShortcut(QKeySequence("F1"))
        self.actionGenerate_Doc.triggered.connect(self.gen_generate)
        self.actionGenerate_Doc.setShortcut(QKeySequence("F6"))
        # Buttons
        self.script_section_add.clicked.connect(self.script_section_add_new)
        self.script_section_remove.clicked.connect(self.script_section_remove_selected)
        self.var_button_add.clicked.connect(self.var_add)
        self.var_button_remove.clicked.connect(self.var_remove)
        self.doc_section_add.clicked.connect(self.doc_section_add_new)
        self.doc_section_remove.clicked.connect(self.doc_section_remove_selected)
        self.pattern_add_button.clicked.connect(self.pattern_add)
        self.pattern_remove_button.clicked.connect(self.pattern_remove)
        self.run_button.clicked.connect(self.actionRun_Attack.trigger)
        self.run_pause_button.clicked.connect(self.run_pause)
        self.run_stop_button.clicked.connect(self.run_stop)
        self.gen_button_generate.clicked.connect(self.gen_generate)
        self.gen_button_refresh.clicked.connect(self.gen_refresh)
        # Combo Boxes
        self.script_section_type.currentIndexChanged.connect(self.script_update_current)
        self.doc_section_type.currentIndexChanged.connect(self.doc_update_current)
        self.pattern_select.currentIndexChanged.connect(self.pattern_read_current)
        self.pattern_behavior.currentIndexChanged.connect(self.pattern_set_current)
        # Text Edits
        self.script_section_name.textChanged.connect(self.script_update_current)
        self.script_section_content.textChanged.connect(self.script_update_current)
        self.doc_section_name.textChanged.connect(self.doc_update_current)
        self.doc_section_content.textChanged.connect(self.doc_update_current)
        self.pattern_regex.textChanged.connect(self.pattern_set_current)
        self.pattern_content.textChanged.connect(self.pattern_set_current)
        self.gen_quick_edit.textChanged.connect(self.gen_update_current)
        # Item Lists
        self.script_section_list.itemSelectionChanged.connect(self.script_read_current)
        self.doc_section_list.itemSelectionChanged.connect(self.doc_read_current)
        self.var_table.itemSelectionChanged.connect(self.var_entered)
        self.var_table.cellChanged.connect(self.var_changed)
        self.gen_section_list.itemSelectionChanged.connect(self.gen_read_current)
        # Spinner
        movie = QMovie("ui/skull.gif")
        movie.setScaledSize(QSize(50, 50))
        self.run_spinner.setMovie(movie)
        movie.start()

    @staticmethod
    def open_manual():
        # TODO: Replace this with a link to a pdf on machine.
        webbrowser.open("https://docs.google.com/document/d/1_ibPUTPo9p80J6AhXcd5wSnR0rmHy5oWmvowWfFlm8Q")

    def new_attack(self):
        self.loading = True
        self.create_dlg = CreateAttackDlg(self)
        self.create_dlg.show()
        self.loading = False

    def open_attack(self):
        self.loading = True
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
            for doc_section in self.atk.document.sections:
                self.doc_section_add_existing(doc_section)
            self.var_load()
            self.gen_load()
            self.setWindowTitle(f"APT - {self.atk.meta.name}")
            self.atk_saved = True
        except KeyError:
            err = QErrorMessage(self)
            err.finished.connect(self.open_attack)
            err.showMessage("Attack was invalid.")
        except FileNotFoundError:
            pass
        self.loading = False

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
        try:
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
        except IndexError:
            if self.atk is None:
                QErrorMessage(self).showMessage("Please Open or Make an attack first.")
            else:
                QErrorMessage(self).showMessage("Please add and select at least one section.")

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

    def generate_new_var_name(self):
        idx = 0
        for i in self.atk.variables.keys():
            res = re.match(r"unnamed(\([0-9]+\))?", i)
            try:
                if res is not None and int(res.group(1)[1:-1]) >= idx:
                    idx = int(res.group(1)[1:-1]) + 1
            except TypeError:  # for "unnamed"
                if idx == 0:
                    idx = 1
        if idx == 0:
            return "unnamed"
        else:
            return f"unnamed({idx})"

    def var_add(self):
        try:
            new_name = self.generate_new_var_name()
            new_value = "value goes here"
            new_var = {new_name: new_value}
            new_row_idx = self.var_table.rowCount()
            self.var_table.insertRow(new_row_idx)
            new_name_item = QTableWidgetItem(new_name)
            new_value_item = QTableWidgetItem(new_value)
            self.var_table.setItem(new_row_idx, 0, new_name_item)
            self.var_table.setItem(new_row_idx, 1, new_value_item)
            self.var_table.scrollToItem(new_name_item)
            self.atk.variables.update(new_var)
            self.mark_unsaved_changes()
        except AttributeError:
            QErrorMessage(self).showMessage("Please Open or Make an attack first.")

    def var_remove(self):
        to_remove = [i.row() for i in self.var_table.selectedIndexes()]
        to_remove = reversed(list(set(to_remove)))  # Remove duplicates, sort, reverse.
        for idx in to_remove:
            var_to_remove = self.var_table.item(idx, 0).text()
            self.atk.variables.pop(var_to_remove)
            self.var_table.removeRow(idx)
        self.mark_unsaved_changes()

    def var_load(self):
        self.var_table.setRowCount(0)
        to_load = self.atk.variables.keys()
        for i in to_load:
            new_row_idx = self.var_table.rowCount()
            self.var_table.insertRow(new_row_idx)
            new_name_item = QTableWidgetItem(i)
            new_value_item = QTableWidgetItem(self.atk.variables[i])
            self.var_table.setItem(new_row_idx, 0, new_name_item)
            self.var_table.setItem(new_row_idx, 1, new_value_item)

    def var_changed(self, row, column):
        if self.loading:
            return
        try:
            if column == 0:
                old_name = self.var_old_content
                old_val = self.atk.variables[old_name]
                new_name = self.var_table.item(row, column).text()
                self.atk.variables.pop(old_name)
                self.atk.variables.update({new_name: old_val})
            else:
                name = self.var_table.item(row, 0).text()
                self.atk.variables[name] = self.var_table.item(row, column).text()
        except AttributeError:  # Adds
            pass
        except KeyError:  # Removes
            pass
        self.mark_unsaved_changes()

    def var_entered(self):
        try:
            current = self.var_table.selectedItems()[0]
            row = self.var_table.row(current)
            column = self.var_table.column(current)
            self.var_old_content = self.var_table.item(row, column).text()
        except IndexError:
            pass

    def run_start_attack(self):
        self.run_scriptout.document().setPlainText("")
        self.run_button.setDisabled(True)
        self.run_pause_button.setEnabled(True)
        self.run_stop_button.setEnabled(True)

        worker = ScriptWorker(self.app_dir,
                              self.atk_path,
                              self.atk.meta.name,
                              self.atk.script.sections,
                              self.prefix,
                              self.postfix,
                              self.atk.variables)
        self.workers.append(worker)
        worker.signals.append_scriptout.connect(self.run_append_to_scriptout)
        worker.signals.change_statusline.connect(self.run_set_statusline)
        worker.signals.append_scriptout_from_section.connect(self.run_append_scriptout_from_section)
        worker.signals.append_output.connect(self.run_append_output)
        worker.signals.finished.connect(self.run_attack_finished)
        self.pool.start(worker)

    def run_pause(self):
        self.run_paused = not self.run_paused
        if self.run_paused:
            self.run_pause_button.setText("Unpause")
        else:
            self.run_pause_button.setText("Pause At End Of Section")
        for worker in self.workers:
            if not self.run_paused:
                worker.unpause()
            else:
                worker.pause()

    def run_stop(self):
        for worker in self.workers:
            worker.kill()
        self.workers = []
        self.pool.waitForDone(1)
        self.run_attack_finished()

    def run_attack_finished(self):
        self.run_button.setEnabled(True)
        self.run_pause_button.setDisabled(True)
        self.run_stop_button.setDisabled(True)
        self.run_set_statusline("Done")
        self.mark_unsaved_changes()

    def run_append_to_scriptout(self, text: str):
        doc = self.run_scriptout.document()
        doc.setPlainText(f"{doc.toPlainText()}\n{text}")

    def run_append_scriptout_from_section(self):
        self.run_append_to_scriptout(self.atk.output.sections[-1].content)

    def run_set_statusline(self, text: str):
        self.run_statusline.setText(text)

    def run_append_output(self, out: attack.SectionOutput):
        self.atk.output.sections.append(out)

    def doc_section_add_new(self):
        if self.atk is None:
            QErrorMessage(self).showMessage("Please Open or Make an attack first.")
            return
        new_id = 0
        try:
            new_id = self.atk.document.sections[-1].section_id + 1
        except IndexError:
            pass
        self.atk.document.sections.append(attack.SectionDocument(new_id,
                                                                 "Unnamed Section",
                                                                 attack.DocumentSectionType.EMPTY,
                                                                 "",
                                                                 []))
        self.doc_section_list.addItem(f"{new_id}: Unnamed Section")
        self.gen_load()
        self.mark_unsaved_changes()

    def doc_section_add_existing(self, section: attack.SectionDocument):
        self.doc_section_list.addItem(f"{section.section_id}: {section.name}")

    def doc_section_remove_selected(self):
        try:
            selected_indexes = [self.doc_section_list.row(i) for i in self.doc_section_list.selectedItems()]
            for i in reversed(selected_indexes):
                self.atk.document.sections.pop(i)
                self.doc_section_list.takeItem(i)
                self.doc_section_list.setCurrentRow(selected_indexes[0] - 1)
            self.gen_load()
            self.mark_unsaved_changes()
        except IndexError:
            return

    def doc_clear(self):
        for i in reversed(range(self.doc_section_list.count())):
            self.doc_section_list.takeItem(i)

    def doc_update_current(self):
        try:
            current_idx = [self.doc_section_list.row(i) for i in self.doc_section_list.selectedItems()][0]
            current: attack.SectionDocument = self.atk.document.sections[current_idx]
            current.name = self.doc_section_name.text()
            self.doc_section_list.item(current_idx).setText(f"{current.section_id}: {current.name}")
            current.content = self.doc_section_content.document().toPlainText()
            if self.doc_section_type.currentIndex() == 0:
                current.section_type = attack.DocumentSectionType.EMPTY
            elif self.doc_section_type.currentIndex() == 1:
                current.section_type = attack.DocumentSectionType.LITERAL
            elif self.doc_section_type.currentIndex() == 2:
                current.section_type = attack.DocumentSectionType.REFERENCE
            elif self.doc_section_type.currentIndex() == 3:
                current.section_type = attack.DocumentSectionType.PATTERN
            self.pattern_load()
            self.gen_load()
            self.mark_unsaved_changes()
        except IndexError:
            if self.atk is None:
                QErrorMessage(self).showMessage("Please Open or Make an attack first.")
            else:
                QErrorMessage(self).showMessage("Please add and select at least one section.")

    def doc_read_current(self):
        try:
            current_idx = [self.doc_section_list.row(i) for i in self.doc_section_list.selectedItems()][0]
            current: attack.SectionDocument = self.atk.document.sections[current_idx]
            name = current.name
            content = current.content
            current_type = current.section_type
            self.doc_section_name.setText(name)
            self.doc_section_content.document().setPlainText(content)
            if current_type is attack.DocumentSectionType.EMPTY:
                self.doc_section_type.setCurrentIndex(0)
            elif current_type is attack.DocumentSectionType.LITERAL:
                self.doc_section_type.setCurrentIndex(1)
            elif current_type is attack.DocumentSectionType.REFERENCE:
                self.doc_section_type.setCurrentIndex(2)
            elif current_type is attack.DocumentSectionType.PATTERN:
                self.doc_section_type.setCurrentIndex(3)
            current.name = name
            current.section_type = current_type
            current.content = content
        except IndexError:
            return

    def pattern_add(self):
        new_pattern = attack.Pattern("new pattern", "This pattern has not been set-up.", attack.PatternBehavior.REPLACE)
        current_idx = [self.doc_section_list.row(i) for i in self.doc_section_list.selectedItems()][0]
        current: attack.SectionDocument = self.atk.document.sections[current_idx]
        current.patterns.append(new_pattern)
        self.pattern_select.addItem(new_pattern.pattern_str)
        self.pattern_select.setCurrentIndex(len(current.patterns) - 1)

    def pattern_remove(self):
        current_idx = [self.doc_section_list.row(i) for i in self.doc_section_list.selectedItems()][0]
        current: attack.SectionDocument = self.atk.document.sections[current_idx]
        pattern_idx = self.pattern_select.currentIndex()
        self.pattern_select.removeItem(pattern_idx)
        current.patterns.pop(pattern_idx)

    def pattern_load(self):
        current_idx = [self.doc_section_list.row(i) for i in self.doc_section_list.selectedItems()][0]
        current: attack.SectionDocument = self.atk.document.sections[current_idx]
        for pattern in current.patterns:
            self.pattern_select.addItem(pattern.pattern_str)
        self.pattern_select.setCurrentIndex(0)

    def pattern_read_current(self):
        try:
            current_idx = [self.doc_section_list.row(i) for i in self.doc_section_list.selectedItems()][0]
            current: attack.SectionDocument = self.atk.document.sections[current_idx]
            pattern_idx = self.pattern_select.currentIndex()
            self.pattern_regex.setText(current.patterns[pattern_idx].pattern_str)
            self.pattern_content.setText(current.patterns[pattern_idx].match_content)
            if current.patterns[pattern_idx].behavior is attack.PatternBehavior.REPLACE:
                self.pattern_behavior.setCurrentIndex(0)
            elif current.patterns[pattern_idx].behavior is attack.PatternBehavior.ADD:
                self.pattern_behavior.setCurrentIndex(1)
            elif current.patterns[pattern_idx].behavior is attack.PatternBehavior.REMOVE:
                self.pattern_behavior.setCurrentIndex(2)
            elif current.patterns[pattern_idx].behavior is attack.PatternBehavior.END:
                self.pattern_behavior.setCurrentIndex(3)
            elif current.patterns[pattern_idx].behavior is attack.PatternBehavior.ERROR:
                self.pattern_behavior.setCurrentIndex(4)
        except IndexError:
            return

    def pattern_set_current(self):
        current = None
        try:
            current_idx = [self.doc_section_list.row(i) for i in self.doc_section_list.selectedItems()][0]
            current = self.atk.document.sections[current_idx]
            pattern_idx = self.pattern_select.currentIndex()
            current.patterns[pattern_idx].pattern_str = self.pattern_regex.text()
            current.patterns[pattern_idx].match_content = self.pattern_content.text()
            if self.pattern_behavior.currentIndex() == 0:
                current.patterns[pattern_idx].behavior = attack.PatternBehavior.REPLACE
            elif self.pattern_behavior.currentIndex() == 1:
                current.patterns[pattern_idx].behavior = attack.PatternBehavior.ADD
            elif self.pattern_behavior.currentIndex() == 2:
                current.patterns[pattern_idx].behavior = attack.PatternBehavior.REMOVE
            elif self.pattern_behavior.currentIndex() == 3:
                current.patterns[pattern_idx].behavior = attack.PatternBehavior.END
            elif self.pattern_behavior.currentIndex() == 4:
                current.patterns[pattern_idx].behavior = attack.PatternBehavior.ERROR
        except IndexError:
            if self.atk is None:
                QErrorMessage(self).showMessage("Please Open or Make an attack first.")
            elif current is None:
                QErrorMessage(self).showMessage("Please add and select at least one section.")
            else:
                QErrorMessage(self).showMessage("Please add and select at least one pattern.")

    def gen_load(self):
        self.gen_clear()
        for section in self.atk.document.sections:
            self.gen_section_list.addItem(f"{section.section_id}: {section.name}")

    def gen_clear(self):
        self.gen_section_list.clear()

    def gen_read_current(self):
        try:
            current_index = [self.gen_section_list.row(i) for i in self.gen_section_list.selectedItems()][0]
            current = self.atk.document.sections[current_index]
            self.gen_quick_edit.document().setPlainText(current.content)
        except IndexError:
            pass

    def gen_update_current(self):
        try:
            current_index = [self.gen_section_list.row(i) for i in self.gen_section_list.selectedItems()][0]
            current = self.atk.document.sections[current_index]
            current.content = self.gen_quick_edit.document().toPlainText()
            self.mark_unsaved_changes()
        except IndexError:
            if self.atk is None:
                QErrorMessage(self).showMessage("Please Open or Make an attack first.")
            else:
                QErrorMessage(self).showMessage("Please add at least one document section and select it here.")

    def gen_refresh(self):
        try:
            self.gen_button_generate.setDisabled(True)
            self.gen_button_refresh.setDisabled(True)
            current_index = [self.gen_section_list.row(i) for i in self.gen_section_list.selectedItems()][0]
            current = self.atk.document.sections[current_index]
            filename = f"{self.atk.meta.name}_section_{current.section_id}"
            worker = DocumentWorker(current.section_id, filename, self.atk_path, self.atk, self.app_dir)
            self.workers.append(worker)
            worker.signals.change_statusline.connect(self.gen_set_statusline)
            worker.signals.finished.connect(self.gen_finished)
            self.pool.start(worker)
        except IndexError:
            if self.atk is None:
                QErrorMessage(self).showMessage("Please Open or Make an attack first.")
            else:
                QErrorMessage(self).showMessage("Please add at least one document section and select it here.")
            self.gen_button_generate.setDisabled(False)
            self.gen_button_refresh.setDisabled(False)

    def gen_generate(self):
        try:
            self.gen_button_generate.setDisabled(True)
            self.gen_button_refresh.setDisabled(True)
            worker = DocumentWorker(-1, self.atk.meta.name, self.atk_path, self.atk, self.app_dir)
            self.workers.append(worker)
            worker.signals.change_statusline.connect(self.gen_set_statusline)
            worker.signals.finished.connect(self.gen_finished)
            self.pool.start(worker)
        except AttributeError:
            QErrorMessage(self).showMessage("Please Open or Make an attack first.")
            self.gen_button_generate.setDisabled(False)
            self.gen_button_refresh.setDisabled(False)

    def gen_finished(self, section: int):
        if section >= 0:
            print("Section preview not finished.")
        else:
            pass
        self.gen_button_generate.setDisabled(False)
        self.gen_button_refresh.setDisabled(False)

    def gen_set_statusline(self, text: str):
        self.gen_statusline.setText(text)

    def gen_preview_next(self):
        pass

    def gen_preview_prev(self):
        pass

    def app_quit(self):
        if not self.atk_saved:
            AttackUnsavedDlg(self).show()
        else:
            QCoreApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.app_dir = os.path.dirname(os.path.abspath(__file__))
    with open(f"{window.app_dir}/prefix.bat", 'r') as p:
        window.prefix = p.read()
    with open(f"{window.app_dir}/postfix.bat", 'r') as p:
        window.postfix = p.read()
    window.show()
    app.exec()
