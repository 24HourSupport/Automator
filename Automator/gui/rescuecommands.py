import logging
import os
import time

from PyQt6.QtGui import QPaintEvent, QCloseEvent
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QGroupBox, QHBoxLayout, QTextEdit, QProgressBar

from Automator.gui.common_components import ProcessWatcher, RestartDialog


class RescueCommandsWindow(QDialog):
    def __init__(self, *args, **kwargs):
        super(RescueCommandsWindow, self).__init__(*args, **kwargs)
        self.layout = QVBoxLayout()

        self.logger = logging.getLogger('Rescuecommands')
        self.sfc_watcher: ProcessWatcher
        self.dism_watcher: ProcessWatcher

        group_box = QGroupBox(self)
        self.button_layout = QHBoxLayout()
        button_data = [
            ('Start SFC scan', self.sfc_start),
            ('Start DISM scan', self.dism_start),
            ('Start CHKDSK scan', self.chkdsk_start)
        ]
        for button_text, callback in button_data:
            button = QPushButton(button_text, self)
            button.setMaximumWidth(150)
            button.setAutoDefault(False)
            if callback:
                button.clicked.connect(callback)
            self.button_layout.addWidget(button)
        group_box.setLayout(self.button_layout)
        self.layout.addWidget(group_box)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar_value = 0
        # Start with a value of 0 since the empty space looks weird otherwise
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar)

        self.text_area = QTextEdit(self)
        self.text_area.setPlaceholderText('Click a button to start testing')
        self.text_area.setReadOnly(True)
        self.layout.addWidget(self.text_area)

        self.setWindowTitle('SFC / DISM / CHKDSK scans')
        self.setMinimumSize(500, 300)
        self.setLayout(self.layout)

    def paintEvent(self, a0: QPaintEvent) -> None:
        self.progress_bar.setValue(self.progress_bar_value)

    def closeEvent(self, a0: QCloseEvent) -> None:
        if hasattr(self, 'sfc_watcher'):
            if not self.sfc_watcher.has_finished():
                self.sfc_watcher.cancel()
        if hasattr(self, 'dism_watcher'):
            if not self.dism_watcher.has_finished():
                self.dism_watcher.cancel()
        if hasattr(self, 'sfc_watcher') and hasattr(self, 'dism_watcher'):
            RestartDialog('To finish up the SFC and DISM scans, you\'ll have to restart').exec()

    def _for_each_button(self, enable=False, ignore_button=-1, ignore_button_text=None, click_connect=None):
        for i in range(self.button_layout.count()):
            button_widget = self.button_layout.itemAt(i).widget()
            # In case any function has to do special things with the buttons
            if i == ignore_button:
                if click_connect:
                    button_widget.disconnect()
                    button_widget.clicked.connect(click_connect)
                # If a text was supplied, set the buttons text to that
                if ignore_button_text:
                    button_widget.setText(ignore_button_text)
            else:
                button_widget.setEnabled(enable)

    def _setup_scan(self, scan_name: str):
        self.progress_bar_value = 0
        self.text_area.clear()
        self.text_area.append('Starting {} scan...\n'.format(scan_name))
        self.logger.info('Starting {} scan'.format(scan_name))

    def _cancel_scan(self, scan_name: str):
        self.text_area.append('{} scan cancelled'.format(scan_name))
        self.logger.info('{} scan cancelled'.format(scan_name))

    def _check_scan(self, scan_name: str):
        if self.progress_bar_value != self.progress_bar.maximum():
            self.logger.warning('{} scan did not finish successfully!'.format(scan_name))
            self.text_area.append('{} scan did not finish successfully!'.format(scan_name))
        else:
            self.logger.info('{} scan finished'.format(scan_name))
            self.text_area.append('\n{} scan finished'.format(scan_name))

    def sfc_start(self):
        self._setup_scan('SFC')

        # noinspection PyAttributeOutsideInit
        self.sfc_watcher = ProcessWatcher('sfc /scannow', 'utf_16_le')
        # noinspection PyUnresolvedReferences
        self.sfc_watcher.processFinished.connect(self.sfc_done)
        # noinspection PyUnresolvedReferences
        self.sfc_watcher.newData.connect(self.sfc_update)
        try:
            self.sfc_watcher.start()
        except RuntimeError:
            self.logger.info('SFC scan aborted')
            return

        self._for_each_button(
            ignore_button=0, ignore_button_text='Cancel SFC scan', click_connect=self.sfc_cancel
        )

    def sfc_cancel(self):
        self.sfc_watcher.cancel()
        self._cancel_scan('SFC')

    def sfc_update(self, line: str):
        # If the line has a % in it, update the progress bar and don't display it in the main log
        percent_index = line.find('%')
        if percent_index != -1:
            percent_part = next(x for x in line.split(' ') if '%' in x)
            percent = int(percent_part.replace('%', ''))
            if percent > self.progress_bar_value:
                self.progress_bar_value = percent
        else:
            self.text_area.append(line)

        self.update()

    def sfc_done(self):
        self._for_each_button(
            enable=True, ignore_button=0, ignore_button_text='Start SFC scan', click_connect=self.sfc_start
        )
        self._check_scan('SFC')

    def dism_start(self):
        self._setup_scan('DISM')
        # noinspection PyAttributeOutsideInit
        self.dism_watcher = ProcessWatcher('DISM /Online /Cleanup-Image /RestoreHealth', 'utf_8')
        # noinspection PyUnresolvedReferences
        self.dism_watcher.processFinished.connect(self.dism_done)
        # noinspection PyUnresolvedReferences
        self.dism_watcher.newData.connect(self.dism_update)
        try:
            self.dism_watcher.start()
        except RuntimeError:
            self.logger.info('DISM scan aborted')
            return

        self._for_each_button(
            ignore_button=1, ignore_button_text='Cancel DISM scan', click_connect=self.dism_cancel
        )

    def dism_cancel(self):
        self.dism_watcher.cancel()
        self._cancel_scan('DISM')

    def dism_update(self, line: str):
        percent_index = line.find('%')
        if percent_index != -1:
            percent = line[percent_index-5:percent_index-2]
            percent = percent.replace('=', '').replace(' ', '')
            percent = int(percent)
            if percent > self.progress_bar_value:
                self.progress_bar_value = percent
        else:
            self.text_area.append(line)

        self.update()

    def dism_done(self):
        self._for_each_button(
            enable=True, ignore_button=1, ignore_button_text='Start DISM scan', click_connect=self.dism_start
        )

        self._check_scan('DISM')

    def chkdsk_start(self):
        self._setup_scan('CHKDSK')

        with open(os.path.join(os.path.expandvars('%TEMP%'), 'chkdsk_temp.bat'), 'w') as f:
            f.write("""
            @echo off\n
            cd "%TEMP%"\n
            chkdsk C: /r /x < chkdsk_y.txt\n
            echo 1 >done.txt
            """)

        with open(os.path.join(os.path.expandvars('%TEMP%'), 'chkdsk_y.txt'), 'w') as f:
            f.write('Y\n')

        if os.path.exists(os.path.join(os.path.expandvars('%TEMP%'), 'done.txt')):
            os.remove(os.path.join(os.path.expandvars('%TEMP%'), 'done.txt'))

        # noinspection PyAttributeOutsideInit
        self.chkdsk_watcher = ProcessWatcher(
            'cmd /c %TEMP%\\chkdsk_temp.bat', 'utf-8', skip_last_line=False
        )
        # noinspection PyUnresolvedReferences
        self.chkdsk_watcher.processFinished.connect(self.chkdsk_done)
        # noinspection PyUnresolvedReferences
        self.chkdsk_watcher.newData.connect(self.text_area.append)
        self.chkdsk_watcher.start()

        self._for_each_button()

        while True:
            if os.path.exists(os.path.join(os.path.expandvars('%TEMP%'), 'done.txt')):
                break
        time.sleep(0.5)
        # noinspection PyProtectedMember
        self.chkdsk_watcher._finish()

    def chkdsk_done(self):
        self.logger.info('CHKDSK scan done')

        # Remove all temporary files created
        temp_path = os.path.expandvars('%TEMP%')
        for filename in ['chkdsk_temp.bat', 'chkdsk_y.txt', 'done.txt']:
            os.remove(os.path.join(temp_path, filename))

        # Re-enable buttons
        self._for_each_button(enable=True)

        RestartDialog('To run the CHKDSK scan, you will have to restart your computer').exec()
