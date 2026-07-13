from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Sequence
import numpy as np

try:
    import bpy
except ImportError as exc:
    raise RuntimeError(
        "This module must run inside Blender's Python interpreter"
    ) from exc

try:
    from mesh_data import MeshData
except ImportError:
    MeshData = object  # Allows use with any object exposing vbo/ibo/polygon_stride.


def _atlas_png_path(png_folder: Path, split_index: int) -> Path:
    candidates = (
        png_folder / f"{split_index}-color-ptex.png",
        png_folder / f"{split_index}-color-ptex.hdr.png",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Missing atlas for split {split_index}; expected {candidates[0].name}"
    )


def _validate_submesh(mesh: object, split_index: int) -> tuple[np.ndarray, np.ndarray]:
    vbo = np.asarray(mesh.vbo, dtype=np.float32)
    ibo = np.asarray(mesh.ibo, dtype=np.uint32).reshape(-1)
    stride = int(mesh.polygon_stride)

    if vbo.ndim != 2 or vbo.shape[1] < 3:
        raise ValueError(f"Submesh {split_index}: vbo must have shape (N, >=3)")
    if stride != 4:
        raise ValueError(f"Submesh {split_index}: only quad meshes are supported")
    if ibo.size % 4:
        raise ValueError(f"Submesh {split_index}: ibo length is not divisible by four")
    if ibo.size and int(ibo.max()) >= vbo.shape[0]:
        raise IndexError(f"Submesh {split_index}: ibo references a missing vertex")
    return vbo[:, :3], ibo.reshape(-1, 4)


def _build_atlas_uvs(
    face_count: int,
    *,
    atlas_width: int,
    atlas_height: int,
    tile_size: int,
    inset_texels: float,
) -> np.ndarray:
    """Build flattened quad UV coordinates for Blender foreach_set()."""
    width_in_tiles = atlas_width // tile_size

    face_indices = np.arange(face_count, dtype=np.int64)
    tile_x = face_indices % width_in_tiles
    tile_y = face_indices // width_in_tiles

    x0 = (tile_x * tile_size + inset_texels) / atlas_width
    x1 = ((tile_x + 1) * tile_size - inset_texels) / atlas_width
    y0 = (tile_y * tile_size + inset_texels) / atlas_height
    y1 = ((tile_y + 1) * tile_size - inset_texels) / atlas_height

    # Four loops per quad, ordered to match the IBO winding:
    # edge 0 = bottom, edge 1 = right, edge 2 = top, edge 3 = left.
    uvs = np.empty(face_count * 8, dtype=np.float32)
    uvs[0::8] = x0
    uvs[1::8] = y0
    uvs[2::8] = x1
    uvs[3::8] = y0
    uvs[4::8] = x1
    uvs[5::8] = y1
    uvs[6::8] = x0
    uvs[7::8] = y1
    return uvs


def _make_material(name: str, image_path: Path) -> bpy.types.Material:
    image = bpy.data.images.load(str(image_path.resolve()), check_existing=True)
    image.colorspace_settings.name = "sRGB"
    image.pack()

    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = "Linear"
    texture.extension = "CLIP"

    links.new(texture.outputs["Color"], principled.inputs["Base Color"])
    links.new(texture.outputs["Alpha"], principled.inputs["Alpha"])
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    principled.inputs["Roughness"].default_value = 1.0
    return material

def create_textured_objects(
    split_meshes: Sequence[object],
    png_folder: str | Path,
    tile_size: int,
    *,
    collection_name: str = "PTexMesh",
    inset_texels: float = 0.5,
    clear_scene: bool = True,
    debug: bool = False,
) -> list[bpy.types.Object]:
    """Create one textured Blender mesh object for every split mesh."""

    def log(message: str) -> None:
        if debug:
            print(message)

    if tile_size <= 0:
        raise ValueError("tile_size must be greater than zero")
    if inset_texels < 0 or inset_texels * 2 >= tile_size:
        raise ValueError("inset_texels must be >= 0 and less than half tile_size")

    png_folder = Path(png_folder)
    split_count = len(split_meshes)

    if clear_scene:
        log("Clearing existing scene objects...")
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)

    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

    objects: list[bpy.types.Object] = []

    for split_index, source_mesh in enumerate(split_meshes):
        log(f"[{split_index + 1}/{split_count}] Processing split mesh...")

        positions, faces = _validate_submesh(source_mesh, split_index)
        image_path = _atlas_png_path(png_folder, split_index)

        image = bpy.data.images.load(
            str(image_path.resolve()),
            check_existing=True,
        )

        atlas_width, atlas_height = map(int, image.size)
        if atlas_width <= 0 or atlas_height <= 0:
            raise ValueError(f"Could not read image dimensions: {image_path}")

        if atlas_width % tile_size or atlas_height % tile_size:
            raise ValueError(
                f"{image_path.name}: dimensions {atlas_width}x{atlas_height} "
                f"are not divisible by tile_size={tile_size}"
            )

        tile_capacity = (
            atlas_width // tile_size
        ) * (
            atlas_height // tile_size
        )

        if len(faces) > tile_capacity:
            raise ValueError(
                f"Submesh {split_index} has {len(faces)} faces but its atlas "
                f"contains only {tile_capacity} tiles"
            )

        log(
            f"[{split_index + 1}/{split_count}] "
            f"Creating mesh with {len(positions)} vertices and "
            f"{len(faces)} faces..."
        )

        mesh_data = bpy.data.meshes.new(f"PTexMesh_{split_index:04d}")
        mesh_data.from_pydata(
            positions.tolist(),
            [],
            faces.tolist(),
        )
        mesh_data.update(calc_edges=True)

        obj = bpy.data.objects.new(mesh_data.name, mesh_data)
        collection.objects.link(obj)

        material = _make_material(
            f"PTexMaterial_{split_index:04d}",
            image_path,
        )
        mesh_data.materials.append(material)

        log(
            f"[{split_index + 1}/{split_count}] "
            f"Generating UV coordinates..."
        )

        uv_layer = mesh_data.uv_layers.new(name="UVMap")

        face_count = len(mesh_data.polygons)
        expected_loop_count = face_count * 4
        actual_loop_count = len(mesh_data.loops)
        if actual_loop_count != expected_loop_count:
            raise ValueError(
                f"Submesh {split_index}: expected {expected_loop_count} loops "
                f"for {face_count} quads, found {actual_loop_count}"
            )

        uv_values = _build_atlas_uvs(
            face_count,
            atlas_width=atlas_width,
            atlas_height=atlas_height,
            tile_size=tile_size,
            inset_texels=inset_texels,
        )
        uv_layer.data.foreach_set("uv", uv_values)

        # Newly created polygons already default to material index 0 and flat shading,
        # so avoid one Blender RNA write per property per polygon.

        objects.append(obj)

        log(
            f"[{split_index + 1}/{split_count}] Completed {obj.name}: "
            f"{len(positions)} vertices, {len(faces)} faces, "
            f"{image_path.name}"
        )

    return objects

def export_embedded_fbx(
    split_meshes: Sequence[object],
    png_folder: str | Path,
    tile_size: int,
    output_fbx: str | Path,
    *,
    inset_texels: float = 0.5,
    clear_scene: bool = True,
    debug: bool = False,
) -> Path:
    """Create the scene and export a binary FBX with embedded PNG media."""

    def log(msg: str):
        if debug:
            print(msg)

    output_fbx = Path(output_fbx).resolve()
    output_fbx.parent.mkdir(parents=True, exist_ok=True)

    log("Creating textured Blender objects...")

    objects = create_textured_objects(
        split_meshes,
        png_folder,
        tile_size,
        inset_texels=inset_texels,
        clear_scene=clear_scene,
        debug=debug
    )

    log(f"Created {len(objects)} mesh objects.")

    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active = objects[0]

    log("Exporting FBX (this may take a while)...")

    result = bpy.ops.export_scene.fbx(
        filepath=str(output_fbx),
        use_selection=True,
        object_types={"MESH"},
        use_mesh_modifiers=True,
        mesh_smooth_type="OFF",
        add_leaf_bones=False,
        bake_anim=False,
        path_mode="COPY",
        embed_textures=True,
        axis_forward="-Z",
        axis_up="Y",
    )

    if "FINISHED" not in result:
        raise RuntimeError(f"FBX export failed: {result}")

    log(f"Export complete: {output_fbx}")

    return output_fbx

def load_split_meshes_npz(path: str | Path) -> list[object]:
    """Load split meshes from an NPZ containing vbo_0/ibo_0, vbo_1/ibo_1, ..."""
    path = Path(path)
    data = np.load(path, allow_pickle=False)
    indices = sorted(
        int(key[4:]) for key in data.files if key.startswith("vbo_")
    )
    if not indices or indices != list(range(len(indices))):
        raise ValueError("NPZ must contain contiguous vbo_0, vbo_1, ... arrays")

    class LoadedMesh:
        pass

    meshes: list[object] = []
    for index in indices:
        ibo_key = f"ibo_{index}"
        if ibo_key not in data:
            raise ValueError(f"Missing {ibo_key}")
        mesh = LoadedMesh()
        mesh.vbo = data[f"vbo_{index}"]
        mesh.ibo = data[ibo_key]
        mesh.polygon_stride = 4
        meshes.append(mesh)
    return meshes


def _blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create an embedded-texture FBX from split quad meshes and PTex PNG atlases."
    )
    parser.add_argument("split_npz", type=Path)
    parser.add_argument("png_folder", type=Path)
    parser.add_argument("output_fbx", type=Path)
    parser.add_argument("--tile-size", type=int, required=True)
    parser.add_argument("--inset-texels", type=float, default=0.5)
    parser.add_argument("--keep-scene", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args(_blender_args())
    split_meshes = load_split_meshes_npz(args.split_npz)
    export_embedded_fbx(
        split_meshes,
        args.png_folder,
        args.tile_size,
        args.output_fbx,
        inset_texels=args.inset_texels,
        clear_scene=not args.keep_scene,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())