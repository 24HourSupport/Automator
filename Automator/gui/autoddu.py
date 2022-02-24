import logging
import sys

import wmi
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QInputDialog, QMessageBox

from Automator.gui.common_components import WrappingLabel, StepList, StepListItemStatus
from Automator.misc.platform_info import get_gpu_manufacturers
from Automator.misc.versioninfo import fido_get_rel_list


class AutoDDU(QDialog):
    def __init__(self, *args, **kwargs):
        super(AutoDDU, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger('AutoDDU')
        self.wmi_inst = wmi.WMI()

        layout = QVBoxLayout(self)

        layout.addWidget(WrappingLabel(
            'DDU is going to completely remove your GPU drivers and re-install them afterwards.\n'
            'It is going to take 10-15 minutes. Interrupting it is not possible, and forcing a\n'
            'reboot can cause issues. Once everything\'s done, a big "Done" text will be displayed.',
            layout.widget()
        ))

        start_button = QPushButton('Start', layout.widget())
        start_button.pressed.connect(self.start_autoddu)
        layout.addWidget(start_button)

        self.setWindowTitle('AutoDDU')
        self.setMinimumSize(500, 300)

        self.ddu_steps = StepList([
            'Get required info',
            'Check Windows version',
            'Create backup user account',
            'Download programs',
            'Enable safe mode',
            'Reboot to enter safe mode',
            'Run DDU',
            'Disable safe mode',
            'Reboot to exit safe mode',
            'Re-install GPU drivers',
            'Re-enable Windows Update'
        ])

    def start_autoddu(self):
        self.logger.info('Starting AutoDDU')

        # noinspection PyTypeChecker
        layout: QVBoxLayout = self.layout()

        for i in range(layout.count()):
            layout.removeWidget(layout.itemAt(0).widget())

        layout.addWidget(WrappingLabel(
            'AutoDDU in progress...',
            layout.widget()
        ))

        layout.addWidget(self.ddu_steps)
        layout.addStretch()
        self.setMinimumSize(500, 550)

        self.ddu_steps.set_step_status(0, StepListItemStatus.IN_PROGRESS)

        # Get the number of GPUs installed in the system
        valid_manufacturers = ['NVIDIA', 'Advanced Micro Devices, Inc.', 'Intel Corporation']
        gpu_manufacturers = get_gpu_manufacturers()
        has_invalid_manufacturers = any(manufacturer not in valid_manufacturers for manufacturer in gpu_manufacturers)

        if has_invalid_manufacturers:
            selected_driver = QInputDialog.getItem(
                self,
                'Unsupported GPU drivers',
                'Automator has detected that a GPU driver in this system is not supported.\n'
                'This could be caused by an incomplete installation, or just an unpopular GPU\n'
                'manufacturer. Please select the driver you want to uninstall.',
                valid_manufacturers,
                editable=False
            )
        else:
            if len(gpu_manufacturers) > 1:
                selected_driver = QInputDialog.getItem(
                    self,
                    'Select GPU driver to uninstall',
                    'You have more than one GPU driver installed. This is normal on\n'
                    'laptops (which have both an iGPU as well as a dGPU). Please select the\n'
                    'driver you want to uninstall.',
                    list(gpu_manufacturers)
                )
            else:
                manufacturer = gpu_manufacturers.pop()
                msgbox = QMessageBox(
                    QMessageBox.Icon.Question,
                    'GPU driver detected successfully',
                    f'Your GPU driver seems to be made by {manufacturer}, do you want\n'
                    'to continue DDU?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
                )
                msgbox.addButton('Choose different driver', QMessageBox.ButtonRole.ActionRole)

                # Oh hey look, new Python 3.10 features
                match msgbox.exec():
                    case QMessageBox.ButtonRole.RejectRole:
                        selected_driver = (manufacturer, False)
                    case QMessageBox.ButtonRole.ActionRole:
                        selected_driver = QInputDialog.getItem(
                            self,
                            'Select GPU driver to uninstall',
                            'Please select the GPU driver you want to uninstall',
                            valid_manufacturers
                        )
                    case _:
                        selected_driver = (manufacturer, True)

        if not selected_driver[1]:
            self.logger.info('User canceled Auto-DDU (at driver selection)')
            self.close()
            return

        self.ddu_steps.set_step_status(0, StepListItemStatus.SUCCESS)
        self.check_windows_version()

    def check_windows_version(self):
        self.ddu_steps.set_step_status(1, StepListItemStatus.IN_PROGRESS)
        # Distinguish between W10 / W11 / older windows versions
        win_maj_ver = sys.getwindowsversion()[0]
        if win_maj_ver in [10, 11]:
            build_version_list = fido_get_rel_list(str(win_maj_ver))
        else:
            self.ddu_steps.set_step_status(1, StepListItemStatus.FAILURE)
            QMessageBox(
                QMessageBox.Icon.Critical,
                'Windows version unsupported',
                'The Windows version you\'re currently using is unsupported.\n'
                'Please update to either Windows 10 or 11.'
            ).exec()
            return
        current_build = self.wmi_inst.Win32_OperatingSystem()[0].BuildNumber
        if current_build not in build_version_list.keys():
            QMessageBox(
                QMessageBox.Icon.Warning,
                'Windows build not found',
                'The windows version you\'re using is not in Fido\'s database.\n'
                'This most likely means that you\'re using an Insider build of Windows, and that\n'
                'Auto-DDU will probably fail/not do anything. You\'ve been warned.'
            ).exec()
        self.logger.debug(f'Version list returned by Fido: {build_version_list}')
