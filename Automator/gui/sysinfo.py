import logging
import os.path
import shutil
from typing import Union
# noinspection PyUnresolvedReferences
from win32com.shell import shell, shellcon

import wmi
from PyQt6.QtCore import pyqtSignal, Qt, QProcess, QMimeData, QUrl
from PyQt6.QtGui import QMouseEvent, QCloseEvent, QGuiApplication
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QGroupBox, QGridLayout, QLabel, QSpacerItem, QSizePolicy, \
    QButtonGroup, QRadioButton, QVBoxLayout, QWidget, QLineEdit, QPushButton, QMessageBox

from Automator.misc.platform_info import is_laptop


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


class SysInfoWindow(QDialog):
    def __init__(self, *args, **kwargs):
        super(SysInfoWindow, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger('SysInfo')
        self.msinfo_proc = QProcess()
        self.msinfo_proc.finished.connect(self.msinfo_finished)

        self.layout = QHBoxLayout()
        self._layout = QVBoxLayout()

        general_group = QGroupBox('General questions')
        self.desktop_group = QGroupBox('Desktop-specific questions')
        general_group_layout = QGridLayout()

        # Overclock
        general_group_layout.addWidget(WrappingLabel(
            'Did you do any overclocks/underclocks/undervolts anywhere?'
        ), 0, 0, 1, 2)

        self.overclock_buttons = QButtonGroup()
        overclock_button_yes = QRadioButton('Yes')
        self.overclock_buttons.addButton(overclock_button_yes, 1)
        general_group_layout.addWidget(overclock_button_yes, 1, 0)
        overclock_button_no = QRadioButton('No')
        self.overclock_buttons.addButton(overclock_button_no, 2)
        general_group_layout.addWidget(overclock_button_no, 1, 1)

        # Install method
        general_group_layout.addWidget(
            WrappingLabel(
                'When you got this computer, which of these methods did you do to get Windows up and running? '
            ), 2, 0, 1, 2
        )

        self.install_method = QButtonGroup()

        came_with_pc_widget = WrappingRadioButton('I just bought the computer and it came with Windows already.')
        self.install_method.addButton(came_with_pc_widget.button, 1)
        general_group_layout.addWidget(came_with_pc_widget, 3, 0, 1, 2)

        usb_install_widget = WrappingRadioButton(
            'I created a Windows USB, booted into it with no drives connected (with the exception of the USB and the '
            'drive I wanted to install Windows on), deleted all partitions if there were any and installed in the '
            'unallocated space.'
        )
        self.install_method.addButton(usb_install_widget.button, 2)
        general_group_layout.addWidget(usb_install_widget, 4, 0, 1, 2)

        premade_install_widget = WrappingRadioButton(
            'I took an already made Windows USB or CD (like if you bought one from a shop), booted into it with no '
            'drives connected (with the exception of the USB and the drive I wanted to install Windows on), '
            'deleted all partitions if there were any and installed in the unallocated space.'
        )
        self.install_method.addButton(premade_install_widget.button, 3)
        general_group_layout.addWidget(premade_install_widget, 5, 0, 1, 2)

        not_all_drives_widget = WrappingRadioButton(
            'I did either Option 2 or 3, but did not remove all drives before doing so (with the exception of the USB '
            'and the drive I wanted to install Windows on), or simply did upgrade or installed in a partition without '
            'deleting it.'
        )
        self.install_method.addButton(not_all_drives_widget.button, 4)
        general_group_layout.addWidget(not_all_drives_widget, 6, 0, 1, 2)

        clone_transfer_widget = WrappingRadioButton('I cloned / transferred a Windows install from another computer.')
        self.install_method.addButton(clone_transfer_widget.button, 5)
        general_group_layout.addWidget(clone_transfer_widget, 7, 0, 1, 2)

        # Tweaks
        general_group_layout.addWidget(WrappingLabel(
            'Did you modify Windows? Please answer if you followed any debloat guide, anti spy scripts or '
            'applications, disabled Windows updates, pirated Windows, or ANY MODIFICATION. PLEASE DISCLOSE THIS. This '
            'includes you BLOCKING Microsoft domains from connecting to your computer (regardless if this is outside, '
            'like with a pihole or a VPN or whatever, this counts as modifying the behavior of Windows) '
        ), 8, 0, 1, 2)

        self.tweak_buttons = QButtonGroup()
        tweak_button_yes = QRadioButton('Yes')
        self.tweak_buttons.addButton(tweak_button_yes, 1)
        general_group_layout.addWidget(tweak_button_yes, 9, 0)
        tweak_button_no = QRadioButton('No')
        self.tweak_buttons.addButton(tweak_button_no, 2)
        general_group_layout.addWidget(tweak_button_no, 9, 1)

        # Desktop/Laptop
        general_group_layout.addWidget(WrappingLabel(
            'My system is a...'
        ), 10, 0, 1, 2)

        self.platform_buttons = QButtonGroup()
        platform_button_desktop = QRadioButton('Desktop')
        platform_button_desktop.clicked.connect(lambda: self.desktop_group.setEnabled(True))
        self.platform_buttons.addButton(platform_button_desktop, 1)
        general_group_layout.addWidget(platform_button_desktop, 11, 0)
        platform_button_laptop = QRadioButton('Laptop')
        platform_button_laptop.clicked.connect(lambda: self.desktop_group.setEnabled(False))
        self.platform_buttons.addButton(platform_button_laptop, 2)
        if is_laptop():
            platform_button_laptop.click()
        else:
            platform_button_desktop.click()
        general_group_layout.addWidget(platform_button_laptop, 11, 1)

        general_group_layout.addItem(
            QSpacerItem(
                0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
        )

        general_group.setLayout(general_group_layout)
        self.layout.addWidget(general_group)

        #
        # Desktop group starts here
        #

        desktop_group_layout = QGridLayout()
        psu_model = WrappingLabel(
            'What power supply model do you have? '
            '<a href="https://www.xtremegaminerd.com/two-easy-ways-to-know-what-power-supply-you-have/">'
            'See how to find this out</a>. <b>Do not just tell us the wattage. We want the exact model.</b> Telling us '
            'only the wattage is not helpful!'
        )
        psu_model.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        psu_model.setTextFormat(Qt.TextFormat.RichText)
        psu_model.setOpenExternalLinks(True)
        desktop_group_layout.addWidget(psu_model, 0, 0, 1, 2)

        self.psu_model = QLineEdit()
        desktop_group_layout.addWidget(self.psu_model, 1, 0, 1, 2)

        pcie_riser = WrappingLabel(
            'Are you using PCIe riser cables or are you connecting your GPU (and any PCI card) directly to the '
            'motherboard? '
            '<a href="https://i.imgur.com/MbYnMvC.png">See this photo if you are not sure what this means</a>.'
        )
        pcie_riser.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        pcie_riser.setTextFormat(Qt.TextFormat.RichText)
        pcie_riser.setOpenExternalLinks(True)
        desktop_group_layout.addWidget(pcie_riser, 2, 0, 1, 2)
        self.pcie_riser_buttons = QButtonGroup()
        pcie_riser_button_yes = QRadioButton('Using PCIe riser cables')
        self.pcie_riser_buttons.addButton(pcie_riser_button_yes, 1)
        desktop_group_layout.addWidget(pcie_riser_button_yes, 3, 0)
        pcie_riser_button_no = QRadioButton('Connecting directly to MoBo')
        self.pcie_riser_buttons.addButton(pcie_riser_button_no, 2)
        desktop_group_layout.addWidget(pcie_riser_button_no, 3, 1)

        desktop_group_layout.addWidget(WrappingLabel(
            'Are you using the power supply cables that came with your power supply or third party ones? Are you using '
            'any extensions? Are you using any adapters?'
        ), 4, 0, 1, 2)
        self.psu_cables = QLineEdit()
        desktop_group_layout.addWidget(self.psu_cables, 5, 0, 1, 2)

        psu_model = WrappingLabel(
            'If you have a GPU that requires multiple power connectors, <a href="https://i.imgur.com/MjToCN7.jpeg">'
            'are you connecting them using individual power connectors coming from the PSU, or using a single cable '
            'that splits into two or more</a>?'
        )
        psu_model.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        psu_model.setTextFormat(Qt.TextFormat.RichText)
        psu_model.setOpenExternalLinks(True)
        desktop_group_layout.addWidget(psu_model, 6, 0, 1, 2)
        self.gpu_pwer_connector_buttons = QButtonGroup()
        gpu_pwer_connector_button_yes = QRadioButton('Using individual power connectors')
        self.gpu_pwer_connector_buttons.addButton(gpu_pwer_connector_button_yes, 1)
        desktop_group_layout.addWidget(gpu_pwer_connector_button_yes, 7, 0)
        gpu_pwer_connector_button_no = QRadioButton('Using a single cable that splits up')
        self.gpu_pwer_connector_buttons.addButton(gpu_pwer_connector_button_no, 2)
        desktop_group_layout.addWidget(gpu_pwer_connector_button_no, 7, 1)

        monitor_connection = WrappingLabel(
            'Where are you connecting your monitor(s)? To your motherboard or to your graphics card? '
            '<a href="https://i.imgur.com/z4dHNGU.jpg">See this photo if you are not sure what this means</a>.'
        )
        monitor_connection.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        monitor_connection.setTextFormat(Qt.TextFormat.RichText)
        monitor_connection.setOpenExternalLinks(True)
        desktop_group_layout.addWidget(monitor_connection, 8, 0, 1, 2)
        self.monitor_connection_buttons = QButtonGroup()
        monitor_connection_button_yes = QRadioButton('To the Motherboard')
        self.monitor_connection_buttons.addButton(monitor_connection_button_yes, 1)
        desktop_group_layout.addWidget(monitor_connection_button_yes, 9, 0)
        monitor_connection_button_no = QRadioButton('To the graphics card')
        self.monitor_connection_buttons.addButton(monitor_connection_button_no, 2)
        desktop_group_layout.addWidget(monitor_connection_button_no, 9, 1)

        desktop_group_layout.addItem(
            QSpacerItem(
                0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
        )

        self.desktop_group.setLayout(desktop_group_layout)
        self.layout.addWidget(self.desktop_group)
        self._layout.addLayout(self.layout)
        finish_button = QPushButton('Finish')
        finish_button.clicked.connect(self.finish)
        finish_button.setMinimumWidth(200)
        self._layout.addWidget(finish_button, 0, Qt.AlignmentFlag.AlignRight)

        self.setWindowTitle('MSInfo32 Report')
        self.setMinimumSize(1200, 500)
        self.setLayout(self._layout)

    def closeEvent(self, a0: QCloseEvent) -> None:
        if self.msinfo_proc.state() != QProcess.ProcessState.NotRunning:
            a0.ignore()
        else:
            a0.accept()

    def finish(self):
        self.logger.info('User pressed finish button')
        for i in range(self.layout.count()):
            widget = self.layout.itemAt(i).widget()
            widget.setEnabled(False)
        finish_button = self._layout.itemAt(1).widget()
        finish_button.setEnabled(False)
        self.msinfo_proc.start(
            'msinfo32',
            ['/report', os.path.join(os.path.expandvars('%ProgramData%'), '24HS-Automator', 'Sysinfo.txt')],
        )

    def msinfo_finished(self):
        self.logger.info('MsInfo32 finished')

        file_path = os.path.join(os.path.expandvars('%ProgramData%'), '24HS-Automator', 'Sysinfo.txt')

        # Re-enable widgets
        general_section = self.layout.itemAt(0).widget()
        general_section.setEnabled(True)
        desktop_section = self.layout.itemAt(1).widget()
        desktop_section.setEnabled(False if self.platform_buttons.checkedId() != 2 else True)
        finish_button = self._layout.itemAt(1).widget()
        finish_button.setEnabled(True)

        # Add our own info
        no_info_text = 'NoInfoGiven'
        with open(file_path, 'a', encoding='utf_16_le') as f:
            f.write('\n')
            f.write('[Automator_additionalInfo]\n')
            f.write('\n')
            f.write('Item\tValue\t\n')
            f.write('Overclocks\t{}\t\n'.format(get_button_text(self.overclock_buttons, no_info_text)))
            f.write('InstallMethod\t{}\t\n'.format(get_button_id(self.install_method, no_info_text)))
            f.write('ModifiedWindows\t{}\t\n'.format(get_button_text(self.tweak_buttons, no_info_text)))
            f.write('UserSpecifiedSystemType\t{}\t\n'.format(get_button_text(self.platform_buttons)))
            f.write('LaptopCertainty\t{}\t\n'.format(str(is_laptop())))
            f.write('PSUModel\t{}\t\n'.format(self.psu_model.text() if self.psu_model.text() else no_info_text))
            f.write('GPUConnectionMethod\t{}\t\n'.format(get_button_text(self.pcie_riser_buttons, no_info_text)))
            f.write('PSUCables\t{}\t\n'.format(self.psu_cables.text() if self.psu_cables.text() else no_info_text))
            f.write('GPUPowerConnectors\t{}\t\n'.format(get_button_text(self.gpu_pwer_connector_buttons, no_info_text)))
            f.write('MonitorConnection\t{}\t\n'.format(get_button_text(self.monitor_connection_buttons, no_info_text)))
            f.write('\n')
            f.write('[Automator_ramInfo]\n')
            f.write('\n')
            f.write('Name\tSpeed\tDeviceLocator\tPartNumber\tManufacturer\t\n')
            for ram_stick in wmi.WMI().Win32_PhysicalMemory():
                f.write('{}\t{}\t{}\t{}\t{}\t\n'.format(
                    ram_stick.Name, ram_stick.Speed, ram_stick.DeviceLocator, ram_stick.PartNumber, ram_stick.Manufacturer
                ))

        # Copy file to clipboard
        clipboard = QGuiApplication.clipboard()
        file = QMimeData()
        file.setUrls([QUrl.fromLocalFile(file_path)])
        clipboard.setMimeData(file)

        # Try to copy the file to the desktop
        desktop_folder_path = shell.SHGetKnownFolderPath(shellcon.FOLDERID_Desktop, 0, 0)
        try:
            shutil.copyfile(file_path, os.path.join(desktop_folder_path, os.path.basename(file_path)))
        except PermissionError:
            self.logger.warning('Could not copy file to Desktop, trying Downloads instead')
            shutil.copyfile(
                file_path,
                os.path.join(os.path.expandvars('%USERPROFILE%'), 'Downloads', os.path.basename(file_path))
            )
            file_location = 'in your Downloads folder'
        else:
            file_location = 'onto your Desktop'

        # Prompt the user that their system info is ready
        QMessageBox(
            QMessageBox.Icon.Information,
            'System info exported!',
            f'Your system info was saved {file_location}'
        ).exec()
        # Close this window so the user doesn't accidentally click "Finish" twice
        self.close()


def get_button_id(button_group: QButtonGroup, fallback: str = None) -> Union[str, None]:
    button_id = button_group.checkedId()
    if button_id == -1:
        return fallback
    return str(button_id)


def get_button_text(button_group: QButtonGroup, fallback: str = None) -> Union[str, None]:
    button = button_group.checkedButton()
    if button:
        return button.text()
    return fallback
