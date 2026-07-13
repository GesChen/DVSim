
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from plyfile import PlyData

from mesh_data import MeshData

def has_properties(element, names: tuple[str, ...]) -> bool:
    dtype_names = element.data.dtype.names

    if dtype_names is None:
        return False

    return all(name in dtype_names for name in names)


def parse_ply(
    filename: str | Path,
    *,
    mmap_enabled: bool = True,
    debug: bool = False,
) -> MeshData:
    filename = Path(filename)

    if not filename.is_file():
        raise FileNotFoundError(filename)

    if debug:
        print("=" * 80)
        print("PLY PARSER")
        print("=" * 80)
        print(f"file:             {filename}")
        print(f"file size:        {filename.stat().st_size:,} bytes")
        print(f"memory mapping:   {mmap_enabled}")
        print()

    start = time.perf_counter()

    ply = PlyData.read(
        str(filename),
        mmap=mmap_enabled,
    )

    elapsed = time.perf_counter() - start

    if debug:
        print(f"read time:        {elapsed:.6f} seconds")
        print(f"format:           {ply.text and 'ascii' or 'binary'}")
        print(f"byte order:       {ply.byte_order!r}")
        print(f"comments:         {len(ply.comments)}")
        print(f"obj_info:         {len(ply.obj_info)}")
        print()

        print("Elements")
        print("--------")

        for element in ply.elements:
            print(
                f"{element.name}: "
                f"{element.count:,} entries, "
                f"properties={[p.name for p in element.properties]}"
            )

        print()

    if "vertex" not in ply:
        raise ValueError("PLY file has no vertex element")

    vertices = ply["vertex"]
    vertex_count = vertices.count

    if not has_properties(vertices, ("x", "y", "z")):
        raise ValueError("Vertex element must contain x, y, and z")

    mesh = MeshData()

    mesh.vbo = np.ones(
        (vertex_count, 4),
        dtype=np.float32,
    )

    mesh.vbo[:, 0] = np.asarray(vertices["x"], dtype=np.float32)
    mesh.vbo[:, 1] = np.asarray(vertices["y"], dtype=np.float32)
    mesh.vbo[:, 2] = np.asarray(vertices["z"], dtype=np.float32)

    if has_properties(vertices, ("w",)):
        mesh.vbo[:, 3] = np.asarray(vertices["w"], dtype=np.float32)

    if has_properties(vertices, ("nx", "ny", "nz")):
        mesh.nbo = np.ones(
            (vertex_count, 4),
            dtype=np.float32,
        )

        mesh.nbo[:, 0] = np.asarray(vertices["nx"], dtype=np.float32)
        mesh.nbo[:, 1] = np.asarray(vertices["ny"], dtype=np.float32)
        mesh.nbo[:, 2] = np.asarray(vertices["nz"], dtype=np.float32)

    if has_properties(vertices, ("red", "green", "blue")):
        mesh.cbo = np.full(
            (vertex_count, 4),
            255,
            dtype=np.uint8,
        )

        mesh.cbo[:, 0] = np.asarray(vertices["red"], dtype=np.uint8)
        mesh.cbo[:, 1] = np.asarray(vertices["green"], dtype=np.uint8)
        mesh.cbo[:, 2] = np.asarray(vertices["blue"], dtype=np.uint8)

        if has_properties(vertices, ("alpha",)):
            mesh.cbo[:, 3] = np.asarray(
                vertices["alpha"],
                dtype=np.uint8,
            )

    if "face" in ply and ply["face"].count > 0:
        face_element = ply["face"]
        property_names = face_element.data.dtype.names or ()

        face_property = None

        for candidate in (
            "vertex_indices",
            "vertex_index",
        ):
            if candidate in property_names:
                face_property = candidate
                break

        if face_property is None:
            raise ValueError(
                "Face element has no vertex_indices property"
            )

        raw_faces = face_element[face_property]

        if len(raw_faces) == 0:
            mesh.ibo = np.empty(0, dtype=np.uint32)
            mesh.polygon_stride = 0
        else:
            first_stride = len(raw_faces[0])

            if first_stride not in (3, 4):
                raise ValueError(
                    "Only triangle and quad faces are supported; "
                    f"first face has {first_stride} vertices"
                )

            valid_faces = []

            for face_index, face in enumerate(raw_faces):
                face = np.asarray(face, dtype=np.uint32)

                if len(face) != first_stride:
                    raise ValueError(
                        f"Face {face_index} has {len(face)} vertices, "
                        f"expected {first_stride}"
                    )

                valid_faces.append(face)

            faces = np.stack(valid_faces, axis=0)

            mesh.ibo = faces.reshape(-1)
            mesh.polygon_stride = first_stride
    else:
        mesh.ibo = None
        mesh.polygon_stride = 0

    if debug:
        print("Converted MeshData")
        print("------------------")
        print(f"vertices:         {vertex_count:,}")
        print(
            f"faces:            "
            f"{0 if mesh.ibo is None or mesh.polygon_stride == 0 else len(mesh.ibo) // mesh.polygon_stride:,}"
        )
        print(f"polygon stride:   {mesh.polygon_stride}")
        print(f"has normals:      {mesh.nbo is not None}")
        print(f"has colors:       {mesh.cbo is not None}")
        print()

    return mesh


def print_array_debug(
    name: str,
    array: np.ndarray | None,
    sample_count: int = 5,
) -> None:
    print(name)
    print("-" * len(name))

    if array is None:
        print("None")
        print()
        return

    print(f"shape:            {array.shape}")
    print(f"dtype:            {array.dtype}")
    print(f"size:             {array.size:,}")
    print(f"memory:           {array.nbytes:,} bytes")
    print(f"C contiguous:     {array.flags.c_contiguous}")
    print(f"owns memory:      {array.flags.owndata}")

    if array.size > 0 and np.issubdtype(array.dtype, np.number):
        print(f"minimum:          {np.min(array)}")
        print(f"maximum:          {np.max(array)}")
        print(f"finite:           {np.all(np.isfinite(array))}")

    print(f"first entries:")
    print(array[:sample_count])
    print()


def validate_mesh(mesh: MeshData) -> list[str]:
    errors: list[str] = []

    if mesh.vbo is None:
        errors.append("vbo is None")
        return errors

    if mesh.vbo.ndim != 2 or mesh.vbo.shape[1] != 4:
        errors.append(
            f"vbo must have shape (N, 4), got {mesh.vbo.shape}"
        )

    if mesh.vbo.dtype != np.float32:
        errors.append(
            f"vbo must use float32, got {mesh.vbo.dtype}"
        )

    vertex_count = len(mesh.vbo)

    if not np.all(np.isfinite(mesh.vbo)):
        errors.append("vbo contains NaN or infinity")

    if mesh.nbo is not None:
        if mesh.nbo.shape != (vertex_count, 4):
            errors.append(
                f"nbo must have shape {(vertex_count, 4)}, "
                f"got {mesh.nbo.shape}"
            )

        if mesh.nbo.dtype != np.float32:
            errors.append(
                f"nbo must use float32, got {mesh.nbo.dtype}"
            )

        if not np.all(np.isfinite(mesh.nbo)):
            errors.append("nbo contains NaN or infinity")

    if mesh.cbo is not None:
        if mesh.cbo.shape != (vertex_count, 4):
            errors.append(
                f"cbo must have shape {(vertex_count, 4)}, "
                f"got {mesh.cbo.shape}"
            )

        if mesh.cbo.dtype != np.uint8:
            errors.append(
                f"cbo must use uint8, got {mesh.cbo.dtype}"
            )

    if mesh.polygon_stride not in (0, 3, 4):
        errors.append(
            f"polygonStride must be 0, 3, or 4, "
            f"got {mesh.polygon_stride}"
        )

    if mesh.ibo is not None:
        if mesh.ibo.ndim != 1:
            errors.append(
                f"ibo must be flat, got shape {mesh.ibo.shape}"
            )

        if mesh.ibo.dtype != np.uint32:
            errors.append(
                f"ibo must use uint32, got {mesh.ibo.dtype}"
            )

        if mesh.polygon_stride == 0 and len(mesh.ibo) > 0:
            errors.append(
                "ibo contains indices but polygonStride is 0"
            )

        if (
            mesh.polygon_stride > 0
            and len(mesh.ibo) % mesh.polygon_stride != 0
        ):
            errors.append(
                "ibo length is not divisible by polygonStride"
            )

        if len(mesh.ibo) > 0:
            maximum_index = int(np.max(mesh.ibo))

            if maximum_index >= vertex_count:
                errors.append(
                    f"maximum face index is {maximum_index}, "
                    f"but vertex count is {vertex_count}"
                )

    return errors


def print_mesh_debug(mesh: MeshData) -> None:
    print("=" * 80)
    print("MESHDATA DEBUG")
    print("=" * 80)

    vertex_count = 0 if mesh.vbo is None else len(mesh.vbo)

    face_count = (
        0
        if mesh.ibo is None or mesh.polygon_stride == 0
        else len(mesh.ibo) // mesh.polygon_stride
    )

    print(f"vertex count:     {vertex_count:,}")
    print(f"face count:       {face_count:,}")
    print(f"polygon stride:   {mesh.polygon_stride}")
    print(f"has normals:      {mesh.nbo is not None}")
    print(f"has colors:       {mesh.cbo is not None}")
    print()

    if mesh.vbo is not None and len(mesh.vbo) > 0:
        positions = mesh.vbo[:, :3]

        minimum = np.min(positions, axis=0)
        maximum = np.max(positions, axis=0)
        center = (minimum + maximum) * 0.5
        extent = maximum - minimum

        print("Bounds")
        print("------")
        print(f"minimum:          {minimum}")
        print(f"maximum:          {maximum}")
        print(f"center:           {center}")
        print(f"extent:           {extent}")
        print()

    print_array_debug("VBO", mesh.vbo)
    print_array_debug("NBO", mesh.nbo)
    print_array_debug("CBO", mesh.cbo)
    print_array_debug("IBO", mesh.ibo)

    if mesh.ibo is not None and mesh.polygon_stride > 0:
        faces = mesh.ibo.reshape(-1, mesh.polygon_stride)

        print("Faces")
        print("-----")
        print(f"shape:            {faces.shape}")
        print("first faces:")
        print(faces[:5])
        print()

    errors = validate_mesh(mesh)

    print("Validation")
    print("----------")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("passed")

    print("=" * 80)


def test_copy(mesh: MeshData) -> None:
    copied = mesh.copy()

    print("Copy test")
    print("---------")

    for name in ("vbo", "ibo", "nbo", "cbo"):
        original = getattr(mesh, name)
        duplicate = getattr(copied, name)

        if original is None:
            passed = duplicate is None
        else:
            passed = (
                duplicate is not None
                and np.array_equal(original, duplicate)
                and not np.shares_memory(original, duplicate)
            )

        print(f"{name}: {'passed' if passed else 'failed'}")

        if not passed:
            raise AssertionError(f"{name} copy test failed")

    stride_passed = (
        mesh.polygon_stride == copied.polygon_stride
    )

    print(
        f"polygonStride: "
        f"{'passed' if stride_passed else 'failed'}"
    )
    print()

    if not stride_passed:
        raise AssertionError("polygonStride copy test failed")


def equalize_axes(ax, positions: np.ndarray) -> None:
    minimum = np.min(positions, axis=0)
    maximum = np.max(positions, axis=0)

    center = (minimum + maximum) * 0.5
    radius = float(np.max(maximum - minimum) * 0.5)

    if radius <= 0:
        radius = 1.0

    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)


def choose_indices(
    count: int,
    maximum: int,
    seed: int,
) -> np.ndarray:
    if count <= maximum:
        return np.arange(count)

    rng = np.random.default_rng(seed)

    return np.sort(
        rng.choice(
            count,
            size=maximum,
            replace=False,
        )
    )


def visualize_mesh(
    mesh: MeshData,
    title: str,
    *,
    maximum_faces: int,
    maximum_points: int,
    seed: int,
    wireframe: bool,
    show_vertices: bool,
    show_normals: bool,
    normal_scale: float,
) -> None:
    if mesh.vbo is None or len(mesh.vbo) == 0:
        raise ValueError("Mesh has no vertices")

    positions = mesh.vbo[:, :3].astype(
        np.float64,
        copy=False,
    )

    figure = plt.figure(figsize=(12, 9))
    ax = figure.add_subplot(111, projection="3d")

    rendered_face_count = 0

    if (
        mesh.ibo is not None
        and mesh.polygon_stride > 0
        and len(mesh.ibo) > 0
    ):
        faces = mesh.ibo.reshape(
            -1,
            mesh.polygon_stride,
        )

        face_indices = choose_indices(
            len(faces),
            maximum_faces,
            seed,
        )

        selected_faces = faces[face_indices]
        polygons = positions[selected_faces]

        rendered_face_count = len(selected_faces)

        face_colors = None

        if mesh.cbo is not None:
            vertex_colors = (
                mesh.cbo.astype(np.float32) / 255.0
            )

            face_colors = np.mean(
                vertex_colors[selected_faces],
                axis=1,
            )

        collection = Poly3DCollection(
            polygons,
            facecolors=face_colors,
            edgecolors="black" if wireframe else "none",
            linewidths=0.1 if wireframe else 0.0,
        )

        ax.add_collection3d(collection)

    if show_vertices or rendered_face_count == 0:
        point_indices = choose_indices(
            len(positions),
            maximum_points,
            seed,
        )

        selected_positions = positions[point_indices]

        point_colors = None

        if mesh.cbo is not None:
            point_colors = (
                mesh.cbo[point_indices].astype(np.float32)
                / 255.0
            )

        ax.scatter(
            selected_positions[:, 0],
            selected_positions[:, 1],
            selected_positions[:, 2],
            c=point_colors,
            s=1.0,
            depthshade=False,
        )

    if show_normals and mesh.nbo is not None:
        normal_indices = choose_indices(
            len(positions),
            maximum_points,
            seed,
        )

        normal_positions = positions[normal_indices]
        normals = mesh.nbo[
            normal_indices,
            :3,
        ].astype(np.float64, copy=False)

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
        f"{title}\n"
        f"{len(positions):,} vertices, "
        f"{rendered_face_count:,} rendered faces"
    )

    print("Visualizer")
    print("----------")
    print(f"rendered faces:   {rendered_face_count:,}")
    print(f"maximum faces:    {maximum_faces:,}")
    print(f"maximum points:   {maximum_points:,}")
    print(f"wireframe:        {wireframe}")
    print(f"vertices:         {show_vertices}")
    print(f"normals:          {show_normals}")
    print()

    plt.tight_layout()
    plt.show()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Parse, test, debug, and visualize a PLY file "
            "using the plyfile library."
        )
    )

    parser.add_argument(
        "ply_file",
        type=Path,
    )

    parser.add_argument(
        "--no-mmap",
        action="store_true",
        help="Disable plyfile memory mapping.",
    )

    parser.add_argument(
        "--no-visualizer",
        action="store_true",
    )

    parser.add_argument(
        "--skip-copy-test",
        action="store_true",
    )

    parser.add_argument(
        "--max-faces",
        type=int,
        default=200_000,
    )

    parser.add_argument(
        "--max-points",
        type=int,
        default=100_000,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--wireframe",
        action="store_true",
    )

    parser.add_argument(
        "--vertices",
        action="store_true",
    )

    parser.add_argument(
        "--normals",
        action="store_true",
    )

    parser.add_argument(
        "--normal-scale",
        type=float,
        default=0.05,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    if not args.ply_file.is_file():
        print(
            f"ERROR: file does not exist: {args.ply_file}",
            file=sys.stderr,
        )
        return 1

    if args.max_faces <= 0:
        print(
            "ERROR: --max-faces must be greater than zero",
            file=sys.stderr,
        )
        return 1

    if args.max_points <= 0:
        print(
            "ERROR: --max-points must be greater than zero",
            file=sys.stderr,
        )
        return 1

    try:
        mesh = parse_ply(
            args.ply_file,
            mmap_enabled=not args.no_mmap,
            debug=True,
        )

        print_mesh_debug(mesh)

        errors = validate_mesh(mesh)

        if errors:
            return 2

        if not args.skip_copy_test:
            test_copy(mesh)

        if not args.no_visualizer:
            visualize_mesh(
                mesh,
                args.ply_file.name,
                maximum_faces=args.max_faces,
                maximum_points=args.max_points,
                seed=args.seed,
                wireframe=args.wireframe,
                show_vertices=args.vertices,
                show_normals=args.normals,
                normal_scale=args.normal_scale,
            )

    except Exception as exc:
        print(
            f"ERROR: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
