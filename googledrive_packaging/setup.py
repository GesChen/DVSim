import sys
import subprocess
from pathlib import Path
import shutil
import tarfile
import tempfile
from importlib.metadata import version, PackageNotFoundError
from packaging.requirements import Requirement
from ellipses import ellipses

try:
    import gdown
except:
    autoinstall = input('gdown is not installed. install now? (this will run `pip install gdown` for you) (y/n)')
    if autoinstall == 'y':
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            "gdown",
        ])
        import gdown
    else:
        print('aborting execution..')
        sys.exit(1)

def requirements_satisfied(requirements_file: str) -> bool:
    with open(requirements_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            req = Requirement(line)

            try:
                installed = version(req.name)
            except PackageNotFoundError:
                return False

            if not req.specifier.contains(installed, prereleases=True):
                return False

    return True

def safe_extract(tar: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()

    for member in tar.getmembers():
        member_path = (destination / member.name).resolve()

        if destination not in member_path.parents and member_path != destination:
            raise RuntimeError(f"Unsafe archive path: {member.name}")

        if member.issym() or member.islnk():
            raise RuntimeError(f"Archive contains unsupported link: {member.name}")

    tar.extractall(destination)


def restore_files(source_root: Path, target_root: Path) -> None:
    for source in sorted(source_root.rglob("*")):
        if source.is_dir():
            continue

        relative = source.relative_to(source_root)
        destination = target_root / relative

        if destination.exists():
            print(f"IGNORED  {relative}")
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        print(f"COPIED   {relative}")

def main():
    # check py ver
    print('checking py ver')
    ver = sys.version_info
    verstr = f'{ver.major}.{ver.minor}.{ver.micro}'
    if verstr != '3.13.0':
        print(f'py {verstr} detected. if something isn\'t working, try installing 3.13.0')

    # check unity exists
    print('checking unity')
    target_unity_version = '2022.3.62f2'
    typical_unity_install = Path('C:\Program Files\Unity')
    if not typical_unity_install.exists():
        print(f'DVSim requires Unity to be installed. please install version {target_unity_version}')
        return

    # check unity ver
    typical_editor_install = typical_unity_install / 'Hub' / 'Editor' / target_unity_version

    if not typical_editor_install.exists():
        print(f'unity version {target_unity_version} not present. DVSim was made for specifically this version, but it might work with others. if something breaks, install and switch to {target_unity_version}')

    # install requirements
    alreadysatisfied = requirements_satisfied('requirements.txt')
    if not alreadysatisfied:
        print('installing requirements..')
        subprocess.check_call([sys.executable, "-m", "pip", "install", '-r', 'requirements.txt'])

    FILE_ID = "YOUR_GOOGLE_DRIVE_FILE_ID"
    TARGET_DIR = Path.cwd()
    ARCHIVE = Path("DVSim.tar.gz")

    ellipses("Downloading...")
    gdown.download(
        id=FILE_ID,
        output=str(ARCHIVE),
        quiet=False,
    )

    try:
        with tempfile.TemporaryDirectory() as tmp:
            extract_dir = Path(tmp)

            with tarfile.open(ARCHIVE, "r:gz") as tar:
                safe_extract(tar, extract_dir)

            restore_files(extract_dir, TARGET_DIR)

    finally:
        ARCHIVE.unlink(missing_ok=True)
        print(f"DELETED  {ARCHIVE.name}")

if __name__ == '__main__':
    main()