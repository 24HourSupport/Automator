import os.path
from logging import getLogger

import requests

from Automator.misc.paths import main_path
from Automator.misc.powershell import verify_ps, run_script

logger = getLogger('VersionInfo')


def fido_get_rel_list(winver: str) -> dict[int, str]:
    """
    :param winver: Windows version to get the release list from (either 10 or 11)
    :return: A dict with the build numbers as keys and version names as values
    """
    if not verify_ps():
        raise RuntimeError('Unable to run Fido without PowerShell')

    # Download Fido
    fido_raw = requests.get('https://raw.githubusercontent.com/pbatard/Fido/master/Fido.ps1').content
    with open(os.path.join(main_path, 'Fido.ps1'), 'wb') as f:
        f.write(fido_raw)

    # Get the version list from Fido
    fido_output = run_script(
        os.path.join(main_path, 'Fido.ps1') + f' -Win {winver} -Rel List', capture_output=True
    ).stdout.decode()
    version_list = fido_output.strip().split('\n')[1:]

    # Parse the list and construct a dict that has the build numbers as keys and version names as values
    final_dict = {}
    for version_str in version_list:
        version_name = version_str[3:].split(' ')[0]
        everything_after_build = version_str.split('(Build ')[1]
        build_num = everything_after_build.split('.')[0]
        final_dict[int(build_num)] = version_name
    return final_dict
