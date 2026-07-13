from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    blender = Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe")
    script = Path(__file__).with_name("ply_to_vertex_color_fbx.py")

    cmd = [
        str(blender),
        "--background",
        '--factory-startup',
        '--python-use-system-env',
        "--python",
        str(script),
        "--",
        *sys.argv[1:],
    ]

    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())