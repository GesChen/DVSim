import sys
import subprocess
from pathlib import Path
import shutil
import tarfile
import tempfile
from importlib.metadata import PackageNotFoundError, distribution
from packaging.requirements import Requirement

# weak check, just if it exists, not specific versioning
def requirements_satisfied(requirements_file: str) -> bool:
    with open(requirements_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            try:
                distribution(Requirement(line).name)
            except PackageNotFoundError:
                return False

    return True


def main():
    # check py ver
    print('checking py ver')
    pyver = sys.version_info
    pyverstr = f'{pyver.major}.{pyver.minor}.{pyver.micro}'
    if pyverstr != '3.13.0':
        print(f'py {pyverstr} detected. if something isn\'t working, try installing 3.13.0')
    else: print(f'- using correct py ver {pyverstr}')

    # check unity exists
    print('checking unity')
    target_unity_version = '2022.3.62f2'
    typical_unity_install = Path(r'C:\Program Files\Unity')
    if not typical_unity_install.exists():
        print(f'DVSim requires Unity to be installed. please install version {target_unity_version}')
        return
    else: print('- unity is installed')

    # check unity ver
    typical_editor_install = typical_unity_install / 'Hub' / 'Editor' / target_unity_version

    if not typical_editor_install.exists():
        print(f'unity version {target_unity_version} not present. DVSim was made for specifically this version, but it might work with others. if something breaks, install and switch to {target_unity_version}')
    else: print(f'- using correct unity editor version {target_unity_version}')

    # install requirements
    print('checking pip')
    alreadysatisfied = requirements_satisfied('requirements.txt')
    if not alreadysatisfied:
        print('installing requirements..')
        subprocess.check_call([sys.executable, "-m", "pip", "install", '-r', 'requirements.txt'])
    else: print('- requirements already satisfied')

if __name__ == '__main__':
    main()