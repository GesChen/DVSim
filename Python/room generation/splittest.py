# test_split_mesh.py

from __future__ import annotations

from pathlib import Path
import argparse

from mesh_data import MeshData
from mesh_loader import load_ply_mesh
from mesh_splitter import split_mesh
from mesh_visualiser import visualize_mesh


def print_mesh_info(name: str, mesh: MeshData) -> None:
    vertex_count = 0 if mesh.vbo is None else len(mesh.vbo)
    index_count = 0 if mesh.ibo is None else len(mesh.ibo)
    face_count = (
        index_count // mesh.polygon_stride
        if mesh.polygon_stride > 0
        else 0
    )

    normal_count = 0 if mesh.nbo is None else len(mesh.nbo)
    color_count = 0 if mesh.cbo is None else len(mesh.cbo)

    print(f"{name}:")
    print(f"  vertices:       {vertex_count}")
    print(f"  indices:        {index_count}")
    print(f"  faces:          {face_count}")
    print(f"  normals:        {normal_count}")
    print(f"  colors:         {color_count}")
    print(f"  polygon stride: {mesh.polygon_stride}")


def validate_split(
    original: MeshData,
    parts: list[MeshData],
) -> None:
    if original.ibo is None:
        raise ValueError("Original mesh has no index buffer.")

    original_face_count = len(original.ibo) // 4
    split_face_count = sum(
        len(part.ibo) // part.polygon_stride
        for part in parts
        if part.ibo is not None
    )

    print()
    print("Validation:")
    print(f"  original faces: {original_face_count}")
    print(f"  split faces:    {split_face_count}")
    print(f"  part count:     {len(parts)}")

    if split_face_count != original_face_count:
        raise RuntimeError(
            "Split face count does not match original face count: "
            f"{split_face_count} != {original_face_count}"
        )

    for part_index, part in enumerate(parts):
        if part.vbo is None:
            raise RuntimeError(f"Part {part_index} has no VBO.")

        if part.ibo is None:
            raise RuntimeError(f"Part {part_index} has no IBO.")

        if part.nbo is None:
            raise RuntimeError(f"Part {part_index} has no NBO.")

        if part.polygon_stride != 4:
            raise RuntimeError(
                f"Part {part_index} has polygonStride "
                f"{part.polygon_stride}, expected 4."
            )

        if len(part.ibo) % 4 != 0:
            raise RuntimeError(
                f"Part {part_index} IBO length is not divisible by 4."
            )

        if len(part.ibo) > 0 and int(part.ibo.max()) >= len(part.vbo):
            raise RuntimeError(
                f"Part {part_index} contains an out-of-range vertex index."
            )

        if len(part.nbo) != len(part.vbo):
            raise RuntimeError(
                f"Part {part_index} normal count does not match "
                f"vertex count."
            )

    print("  result:         valid")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Load a PLY mesh, split it with the Replica PTex-style "
            "Morton splitter, and visualize each part with a random color."
        )
    )

    parser.add_argument(
        "ply_path",
        type=Path,
        help="Path to the input PLY file.",
    )

    parser.add_argument(
        "split_size",
        type=float,
        help="Spatial split cell size.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=1234,
        help="Random color seed. Default: 1234",
    )

    parser.add_argument(
        "--wireframe",
        action="store_true",
        help="Show triangle wireframes.",
    )

    parser.add_argument(
        "--vertices",
        action="store_true",
        help="Show vertices.",
    )

    parser.add_argument(
        "--normals",
        action="store_true",
        help="Show vertex normals.",
    )

    parser.add_argument(
        "--max-faces",
        type=int,
        default=None,
        help="Maximum rendered triangle count per split part.",
    )

    args = parser.parse_args()

    ply_path = args.ply_path.resolve()

    if not ply_path.is_file():
        raise FileNotFoundError(f"PLY file does not exist: {ply_path}")

    if args.split_size <= 0.0:
        raise ValueError("split_size must be greater than zero.")

    print(f"Loading: {ply_path}")
    mesh = load_ply_mesh(str(ply_path), True)

    print()
    print_mesh_info("Original mesh", mesh)

    if mesh.polygon_stride != 4:
        raise ValueError(
            "The translated SplitMesh implementation expects quadrilateral "
            f"faces, but this PLY has polygonStride={mesh.polygon_stride}."
        )

    print()
    print(f"Splitting with split_size={args.split_size}...")
    split_meshes = split_mesh(mesh, args.split_size, True)

    print(f"Created {len(split_meshes)} split mesh parts.")

    if not split_meshes:
        raise RuntimeError("The splitter returned no mesh parts.")

    validate_split(mesh, split_meshes)

    print()
    print("Split parts:")

    total_split_vertices = 0

    for index, part in enumerate(split_meshes):
        vertex_count = 0 if part.vbo is None else len(part.vbo)
        face_count = (
            0
            if part.ibo is None
            else len(part.ibo) // part.polygon_stride
        )

        total_split_vertices += vertex_count

        print(
            f"  part {index:4d}: "
            f"{vertex_count:8d} vertices, "
            f"{face_count:8d} faces"
        )

    original_vertex_count = 0 if mesh.vbo is None else len(mesh.vbo)

    print()
    print("Vertex duplication:")
    print(f"  original vertices:    {original_vertex_count}")
    print(f"  split-part vertices:  {total_split_vertices}")
    print(
        f"  duplicated references: "
        f"{total_split_vertices - original_vertex_count}"
    )

    print()
    print("Opening visualizer...")

    visualize_mesh(
        split_meshes,
        title=(
            f"Split mesh: {ply_path.name} "
            f"(split_size={args.split_size})"
        ),
        separate_mesh_colors=True,
        random_seed=args.seed,
        show_wireframe=args.wireframe,
        show_vertices=args.vertices,
        show_normals=args.normals,
        max_face_count=args.max_faces,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())