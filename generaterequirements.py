from pathlib import Path
import sys
import shutil
import subprocess
from tqdm import tqdm
from pathlib import Path
import subprocess
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
import time
from ellipses import ellipses # apologies to anyone wanting to generate this on their own
# just remove this and the usage ln 91

def generateRequirementsTxt():
    ellipses('generating requirements..')
    folders = [
        Path("Python/events/"),
        Path("Assets/Scripts/"),
        Path(".")
    ]
    folders = [path.resolve() for path in folders]

    ignorelist = [
        'V2CE-Toolbox-master',
        'v2e-master',
        'data',
        'output',
        '.vscode',
        '.git',
        '.vs',
        'Assets',
        'Library',
        'Logs',
        'obj',
        'Packages',
        'ProjectSettings',
        'Python',
        'Temp',
        'UserSettings',
        'googledrive_packaging'
    ]
    ignores = ','.join(ignorelist)

    excludes = [
        'ellipses'
        'pytorch'
    ]

    requirements = {}

    for folder in folders:
        cmd = [
            sys.executable, '-m',
            "pipreqs.pipreqs", str(folder),
            "--print", "--force",
            '--encoding', 'utf-8',
            '--ignore', ignores]

        print('running '+' '.join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            # check=True, # pipreqs returns code 1 sometimes even on success
        )

        print(f'result out: {result.stdout}')
        print(f'result err: {result.stderr}')

        for line in result.stdout.splitlines():
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            req = Requirement(line)
            key = canonicalize_name(req.name)

            if any([key in e for e in excludes]):
                continue

            previous = requirements.get(key)

            if previous is None:
                requirements[key] = req
                continue

            # Resolve duplicate exact pins by keeping the newer version.
            old_versions = [
                Version(s.version) for s in previous.specifier if s.operator == "=="
            ]
            new_versions = [
                Version(s.version) for s in req.specifier if s.operator == "=="
            ]

            if new_versions and (not old_versions or max(new_versions) > max(old_versions)):
                requirements[key] = req

    print('finishing')
    lines = sorted(
        (str(req) for req in requirements.values()),
        key=str.lower,
    )
    
    Path("requirements.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

if __name__ == '__main__':
    generateRequirementsTxt()