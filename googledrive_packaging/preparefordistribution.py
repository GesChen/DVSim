from pathlib import Path
import shutil
import subprocess
from tqdm import tqdm
import tarfile
from pathlib import Path
import subprocess
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
import gdown
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from pydrive2.files import ApiRequestError
import time
from ellipses import ellipses # apologies to anyone wanting to generate this on their own
# just remove this and the usage ln 91

def generateRequirementsTxt():
    print('generating requirements..')
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
    ]
    ignores = ','.join(ignorelist)

    requirements = {}

    for folder in folders:
        cmd = ["pipreqs", str(folder),
                     "--print", "--force",
                     '--encoding', 'utf-8',
                     '--ignore', ignores]

        print('running '+' '.join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        for line in result.stdout.splitlines():
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            req = Requirement(line)
            key = canonicalize_name(req.name)

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

    lines = sorted(
        (str(req) for req in requirements.values()),
        key=str.lower,
    )

    Path("requirements.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

def generateTarGz():
    root = Path(__file__).parent.resolve()
    rules_file = root / ".gitrestore"
    output = root / "DVSim"
    tar = Path("DVSim.tar.gz")

    if output.exists():
        print('output exists, deleting..')
        shutil.rmtree(str(output))

    if tar.exists():
        print('tar exists, deleting..')
        tar.unlink()

    print('parsing restore..')
    print('reading..')
    rules = []

    for raw in tqdm(rules_file.read_text().splitlines()):
        line = raw.strip()

        if not line or line.startswith("#") or line.startswith("!"):
            continue

        directory_only = line.endswith("/")
        pattern = line.lstrip("/").rstrip("/")
        rules.append((pattern, directory_only))

    print('matching..')
    matches = set()

    for pattern, directory_only in tqdm(rules):
        search = pattern if "/" in pattern else f"**/{pattern}"

        for path in root.glob(search):
            if directory_only and not path.is_dir():
                continue
            if path == output or output in path.parents:
                continue
            matches.add(path)

    selected_dirs = {path for path in matches if path.is_dir()}

    def is_ignored(path):
        result = subprocess.run(
            ["git", "check-ignore", "-q", '--no-index', "--", str(path.relative_to(root))],
            cwd=root
        )

        if result.returncode > 1:
            raise RuntimeError("git check-ignore failed")

        return result.returncode == 0

    def allowed(path):
        for parent in path.parents:
            if parent == root:
                break

            if is_ignored(parent) and parent not in selected_dirs:
                return False

        return True

    print('restoring..')

    matches = {path for path in matches if allowed(path)}
    copied_dirs = {path for path in matches if path.is_dir()}

    for source in tqdm(sorted(matches, key=lambda path: len(path.parts))):
        if any(parent in copied_dirs for parent in source.parents):
            continue

        destination = output / source.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if source.is_dir():
            shutil.copytree(source, destination, symlinks=True)
        else:
            shutil.copy2(source, destination, follow_symlinks=False)

    items = list(output.iterdir())
    with ellipses('compressing'):
        with tarfile.open(tar, "w:gz") as tar:
            for p in items:
                tar.add(p, arcname=p.name)

    shutil.rmtree(str(output))

def handleGdrive():
    print('handling google drive file..')
    gauth = GoogleAuth()

    print('auth')
    # Load saved credentials if present.
    gauth.LoadCredentialsFile("credentials.json")

    if gauth.credentials is None:
        # First run.
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        # Refresh using the refresh token.
        gauth.Refresh()
    else:
        # Already authenticated.
        gauth.Authorize()

    gauth.SaveCredentialsFile("credentials.json")

    drive = GoogleDrive(gauth)

    # delete old tar file
    print('attempting deletion of old gdrive file')
    
    idfile = Path('targz_gdriveid.txt')
    oldid = idfile.read_text()
    print(f'old id: {oldid}')

    if len(oldid) > 0: # try delete
        print('fetching..')
        old = drive.CreateFile({"id": oldid})
        try:
            print('deleting..')
            old.FetchMetadata(fields='title')
            if 'tar.gz' in old['title']:
                old.Delete()
        except:
            print(f'failed to delete old file id {oldid}, might just not exist')
    else:
        print('old id was empty, skipping deletion')

    # upload new file 
    ellipses('uploading new file')
    new = drive.CreateFile({'title':'DVSim_Untracked.tar.gz'})
    new.SetContentFile('DVSim.tar.gz')
    new.Upload()

    print('writing id and deleting local tgz')
    newid = new['id']
    idfile.write_text(newid)

    time.sleep(.1) # gdrive might still have handle on the source file
    # dont need tgz if it's uploaded now
    Path("DVSim.tar.gz").unlink()

if __name__ == '__main__':
    # generateRequirementsTxt()
    # generateTarGz()
    handleGdrive()