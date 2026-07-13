from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from plyparser import MeshData, PLYParse, PLYParseError


def debug_array(name: str, array: np.ndarray | None, sample_count: int = 5) -> None:
    print(f"\n{name}")
    print("-" * len(name))

    if array is None:
        print("None")
        return

    print(f"shape:       {array.shape}")
    print(f"dtype:       {array.dtype}")
    print(f"size:        {array.size}")
    print(f"nbytes:      {array.nbytes:,}")
    print(f"contiguous:  {array.flags.c_contiguous}")

    if array.size == 0:
        print("empty")
        return

    flat = array.reshape(-1)

    if np.issubdtype(array.dtype, np.number):
        print(f"minimum:     {np.min(flat)}")
        print(f"maximum:     {np.max(flat)}")

    count = min(sample_count, len(array))
    print(f"first {count} entries:")
    print(array[:count])


def validate_mesh(mesh: MeshData) -> list[str]:
    errors: list[str] = []

    if mesh.vbo is None:
        errors.append("vbo is None")
        return errors

    if mesh.vbo.ndim != 2 or mesh.vbo.shape[1] != 4:
        errors.append(f"vbo must have shape (N, 4), got {mesh.vbo.shape}")

    if mesh.vbo.dtype != np.float32:
        errors.append(f"vbo must use float32, got {mesh.vbo.dtype}")

    vertex_count = len(mesh.vbo)

    if not np.all(np.isfinite(mesh.vbo)):
        errors.append("vbo contains NaN or infinite values")

    if mesh.nbo is not None:
        if mesh.nbo.shape != mesh.vbo.shape:
            errors.append(
                f"nbo shape {mesh.nbo.shape} does not match vbo shape {mesh.vbo.shape}"
            )

        if mesh.nbo.dtype != np.float32:
            errors.append(f"nbo must use float32, got {mesh.nbo.dtype}")

        if not np.all(np.isfinite(mesh.nbo)):
            errors.append("nbo contains NaN or infinite values")

    if mesh.cbo is not None:
        expected_shape = (vertex_count, 4)

        if mesh.cbo.shape != expected_shape:
            errors.append(
                f"cbo must have shape {expected_shape}, got {mesh.cbo.shape}"
            )

        if mesh.cbo.dtype != np.uint8:
            errors.append(f"cbo must use uint8, got {mesh.cbo.dtype}")

    if mesh.polygonStride not in (0, 3, 4):
        errors.append(
            f"polygonStride must be 0, 3, or 4, got {mesh.polygonStride}"
        )

    if mesh.ibo is not None:
        if mesh.ibo.ndim != 1:
            errors.append(f"ibo must be one-dimensional, got {mesh.ibo.shape}")

        if mesh.ibo.dtype != np.uint32:
            errors.append(f"ibo must use uint32, got {mesh.ibo.dtype}")

        if mesh.polygonStride == 0:
            errors.append("ibo exists but polygonStride is 0")

        elif len(mesh.ibo) % mesh.polygonStride != 0:
            errors.append(
                "ibo length is not divisible by polygonStride: "
                f"{len(mesh.ibo)} % {mesh.polygonStride}"
            )

        if len(mesh.ibo) > 0:
            maximum_index = int(np.max(mesh.ibo))

            if maximum_index >= vertex_count:
                errors.append(
                    f"ibo contains vertex index {maximum_index}, "
                    f"but only {vertex_count} vertices exist"
                )

    return errors


def print_mesh_debug(mesh: MeshData, filename: Path) -> None:
    print("=" * 80)
    print("PLY PARSER DEBUG OUTPUT")
    print("=" * 80)

    print(f"file:              {filename}")
    print(f"file size:         {filename.stat().st_size:,} bytes")
    print(f"polygon stride:    {mesh.polygonStride}")

    vertex_count = 0 if mesh.vbo is None else len(mesh.vbo)

    if mesh.ibo is not None and mesh.polygonStride > 0:
        face_count = len(mesh.ibo) // mesh.polygonStride
    else:
        face_count = 0

    print(f"vertex count:      {vertex_count:,}")
    print(f"face count:        {face_count:,}")
    print(f"has normals:       {mesh.nbo is not None}")
    print(f"has colors:        {mesh.cbo is not None}")
    print(f"has indices:       {mesh.ibo is not None}")

    if mesh.vbo is not None and len(mesh.vbo) > 0:
        positions = mesh.vbo[:, :3]

        minimum = np.min(positions, axis=0)
        maximum = np.max(positions, axis=0)
        center = (minimum + maximum) * 0.5
        extent = maximum - minimum

        print("\nBounds")
        print("------")
        print(f"minimum:           {minimum}")
        print(f"maximum:           {maximum}")
        print(f"center:            {center}")
        print(f"extent:            {extent}")
        print(f"largest extent:    {np.max(extent)}")

    debug_array("VBO", mesh.vbo)
    debug_array("NBO", mesh.nbo)
    debug_array("CBO", mesh.cbo)
    debug_array("IBO", mesh.ibo)

    if mesh.ibo is not None and mesh.polygonStride > 0:
        faces = mesh.ibo.reshape(-1, mesh.polygonStride)

        print("\nFaces")
        print("-----")
        print(f"shape: {faces.shape}")
        print(f"first {min(5, len(faces))} faces:")
        print(faces[:5])

    errors = validate_mesh(mesh)

    print("\nValidation")
    print("----------")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("Mesh validation passed.")

    print("=" * 80)


def equalize_axes(ax, positions: np.ndarray) -> None:
    minimum = np.min(positions, axis=0)
    maximum = np.max(positions, axis=0)

    center = (minimum + maximum) * 0.5
    radius = np.max(maximum - minimum) * 0.5

    if radius <= 0:
        radius = 1.0

    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)


def choose_face_indices(
    face_count: int,
    maximum_faces: int,
    seed: int,
) -> np.ndarray:
    if face_count <= maximum_faces:
        return np.arange(face_count)

    rng = np.random.default_rng(seed)

    return np.sort(
        rng.choice(
            face_count,
            size=maximum_faces,
            replace=False,
        )
    )


def visualize_mesh(
    mesh: MeshData,
    filename: Path,
    maximum_faces: int,
    maximum_points: int,
    seed: int,
    wireframe: bool,
    show_vertices: bool,
    show_normals: bool,
    normal_scale: float,
) -> None:
    if mesh.vbo is None or len(mesh.vbo) == 0:
        raise ValueError("Mesh has no vertices to visualize")

    positions = mesh.vbo[:, :3].astype(np.float64, copy=False)

    figure = plt.figure(figsize=(12, 9))
    ax = figure.add_subplot(111, projection="3d")

    rendered_faces = 0

    if (
        mesh.ibo is not None
        and mesh.polygonStride > 0
        and len(mesh.ibo) > 0
    ):
        faces = mesh.ibo.reshape(-1, mesh.polygonStride)

        selected_face_indices = choose_face_indices(
            len(faces),
            maximum_faces,
            seed,
        )

        selected_faces = faces[selected_face_indices]
        polygons = positions[selected_faces]

        rendered_faces = len(selected_faces)

        if mesh.cbo is not None:
            vertex_colors = mesh.cbo.astype(np.float32) / 255.0
            face_colors = np.mean(vertex_colors[selected_faces], axis=1)
        else:
            face_colors = None

        collection = Poly3DCollection(
            polygons,
            facecolors=face_colors,
            edgecolors="black" if wireframe else "none",
            linewidths=0.15 if wireframe else 0.0,
            alpha=1.0,
        )

        ax.add_collection3d(collection)

    if show_vertices or rendered_faces == 0:
        point_count = len(positions)

        if point_count > maximum_points:
            rng = np.random.default_rng(seed)
            point_indices = np.sort(
                rng.choice(
                    point_count,
                    size=maximum_points,
                    replace=False,
                )
            )
        else:
            point_indices = np.arange(point_count)

        point_positions = positions[point_indices]

        if mesh.cbo is not None:
            point_colors = mesh.cbo[point_indices].astype(np.float32) / 255.0
        else:
            point_colors = None

        ax.scatter(
            point_positions[:, 0],
            point_positions[:, 1],
            point_positions[:, 2],
            c=point_colors,
            s=1.0,
            depthshade=False,
        )

    if show_normals and mesh.nbo is not None:
        normal_count = min(len(positions), maximum_points)

        if len(positions) > normal_count:
            rng = np.random.default_rng(seed)
            normal_indices = np.sort(
                rng.choice(
                    len(positions),
                    size=normal_count,
                    replace=False,
                )
            )
        else:
            normal_indices = np.arange(len(positions))

        normal_positions = positions[normal_indices]
        normals = mesh.nbo[normal_indices, :3].astype(np.float64, copy=False)

        lengths = np.linalg.norm(normals, axis=1)
        valid = lengths > 1e-12

        normal_positions = normal_positions[valid]
        normals = normals[valid]
        lengths = lengths[valid]

        if len(normals) > 0:
            normals = normals / lengths[:, None]

            ax.quiver(
                normal_positions[:, 0],
                normal_positions[:, 1],
                normal_positions[:, 2],
                normals[:, 0],
                normals[:, 1],
                normals[:, 2],
                length=normal_scale,
                normalize=False,
            )

    equalize_axes(ax, positions)

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    ax.set_title(
        f"{filename.name}\n"
        f"{len(positions):,} vertices, "
        f"{rendered_faces:,} rendered faces"
    )

    print("\nVisualizer")
    print("----------")
    print(f"rendered faces:    {rendered_faces:,}")
    print(f"maximum faces:     {maximum_faces:,}")
    print(f"maximum points:    {maximum_points:,}")
    print(f"wireframe:         {wireframe}")
    print(f"show vertices:     {show_vertices}")
    print(f"show normals:      {show_normals}")

    plt.tight_layout()
    plt.show()


def test_copy_behavior(mesh: MeshData) -> None:
    print("\nCopy test")
    print("---------")

    copied = mesh.copy()

    checks = [
        ("vbo", mesh.vbo, copied.vbo),
        ("ibo", mesh.ibo, copied.ibo),
        ("nbo", mesh.nbo, copied.nbo),
        ("cbo", mesh.cbo, copied.cbo),
    ]

    passed = True

    for name, source, destination in checks:
        if source is None:
            valid = destination is None
        else:
            valid = (
                destination is not None
                and np.array_equal(source, destination)
                and not np.shares_memory(source, destination)
            )

        print(f"{name}: {'passed' if valid else 'failed'}")
        passed &= valid

    stride_valid = copied.polygonStride == mesh.polygonStride
    print(f"polygonStride: {'passed' if stride_valid else 'failed'}")
    passed &= stride_valid

    if not passed:
        raise AssertionError("MeshData copy test failed")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test and visualize the restricted binary PLY parser."
    )

    parser.add_argument(
        "ply_file",
        type=Path,
        help="Path to a binary_little_endian PLY file.",
    )

    parser.add_argument(
        "--max-faces",
        type=int,
        default=200_000,
        help="Maximum number of faces to render.",
    )

    parser.add_argument(
        "--max-points",
        type=int,
        default=100_000,
        help="Maximum number of points or normals to render.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed used for visualization subsampling.",
    )

    parser.add_argument(
        "--wireframe",
        action="store_true",
        help="Draw polygon edges.",
    )

    parser.add_argument(
        "--vertices",
        action="store_true",
        help="Draw vertices over the mesh.",
    )

    parser.add_argument(
        "--normals",
        action="store_true",
        help="Draw vertex normals.",
    )

    parser.add_argument(
        "--normal-scale",
        type=float,
        default=0.05,
        help="Displayed normal-vector length.",
    )

    parser.add_argument(
        "--no-visualizer",
        action="store_true",
        help="Run parser tests without opening the visualizer.",
    )

    parser.add_argument(
        "--skip-copy-test",
        action="store_true",
        help="Skip testing MeshData.copy().",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    filename: Path = args.ply_file

    if not filename.is_file():
        print(f"ERROR: File does not exist: {filename}", file=sys.stderr)
        return 1

    if args.max_faces <= 0:
        print("ERROR: --max-faces must be greater than zero", file=sys.stderr)
        return 1

    if args.max_points <= 0:
        print("ERROR: --max-points must be greater than zero", file=sys.stderr)
        return 1

    print(f"Parsing: {filename}")

    mesh = MeshData()

    start_time = time.perf_counter()

    try:
        PLYParse(mesh, filename)
    except PLYParseError as exc:
        print(f"\nPLY parser error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(
            f"\nUnexpected error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise

    elapsed = time.perf_counter() - start_time

    print(f"Parsing completed in {elapsed:.6f} seconds")

    print_mesh_debug(mesh, filename)

    validation_errors = validate_mesh(mesh)

    if validation_errors:
        print(
            f"\nMesh failed validation with "
            f"{len(validation_errors)} error(s).",
            file=sys.stderr,
        )
        return 3

    if not args.skip_copy_test:
        test_copy_behavior(mesh)

    if not args.no_visualizer:
        visualize_mesh(
            mesh=mesh,
            filename=filename,
            maximum_faces=args.max_faces,
            maximum_points=args.max_points,
            seed=args.seed,
            wireframe=args.wireframe,
            show_vertices=args.vertices,
            show_normals=args.normals,
            normal_scale=args.normal_scale,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())