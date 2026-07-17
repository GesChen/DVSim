from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
import shutil

BLENDER_EXE = Path(
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
)

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_DIR = SCRIPT_DIR / "input"
OUTPUT_DIR = SCRIPT_DIR / "output"
BPY_SCRIPT = SCRIPT_DIR / "export_bpy.py"
UNITY_OUT = Path(r'E:\DVSim\Assets\Assets\freemocap')


def resolve_blend_path(value: str) -> Path:
    path = Path(value).expanduser()

    if path.is_absolute():
        return path.resolve()

    current_directory_path = (Path.cwd() / path).resolve()

    if current_directory_path.is_file():
        return current_directory_path

    return (INPUT_DIR / path).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the first armature in a Blender file as FBX."
    )
    parser.add_argument(
        "blend_file",
        help="Path to the input .blend file.",
    )
    args = parser.parse_args()

    blend_path = resolve_blend_path(args.blend_file)
    export_path = OUTPUT_DIR / f"{blend_path.stem}.fbx"

    if not BLENDER_EXE.is_file():
        raise FileNotFoundError(
            f"Blender executable not found: {BLENDER_EXE}"
        )

    if not BPY_SCRIPT.is_file():
        raise FileNotFoundError(
            f"Blender export script not found: {BPY_SCRIPT}"
        )

    if not blend_path.is_file():
        raise FileNotFoundError(
            f"Blend file not found: {blend_path}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            str(BLENDER_EXE),
            "--background",
            '--factory-startup',
            str(blend_path),
            "--python",
            str(BPY_SCRIPT),
            "--",
            str(export_path),
        ],
        check=True,
        cwd=SCRIPT_DIR,
    )

    shutil.copy2(
        str(export_path),
        UNITY_OUT / f"{blend_path.stem}.fbx"
    )


if __name__ == "__main__":
    main()