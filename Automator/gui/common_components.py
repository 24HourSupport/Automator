import logging
import os
import subprocess
import time
from enum import Enum, auto

import requests
import wmi
from PyQt6.QtCore import pyqtSignal, Qt, QThread, QObject
from PyQt6.QtGui import QMouseEvent, QMovie, QPixmap
from PyQt6.QtWidgets import QLabel, QWidget, QHBoxLayout, QRadioButton, QAbstractButton, QMessageBox, QVBoxLayout
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

from Automator.misc.cmd import silent_run_as_admin

icons_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'icons')


class RestartDialog(QMessageBox):
    """
    Displays a "Restart required" dialog with the options to restart now / later
    """
    def __init__(self, text: str = 'A restart is required to complete the scans', title_text: str = 'Restart required'):
        super(RestartDialog, self).__init__(
            QMessageBox.Icon.Information,
            title_text,
            text
        )
        self.addButton('Restart now', QMessageBox.ButtonRole.AcceptRole)
        self.addButton('Restart later', QMessageBox.ButtonRole.RejectRole)
        self.buttonClicked.connect(self.on_restart)

    def on_restart(self, button: QAbstractButton):
        if self.buttonRole(button) == QMessageBox.ButtonRole.AcceptRole:
            subprocess.Popen(['shutdown', '/r', '/t', '0'])


class ProcessWatcher(QObject):
    """
    Spawns a process as admin and sends signals if new stdout/stderr data is available or the process is closed
    """
    processFinished = pyqtSignal()
    newData = pyqtSignal(str)

    def __init__(self, process: str, encoding: str, skip_last_line: bool = True, *args, **kwargs):
        super(ProcessWatcher, self).__init__(*args, **kwargs)
        self.process = process
        self.encoding = encoding
        self.skip_last_line = skip_last_line
        self.lines_to_skip = 0
        process_name = process.split(' ')[0]
        # This is only used to check if the process is still running, so it's easier to append the '.exe' here
        self.process_name = process_name + '.exe'
        self.cmd_proc = None
        self.logger = logging.getLogger('ProcessWatcher ' + self.process_name)
        self.filename = process_name + str(round(time.time())) + '.log'
        self.observer = Observer()

    def _setup_events(self) -> PatternMatchingEventHandler:
        self.logger.debug('Setting up events...')
        self.logger.debug('File name is {}'.format(self.filename))
        event_handler = PatternMatchingEventHandler(patterns=[self.filename])
        self.observer = Observer()
        self.observer.schedule(event_handler, os.path.expandvars('%TEMP%'), recursive=False)
        event_handler.on_modified = lambda e: self._file_modified()
        return event_handler

    def _file_modified(self):
        log_file = os.path.join(os.path.expandvars('%TEMP%'), self.filename)
        with open(log_file, encoding=self.encoding) as f:
            lines = f.readlines()
        if self.skip_last_line:
            lines.pop(-1)
        self.logger.debug('File was modified. Got {} new lines'.format(len(lines[self.lines_to_skip:])))
        for line in lines[self.lines_to_skip:]:
            line = line.replace('\n', '')
            if line:
                # noinspection PyUnresolvedReferences
                self.newData.emit(line)
        self.lines_to_skip = len(lines)
        potential_sfc_proc = wmi.WMI().Win32_Process(name=self.process_name)
        if not potential_sfc_proc:
            self._finish()

    def _finish(self):
        self.observer.stop()
        self.observer = None
        log_file = os.path.join(os.path.expandvars('%TEMP%'), self.filename)
        os.remove(log_file)
        self.cmd_proc.terminate()
        os.remove(log_file[:-4] + '.bat')
        # noinspection PyUnresolvedReferences
        self.processFinished.emit()

    def start(self):
        self.logger.debug('Starting process...')
        self._setup_events()
        # Display the UAC prompt
        log_file = os.path.join(os.path.expandvars('%TEMP%'), self.filename)
        proc_or_false = silent_run_as_admin(self.process + ' 1>{} 2>&1'.format(log_file))
        if not proc_or_false:
            raise RuntimeError('User has not accepted the UAC prompt')
        # Wait for the program to start
        while True:
            try:
                wmi.WMI().Win32_Process(name=self.process_name)
            # AttributeError is normal if the process doesn't exist yet
            except AttributeError:
                pass
            else:
                break
        self.observer.start()
        # For... reasons, Windows doesn't check if a file has changed unless it's actually read out.
        # So here we construct a small batch file to read out the file continuously
        bat_name = self.filename[:-4] + '.bat'
        with open(os.path.join(os.path.expandvars('%TEMP%'), bat_name), 'w') as f:
            f.write('''
            @echo off\n
            :start\n
            timeout /nobreak /t 2 >nul\n
            type "{}" 1>nul 2>&1\n
            goto start\n
            '''.format(log_file))
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        self.cmd_proc = subprocess.Popen(
            ['cmd', '/c', os.path.join(os.path.expandvars('%TEMP%'), bat_name)],
            startupinfo=startupinfo
        )

    def cancel(self):
        potential_sfc_proc = wmi.WMI().Win32_Process(name=self.process_name)
        if not potential_sfc_proc:
            raise RuntimeError('Process could not be found')
        # Once we end the process, the file will be written to one last time. This will then run _file_modified(),
        # which in turn will then run _finished (again), and that will then fail because the process isn't running
        # anymore. With this, we don't get the last bit of % / messages, but I doubt that's gonna matter when the user
        # cancels it anyways
        self.observer.unschedule_all()
        # Send the terminate signal to the process
        # FIXME: This will target the first process that is found. With something like SFC this is fine, but if we
        #        only run CMD for example, we will end other processes not "belonging" to us
        potential_sfc_proc[0].Terminate()
        # Wait for it to close
        while True:
            potential_sfc_proc = wmi.WMI().Win32_Process(name=self.process_name)
            if not potential_sfc_proc:
                break
        self._finish()

    def has_finished(self) -> bool:
        return not wmi.WMI().Win32_Process(name=self.process_name)


class WrappingLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super(WrappingLabel, self).__init__(*args, **kwargs)
        self.setWordWrap(True)

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            # noinspection PyUnresolvedReferences
            self.clicked.emit()


class WrappingRadioButton(QWidget):
    # Thanks Qt for not providing Word Wrapping to QRadioButtons natively
    def __init__(self, text: str, *args, **kwargs):
        super(WrappingRadioButton, self).__init__(*args, **kwargs)
        self._layout = QHBoxLayout()
        self.button = QRadioButton()
        self._label = WrappingLabel(text)
        self.button.text = self._label.text
        # noinspection PyUnresolvedReferences
        self._label.clicked.connect(self.button.click)
        self._layout.addWidget(self.button, 0)
        self._layout.addWidget(self._label, 1)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)


class DownloaderThread(QThread):
    downloadProgress = pyqtSignal(int)

    def __init__(self, url: str, output_path: str, buffer_size: int = 10240, *args, **kwargs):
        super(DownloaderThread, self).__init__(*args, **kwargs)
        self.url = url
        self.output_fp = open(output_path, 'wb')
        self.chunk_size = buffer_size

    def run(self):
        res = requests.get(self.url, stream=True)
        file_size = int(res.headers['Content-Length'])
        for index, chunk in enumerate(res.iter_content(self.chunk_size)):
            self.output_fp.write(chunk)
            progress = self.chunk_size * (index + 1) / file_size
            # noinspection PyUnresolvedReferences
            self.downloadProgress.emit(int(progress))
        self.output_fp.close()
        self.exit(0)


class StepListItemStatus(Enum):
    DEFAULT = auto()
    SUCCESS = auto()
    FAILURE = auto()
    IN_PROGRESS = auto()


class StepListItem(QWidget):
    def __init__(self, text: str, status: StepListItemStatus = StepListItemStatus.DEFAULT, *args, **kwargs):
        super(StepListItem, self).__init__(*args, **kwargs)
        layout = QHBoxLayout(self)

        self._statusLabel = QLabel(self)
        self._label = QLabel(text, self)

        self._in_progress_movie = QMovie(os.path.join(icons_dir, 'loading.gif'))

        layout.addWidget(self._statusLabel, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._label, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()

        self.status = status
        self.setContentsMargins(0, 0, 0, 0)

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, new_status: StepListItemStatus):
        self._status = new_status

        # Since the in_progress icon is a gif, it requires some extra setup
        if new_status == StepListItemStatus.IN_PROGRESS:
            self._statusLabel.setPixmap(QPixmap())
            self._statusLabel.setMovie(self._in_progress_movie)
            self._in_progress_movie.start()
        else:
            self._statusLabel.setMovie(QMovie())
            self._in_progress_movie.stop()

            status_to_icon = {
                StepListItemStatus.DEFAULT: 'todo.svg',
                StepListItemStatus.SUCCESS: 'success.svg',
                StepListItemStatus.FAILURE: 'error.svg'
            }
            self._statusLabel.setPixmap(QPixmap(
                os.path.join(icons_dir, status_to_icon[new_status])
            ).scaled(
                int(self._statusLabel.width() / 2), int(self._statusLabel.height() / 2),
                Qt.AspectRatioMode.KeepAspectRatio
            ))

    @property
    def text(self):
        return self._label.text()

    @text.setter
    def text(self, new_text: str):
        self._label.setText(new_text)


class StepList(QWidget):
    def __init__(self, steps: list[str], *args, **kwargs):
        super(StepList, self).__init__(*args, **kwargs)
        self.setLayout(QVBoxLayout(self))
        self.steps = steps

        self.add_steps(steps)
        self.setContentsMargins(0, 0, 0, 0)

    def add_steps(self, steps: list[str]):
        self.steps = steps
        layout = self.layout()
        for step in steps:
            layout.addWidget(StepListItem(step))

    def set_step_status(self, index: int, status: StepListItemStatus):
        if index >= len(self.steps):
            raise ValueError('Invalid step index specified')
        self.layout().itemAt(index).widget().status = status
