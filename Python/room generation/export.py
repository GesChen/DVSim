from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def find_blender() -> Path:
    candidates = [
        os.environ.get("BLENDER_EXE"),
        r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    ]

    for candidate in candidates:
        if candidate:
            path = Path(candidate)
            if path.is_file():
                return path.resolve()

    raise FileNotFoundError(
        "Could not find Blender. Set the BLENDER_EXE environment variable "
        "to the full path of blender.exe."
    )


def main() -> int:
    if len(sys.argv) != 2:
        print(
            f'Usage: python "{Path(__file__).name}" <replica_folder>',
            file=sys.stderr,
        )
        return 1

    replica_folder = Path(sys.argv[1]).expanduser().resolve()

    if not replica_folder.is_dir():
        print(
            f"Replica folder does not exist: {replica_folder}",
            file=sys.stderr,
        )
        return 1

    script_folder = Path(__file__).resolve().parent
    export_bpy = script_folder / "export_bpy.py"

    if not export_bpy.is_file():
        print(
            f"Missing Blender export script: {export_bpy}",
            file=sys.stderr,
        )
        return 1

    try:
        blender = find_blender()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    command = [
        str(blender),
        '--factory-startup',
        '--python-use-system-env',
        "--background",
        "--python",
        str(export_bpy),
        "--",
        str(replica_folder),
    ]

    print("Running:")
    print(subprocess.list2cmdline(command), flush=True)

    try:
        completed = subprocess.run(command, check=False)
    except OSError as exc:
        print(f"Failed to start Blender: {exc}", file=sys.stderr)
        return 1

    if completed.returncode != 0:
        print(
            f"Blender export failed with exit code {completed.returncode}.",
            file=sys.stderr,
        )
        return completed.returncode

    output_fbx = replica_folder / f"{replica_folder.name}.fbx"
    print(f"Exported: {output_fbx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())