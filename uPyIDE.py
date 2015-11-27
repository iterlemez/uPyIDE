#!/usr/bin/env python3
import os
import sys
import serial
import glob
import xml.etree.ElementTree as ElementTree
import pyqode_i18n
import termWidget

import pyqode.python.backend.server as server
import pyqode.python.widgets as widgets
import pyqode.qt.QtWidgets as QtWidgets
import pyqode.qt.QtCore as QtCore


__version__ = '1.0'


def i18n(s): return pyqode_i18n.tr(s)


def serial_ports():
    """ Lists serial port names
        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')
    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


def icon(name):
    return QtWidgets.QIcon(os.path.join(os.path.dirname(__file__),
                           "{}.svg".format(name)))


class WidgetSpacer(QtWidgets.QWidget):
    def __init__(self, parent):
        super(WidgetSpacer, self).__init__(parent)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding)


class SnipplerWidget(QtWidgets.QDockWidget):
    def __init__(self, parent):
        super(SnipplerWidget, self).__init__(i18n('Snipplets'), parent)
        self.setWindowTitle(i18n("Snipplets"))
        self.snippletView = QtWidgets.QListWidget(self)
        self.setWidget(self.snippletView)
        self.loadSnipplets()
        self.snippletView.itemDoubleClicked.connect(self._insertToParent)

    def _insertToParent(self, item):
        print(("insertToParent", item))
        self.parent().editor.insertPlainText(item.toolTip())

    @QtCore.Slot()
    def loadSnipplets(self):
        print("TODO")
        filename = os.path.join(os.path.dirname(__file__), 'snipplets.xml')
        self.snippletView.setStyleSheet('''QToolTip {
            font-family: "monospace";
        }''')
        for child in ElementTree.parse(filename).getroot():
            item = QtWidgets.QListWidgetItem(self.snippletView)
            item.setText(child.attrib["name"])
            item.setToolTip(child.text)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.cwd = QtCore.QDir.homePath()
        self.setWindowTitle(i18n("Edu CIAA MicroPython"))
        self.editor = widgets.PyCodeEdit(server_script=server.__file__)
        self.term = termWidget.Terminal(self)
        self.outline = widgets.PyOutlineTreeWidget()
        self.outline.set_editor(self.editor)
        self.dock_outline = QtWidgets.QDockWidget(i18n('Outline'))
        self.dock_outline.setWidget(self.outline)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_outline)
        self.snippler = SnipplerWidget(self)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.snippler)
        self.stack = QtWidgets.QStackedWidget(self)
        self.stack.addWidget(self.editor)
        self.stack.addWidget(self.term)
        self.setCentralWidget(self.stack)
        self.makeAppToolBar()
        self.i18n()
        self.resize(800, 600)

    def __enter__(self):
        self.show()

    def __exit__(self, t, v, bt):
        self.terminate()

    def i18n(self, actions=None):
        if not actions:
            actions = self.editor.actions()
        for action in actions:
            if not action.isSeparator():
                action.setText(pyqode_i18n.tr(action.text()))
            if action.menu():
                self.i18n(action.menu().actions())

    def terminate(self):
        self.term.close()
        self.editor.backend.stop()

    def makeAppToolBar(self):
        bar = QtWidgets.QToolBar(self)
        bar.setIconSize(QtCore.QSize(48, 48))
        bar.addAction(icon("document-new"), i18n("New"), self.fileNew)
        bar.addAction(icon("document-open"), i18n("Open"), self.fileOpen)
        bar.addAction(icon("document-save"), i18n("Save"), self.fileSave)
        bar.addWidget(WidgetSpacer(self))
        bar.addAction(icon("run"), i18n("Run"), self.progRun)
        bar.addAction(icon("download"), i18n("Download"), self.progDownload)
        self.termAction = bar.addAction(icon("terminal"), i18n("Terminal"),
                                        self.openTerm)
        self.termAction.setCheckable(True)
        self.termAction.setMenu(self.terminalMenu())
        self.addToolBar(bar)

    def terminalMenu(self):
        m = QtWidgets.QMenu(self)
        g = QtWidgets.QActionGroup(m)
        g.triggered.connect(lambda a: self.setPort(a.text()))
        for s in serial_ports():
            a = m.addAction(s)
            g.addAction(a)
            a.setCheckable(True)
        if g.actions():
            g.actions()[0].setChecked(True)
            self.setPort(g.actions()[0].text())
        return m

    def setPort(self, port):
        self.term.open(port, 115200)

    def closeEvent(self, event):
        event.accept()
        if self.editor.dirty:
            x = self.dirtySaveCancel()
            if x == QtWidgets.QMessageBox.Save:
                if not self.fileSave():
                    event.ignore()
            elif x == QtWidgets.QMessageBox.Cancel:
                event.ignore()

    def fileNew(self):
        if self.editor.dirty:
            x = self.dirtySaveCancel()
            if x == QtWidgets.QMessageBox.Save:
                if not self.fileSave():
                    return
            elif x == QtWidgets.QMessageBox.Cancel:
                return
        self.editor.file.close()

    def dirtySaveCancel(self):
        d = QtWidgets.QMessageBox()
        d.setWindowTitle(i18n("Question"))
        d.setText(i18n("Document was modify"))
        d.setInformativeText(i18n("Save changes?"))
        d.setIcon(QtWidgets.QMessageBox.Question)
        d.setStandardButtons(QtWidgets.QMessageBox.Save |
                             QtWidgets.QMessageBox.Discard |
                             QtWidgets.QMessageBox.Cancel)
        return d.exec_()

    def fileOpen(self):
        if self.editor.dirty:
            x = self.dirtySaveCancel()
            if x == QtWidgets.QMessageBox.Save:
                if not self.fileSave():
                    return
            elif x == QtWidgets.QMessageBox.Cancel:
                return
        name, dummy = QtWidgets.QFileDialog.getOpenFileName(
            self, i18n("Open File"), self.cwd,
            i18n("Python files (*.py);;All files (*)"))
        if name:
            self.editor.file.open(name)
            self.cwd = os.path.dirname(name)

    def fileSave(self):
        if not self.editor.file.path:
            path, dummy = QtWidgets.QFileDialog.getSaveFileName(
                self, i18n("Save File"), self.cwd,
                i18n("Python files (*.py);;All files (*)"))
        else:
            path = self.editor.file.path
        if not path:
            return False
        self.editor.file.save(path)
        return True

    def openTerm(self):
        if self.termAction.isChecked():
            self.stack.setCurrentIndex(1)
            self.term.setFocus()
        else:
            self.stack.setCurrentIndex(0)

    def progRun(self):
        self._targetExec(self.editor.toPlainText())

    def _targetExec(self, script):
        def progrun2(text):
            # print("{} {}".format(4, progrun2.text))
            progrun2.text += text
            if progrun2.text.endswith(b'\x04>'):
                # print("{} {}".format(5, progrun2.text))
                return True
            return False

        def progrun1(text):
            progrun1.text += text
            # print("{} {}".format(2, progrun1.text))
            if progrun1.text.endswith(b'to exit\r\n>'):
                progrun2.text = b''
                # print("{} {}".format(3, progrun1.text))
                cmd = 'print("\033c")\r{}\r\x04'.format(script)
                # print("{} {}".format(3.5, cmd))
                self.term.remoteExec(bytes(cmd, 'utf-8'), progrun2)
                return True
            return False
        progrun1.text = b''
        # print(1)
        self.term.remoteExec(b'\r\x03\x03\r\x01', progrun1)

    def progDownload(self):
        print("TODO")


app = QtWidgets.QApplication(sys.argv)
with MainWindow():
    app.exec_()