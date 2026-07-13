from pathlib import Path
import shutil
import subprocess

OUTPUT_DIR = Path(r"E:\DVSim\Assets\Assets\Replica")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

for ply in Path(r'E:\DVSim\Python\room generation\replica').rglob("mesh.ply"):
    print(ply)

    subprocess.run(
        ["py", "ply2fbx.py", str(ply)],
        check=True,
    )

    fbx = ply.with_suffix(".fbx")
    dst = OUTPUT_DIR / f"{ply.parent.name}.fbx"

    shutil.copy2(fbx, dst)
    print(f" -> {dst}")