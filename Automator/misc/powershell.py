import subprocess
from os import PathLike
from typing import Union


def verify_ps() -> bool:
    """
    Verifies that powershell works
    :return: bool (Powershell working Y/N)
    """
    # TODO
    return True


def run_script(script_path: Union[str, PathLike], *args, **kwargs):
    return subprocess.run(
        ['powershell', '-c', f'Set-ExecutionPolicy Unrestricted -Scope Process -Force; {script_path}'],
        *args, **kwargs
    )
