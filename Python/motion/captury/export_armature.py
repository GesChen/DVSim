from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


BLENDER_EXE = Path(
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
)

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_DIR = SCRIPT_DIR / "input"
OUTPUT_DIR = SCRIPT_DIR / "output"

COPY_OUTPUT_DIR = Path(r'E:\DVSim\Assets\Assets\captury')


def find_input_fbx(folder: Path) -> Path:
    fbx_files = sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() == ".fbx"
    )

    if not fbx_files:
        raise FileNotFoundError(f"No FBX found directly inside: {folder}")

    if len(fbx_files) > 1:
        raise RuntimeError(
            f"Expected one FBX inside {folder}, but found {len(fbx_files)}: "
            + ", ".join(path.name for path in fbx_files)
        )

    return fbx_files[0]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: py export_armature.py <input-folder-name>"
        )

    folder_name = sys.argv[1]
    input_folder = INPUT_DIR / folder_name

    if not BLENDER_EXE.is_file():
        raise FileNotFoundError(f"Blender executable not found: {BLENDER_EXE}")

    if not input_folder.is_dir():
        raise NotADirectoryError(f"Input folder not found: {input_folder}")

    bpy_script = SCRIPT_DIR / "export_armature_bpy.py"

    if not bpy_script.is_file():
        raise FileNotFoundError(f"Blender script not found: {bpy_script}")

    input_fbx = find_input_fbx(input_folder)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    COPY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_fbx = OUTPUT_DIR / f"{folder_name}.fbx"
    copied_fbx = COPY_OUTPUT_DIR / output_fbx.name

    command = [
        str(BLENDER_EXE),
        "--background",
        "--factory-startup",
        "--python",
        str(bpy_script),
        "--",
        str(input_fbx),
        str(output_fbx),
    ]

    print(f"Input:  {input_fbx}")
    print(f"Output: {output_fbx}")

    subprocess.run(command, check=True)

    if not output_fbx.is_file():
        raise RuntimeError(f"Expected output was not created: {output_fbx}")

    shutil.copy2(output_fbx, copied_fbx)

    print(f"Copied: {copied_fbx}")


if __name__ == "__main__":
    main()