from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path


def blender_arguments() -> list[str]:
    if "--" not in sys.argv:
        return []

    return sys.argv[sys.argv.index("--") + 1:]


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required file: {path}")

    return path


def require_directory(path: Path) -> Path:
    if not path.is_dir():
        raise FileNotFoundError(f"Missing required directory: {path}")

    return path


def main() -> int:
    arguments = blender_arguments()

    if len(arguments) != 1:
        raise ValueError(
            "Expected exactly one argument: the Replica scene folder."
        )

    replica_folder = Path(arguments[0]).expanduser().resolve()
    require_directory(replica_folder)

    script_folder = Path(__file__).resolve().parent

    # Supporting modules are guaranteed to be beside this script.
    if str(script_folder) not in sys.path:
        sys.path.insert(0, str(script_folder))

    from mesh_loader import load_ply_mesh
    from mesh_splitter import split_mesh
    from ptex_split_to_fbx import export_embedded_fbx

    mesh_path = require_file(replica_folder / "mesh.ply")
    texture_folder = require_directory(replica_folder / "textures")
    png_folder = require_directory(replica_folder / "textures_png")
    parameters_path = require_file(texture_folder / "parameters.json")
    output_fbx = replica_folder / f"{replica_folder.name}.fbx"

    with parameters_path.open("r", encoding="utf-8") as file:
        parameters = json.load(file)

    try:
        split_size = float(parameters["splitSize"])
        tile_size = int(parameters["tileSize"])
    except KeyError as exc:
        raise KeyError(
            f"{parameters_path} is missing {exc.args[0]!r}."
        ) from exc

    if split_size <= 0:
        raise ValueError("splitSize must be greater than zero.")

    if tile_size <= 0:
        raise ValueError("tileSize must be greater than zero.")

    print(f"Replica:      {replica_folder}", flush=True)
    print(f"Mesh:         {mesh_path}", flush=True)
    print(f"Textures:     {texture_folder}", flush=True)
    print(f"PNG textures: {png_folder}", flush=True)
    print(f"Output:       {output_fbx}", flush=True)
    print(f"splitSize:    {split_size}", flush=True)
    print(f"tileSize:     {tile_size}", flush=True)

    mesh = load_ply_mesh(mesh_path, True)

    if int(mesh.polygon_stride) != 4:
        raise ValueError(
            "Replica PTex export requires a quad mesh. "
            f"Received polygon_stride={mesh.polygon_stride}."
        )

    split_meshes = split_mesh(
        mesh,
        split_size=split_size,
        debug=True,
    )

    if not split_meshes:
        raise RuntimeError("Mesh splitting produced no submeshes.")

    export_embedded_fbx(
        split_meshes=split_meshes,
        png_folder=png_folder,
        tile_size=tile_size,
        output_fbx=output_fbx,
        inset_texels=0.5,
        clear_scene=True,
        debug=True
    )

    print(f"Finished: {output_fbx}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)