from __future__ import annotations

import argparse
import sys
from pathlib import Path
from tqdm import tqdm

import bpy


OUTPUT_COLOR_ATTRIBUTE = "Color"


def parse_arguments() -> argparse.Namespace:
    argv = sys.argv

    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(
        description="Convert a vertex-colored PLY file to FBX."
    )

    parser.add_argument(
        "input_ply",
        type=Path,
        help="Input PLY file.",
    )

    parser.add_argument(
        "output_fbx",
        type=Path,
        nargs="?",
        default=None,
        help="Optional output FBX file. Defaults beside the input PLY.",
    )

    args = parser.parse_args(argv)

    if args.output_fbx is None:
        args.output_fbx = args.input_ply.with_suffix(".fbx")

    return args


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def import_ply(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)

    if hasattr(bpy.ops.wm, "ply_import"):
        bpy.ops.wm.ply_import(filepath=str(path))
    else:
        bpy.ops.import_mesh.ply(filepath=str(path))

    imported = [
        obj
        for obj in bpy.data.objects
        if obj not in before and obj.type == "MESH"
    ]

    if not imported:
        raise RuntimeError(f"No mesh was imported from: {path}")

    return imported


def find_source_color_attribute(
    mesh: bpy.types.Mesh,
) -> bpy.types.Attribute:
    color_attributes = mesh.color_attributes

    if not color_attributes:
        raise RuntimeError(
            f'Mesh "{mesh.name}" contains no color attributes.'
        )

    active_render = color_attributes.active_color

    if active_render is not None:
        return active_render

    preferred_names = (
        "Color",
        "Col",
        "color",
        "colour",
        "vertex_color",
        "vertex_colors",
    )

    for name in preferred_names:
        attribute = color_attributes.get(name)

        if attribute is not None:
            return attribute

    return color_attributes[0]


def read_color(
    attribute: bpy.types.Attribute,
    *,
    vertex_index: int,
    loop_index: int,
    polygon_index: int,
) -> tuple[float, float, float, float]:
    if attribute.domain == "POINT":
        value = attribute.data[vertex_index]
    elif attribute.domain == "CORNER":
        value = attribute.data[loop_index]
    elif attribute.domain == "FACE":
        value = attribute.data[polygon_index]
    else:
        raise RuntimeError(
            f'Unsupported color domain "{attribute.domain}" '
            f'for attribute "{attribute.name}".'
        )

    color = value.color

    return (
        float(color[0]),
        float(color[1]),
        float(color[2]),
        float(color[3]),
    )


def create_fbx_color_attribute(
    mesh: bpy.types.Mesh,
    source: bpy.types.Attribute,
    *,
    show_progress: bool = False,
) -> bpy.types.Attribute:
    color_attributes = mesh.color_attributes

    destination_name = OUTPUT_COLOR_ATTRIBUTE

    if source.name == destination_name:
        destination_name = "__FBX_Color_Temporary"

    old_destination = color_attributes.get(destination_name)

    if old_destination is not None:
        if show_progress:
            print(f'Removing existing color attribute "{destination_name}"...')

        color_attributes.remove(old_destination)

    if show_progress:
        print(
            f'Creating FBX color attribute for mesh "{mesh.name}" '
            f"with {len(mesh.loops):,} corner colors..."
        )

    destination = color_attributes.new(
        name=destination_name,
        type="BYTE_COLOR",
        domain="CORNER",
    )

    polygons = mesh.polygons

    if show_progress:
        polygons = tqdm(
            polygons,
            total=len(mesh.polygons),
            desc="Copying vertex colors",
            unit="polygon",
        )

    for polygon in polygons:
        for loop_index in polygon.loop_indices:
            loop = mesh.loops[loop_index]

            destination.data[loop_index].color = read_color(
                source,
                vertex_index=loop.vertex_index,
                loop_index=loop_index,
                polygon_index=polygon.index,
            )

    existing_final = color_attributes.get(OUTPUT_COLOR_ATTRIBUTE)

    if existing_final is not None and existing_final != destination:
        if show_progress:
            print(
                f'Replacing existing final color attribute '
                f'"{OUTPUT_COLOR_ATTRIBUTE}"...'
            )

        color_attributes.remove(existing_final)

    destination.name = OUTPUT_COLOR_ATTRIBUTE

    color_attributes.active_color = destination
    color_attributes.active = destination

    mesh.update()

    if show_progress:
        print(
            f'Created "{OUTPUT_COLOR_ATTRIBUTE}" with '
            f"{len(destination.data):,} corner colors."
        )

    return destination

def prepare_mesh_object(obj: bpy.types.Object) -> None:
    mesh = obj.data
    source = find_source_color_attribute(mesh)

    print(
        f'Preparing "{obj.name}": '
        f'color="{source.name}", '
        f'domain={source.domain}, '
        f'type={source.data_type}'
    )

    destination = create_fbx_color_attribute(mesh, source, show_progress=True)

    print(
        f'Created export color attribute "{destination.name}" '
        f'with {len(destination.data)} corner colors.'
    )


def select_only(objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")

    for obj in objects:
        obj.select_set(True)

    bpy.context.view_layer.objects.active = objects[0]


def export_fbx(
    objects: list[bpy.types.Object],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    select_only(objects)

    bpy.ops.export_scene.fbx(
        filepath=str(output_path),
        use_selection=True,
        object_types={"MESH"},
        axis_forward="-Z",
        axis_up="Y",
        global_scale=1.0,
        apply_unit_scale=True,
        bake_space_transform=False,
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        use_triangles=False,
        use_tspace=False,
        colors_type="SRGB",
        prioritize_active_color=True,
        add_leaf_bones=False,
        bake_anim=False,
        path_mode="AUTO",
        embed_textures=False,
    )

    print(f"Exported FBX: {output_path}")


def main() -> None:
    args = parse_arguments()

    input_path = args.input_ply.expanduser().resolve()
    output_path = args.output_fbx.expanduser().resolve()

    if not input_path.is_file():
        raise FileNotFoundError(f"PLY file not found: {input_path}")

    if output_path.suffix.lower() != ".fbx":
        output_path = output_path.with_suffix(".fbx")

    clear_scene()

    objects = import_ply(input_path)

    for obj in objects:
        prepare_mesh_object(obj)

    export_fbx(objects, output_path)


if __name__ == "__main__":
    main()