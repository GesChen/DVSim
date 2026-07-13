# Copyright (c) Facebook, Inc. and its affiliates.
# All Rights Reserved

from __future__ import annotations

from typing import Iterable, Optional, TypeVar

import numpy as np
from numpy.typing import NDArray

from mesh_data import MeshData

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


Float32Array = NDArray[np.float32]
UInt32Array = NDArray[np.uint32]
UInt8Array = NDArray[np.uint8]

T = TypeVar("T")


def _debug_print(debug: bool, message: str) -> None:
    if debug:
        print(message, flush=True)


def _debug_progress(
    iterable: Iterable[T],
    *,
    debug: bool,
    desc: str,
    total: Optional[int] = None,
) -> Iterable[T]:
    """
    Wrap an iterable with tqdm when debug mode is enabled.

    If tqdm is unavailable, the iterable is returned unchanged and progress
    is reported through start/completion print statements around the loop.
    """
    if debug and tqdm is not None:
        return tqdm(
            iterable,
            desc=desc,
            total=total,
            unit="item",
            dynamic_ncols=True,
        )

    return iterable


def _part1_by2(x: int) -> int:
    """
    Spread the lower 21 bits of x so that two zero bits occur between
    each original bit.

    This directly reproduces the C++ Part1By2 lambda using unsigned
    64-bit arithmetic.
    """
    x = int(x) & 0xFFFFFFFFFFFFFFFF

    x &= 0x1FFFFF
    x = (x | (x << 32)) & 0x1F00000000FFFF
    x = (x | (x << 16)) & 0x1F0000FF0000FF
    x = (x | (x << 8)) & 0x100F00F00F00F00F
    x = (x | (x << 4)) & 0x10C30C30C30C30C3
    x = (x | (x << 2)) & 0x1249249249249249

    return x & 0xFFFFFFFFFFFFFFFF


def _encode_morton3(v: NDArray[np.integer]) -> int:
    """
    Encode a three-dimensional integer coordinate into a Morton code.

    The bit ordering exactly matches the C++ implementation:

        x bits -> positions 0, 3, 6, ...
        y bits -> positions 1, 4, 7, ...
        z bits -> positions 2, 5, 8, ...
    """
    if v.shape != (3,):
        raise ValueError(
            f"Expected a three-element vector, got shape {v.shape}"
        )

    x = int(v[0])
    y = int(v[1])
    z = int(v[2])

    code = (
        (_part1_by2(z) << 2)
        + (_part1_by2(y) << 1)
        + _part1_by2(x)
    )

    return code & 0xFFFFFFFFFFFFFFFF


def _cpp_float_to_int32_trunc(value: np.float32) -> np.int32:
    """
    Reproduce Eigen's float-to-int cast for ordinary finite values.

    C++ integer conversion truncates toward zero.
    """
    return np.int32(np.trunc(value))


def split_mesh(
    mesh: MeshData,
    split_size: float,
    debug: bool = False,
) -> list[MeshData]:
    """
    Python translation of PTexMesh::SplitMesh.

    Faces are assigned a Morton code equal to the minimum Morton code of
    their four referenced vertices. Faces with equal codes are grouped
    into one output submesh.

    Within each submesh:

    - faces retain their order after sorting by code;
    - vertices are inserted in first-reference order;
    - vertex indices are remapped to a contiguous local index range;
    - only VBO and NBO data are copied;
    - color data is not copied, matching the C++ implementation;
    - polygon_stride is set to 4.

    Parameters
    ----------
    mesh:
        Input mesh containing VBO, IBO and NBO arrays.

    split_size:
        World-space grid cell size. Must be greater than zero.

    debug:
        When True, reports every major processing step. Iterative operations
        use tqdm progress bars when tqdm is installed. Non-iterative operations
        use printed status messages.

    Returns
    -------
    list[MeshData]
        One mesh for each distinct face Morton code.
    """
    _debug_print(debug, "[SplitMesh] Starting mesh split")

    split_size_f32 = np.float32(split_size)

    _debug_print(
        debug,
        f"[SplitMesh] Validating split size: {split_size_f32}",
    )

    if (
        not np.isfinite(split_size_f32)
        or split_size_f32 <= np.float32(0.0)
    ):
        raise ValueError(
            "split_size must be a finite value greater than zero"
        )

    _debug_print(debug, "[SplitMesh] Reading mesh dimensions")

    vertex_count = mesh.vbo.shape[0]

    if vertex_count == 0:
        _debug_print(
            debug,
            "[SplitMesh] Mesh contains no vertices; returning no submeshes",
        )
        return []

    _debug_print(
        debug,
        (
            f"[SplitMesh] Input arrays: "
            f"vbo={mesh.vbo.shape}, "
            f"ibo={mesh.ibo.shape}, "
            f"nbo={mesh.nbo.shape}"
        ),
    )

    _debug_print(debug, "[SplitMesh] Validating VBO")

    if mesh.vbo.ndim != 2 or mesh.vbo.shape[1] != 4:
        raise ValueError(
            f"mesh.vbo must have shape (N, 4), got {mesh.vbo.shape}"
        )

    _debug_print(debug, "[SplitMesh] Validating NBO")

    if mesh.nbo.ndim != 2 or mesh.nbo.shape[1] != 4:
        raise ValueError(
            f"mesh.nbo must have shape (N, 4), got {mesh.nbo.shape}"
        )

    if mesh.nbo.shape[0] != vertex_count:
        raise ValueError(
            "mesh.nbo must contain one normal for every vertex: "
            f"{mesh.nbo.shape[0]} normals for {vertex_count} vertices"
        )

    _debug_print(debug, "[SplitMesh] Validating IBO")

    if mesh.ibo.ndim != 1:
        raise ValueError(
            "mesh.ibo must be a flattened one-dimensional array, "
            f"got shape {mesh.ibo.shape}"
        )

    if mesh.ibo.size % 4 != 0:
        raise ValueError(
            "mesh.ibo length must be divisible by four because the original "
            "SplitMesh function unconditionally processes quadrilateral faces"
        )

    num_faces = mesh.ibo.size // 4

    _debug_print(
        debug,
        (
            f"[SplitMesh] Mesh contains {vertex_count:,} vertices and "
            f"{num_faces:,} faces"
        ),
    )

    if num_faces == 0:
        _debug_print(
            debug,
            "[SplitMesh] Mesh contains no faces; returning no submeshes",
        )
        return []

    _debug_print(
        debug,
        "[SplitMesh] Checking all face indices against the vertex count",
    )

    ibo_uint64 = mesh.ibo.astype(np.uint64)
    invalid_index_mask = ibo_uint64 >= vertex_count

    if np.any(invalid_index_mask):
        bad_positions = np.flatnonzero(invalid_index_mask)
        first_bad_position = int(bad_positions[0])
        bad_index = int(mesh.ibo[first_bad_position])

        raise IndexError(
            f"IBO element {first_bad_position} references vertex "
            f"{bad_index}, but the mesh contains only {vertex_count} vertices"
        )

    del ibo_uint64
    del invalid_index_mask

    _debug_print(
        debug,
        "[SplitMesh] Computing mesh bounding-box minimum",
    )

    positions = mesh.vbo[:, :3]
    bounding_box_min = np.min(
        positions,
        axis=0,
    ).astype(
        np.float32,
        copy=False,
    )

    _debug_print(
        debug,
        (
            "[SplitMesh] Bounding-box minimum: "
            f"({bounding_box_min[0]}, "
            f"{bounding_box_min[1]}, "
            f"{bounding_box_min[2]})"
        ),
    )

    # C++:
    #     Eigen::Vector3f pi =
    #         (p - boundingBox.min()) / splitSize;
    #     verts[i] = EncodeMorton3(pi.cast<int>());
    #
    # verts is uint32, so the 64-bit Morton result is truncated to its
    # lower 32 bits on assignment.
    vertex_codes = np.empty(vertex_count, dtype=np.uint32)

    _debug_print(
        debug,
        "[SplitMesh] Computing Morton code for every vertex",
    )

    vertex_iterator = _debug_progress(
        range(vertex_count),
        debug=debug,
        desc="Vertex Morton codes",
        total=vertex_count,
    )

    for i in vertex_iterator:
        p = positions[i]

        grid_position_float = (
            (p - bounding_box_min) / split_size_f32
        ).astype(
            np.float32,
            copy=False,
        )

        grid_position_int = np.empty(3, dtype=np.int32)

        for axis in range(3):
            grid_position_int[axis] = _cpp_float_to_int32_trunc(
                grid_position_float[axis]
            )

        morton_code_64 = _encode_morton3(grid_position_int)
        vertex_codes[i] = np.uint32(
            morton_code_64 & 0xFFFFFFFF
        )

    if debug and tqdm is None:
        _debug_print(
            debug,
            (
                "[SplitMesh] Completed Morton-code generation for "
                f"{vertex_count:,} vertices"
            ),
        )

    _debug_print(
        debug,
        "[SplitMesh] Reshaping the index buffer into quadrilateral faces",
    )

    face_indices = mesh.ibo.reshape((-1, 4)).copy()

    _debug_print(
        debug,
        "[SplitMesh] Creating original face-index array",
    )

    original_faces = np.arange(
        num_faces,
        dtype=np.uint64,
    )

    face_codes = np.empty(
        num_faces,
        dtype=np.uint32,
    )

    _debug_print(
        debug,
        "[SplitMesh] Computing the minimum vertex Morton code for each face",
    )

    face_iterator = _debug_progress(
        range(num_faces),
        debug=debug,
        desc="Face Morton codes",
        total=num_faces,
    )

    for i in face_iterator:
        code = np.uint32(0xFFFFFFFF)

        for j in range(4):
            vertex_index = int(face_indices[i, j])
            vertex_code = vertex_codes[vertex_index]

            if vertex_code < code:
                code = vertex_code

        face_codes[i] = code

    if debug and tqdm is None:
        _debug_print(
            debug,
            (
                "[SplitMesh] Completed Morton-code generation for "
                f"{num_faces:,} faces"
            ),
        )

    # std::sort only compares code. Equal-code ordering is formally
    # unspecified because std::sort is not stable.
    #
    # NumPy's quicksort is also unstable and therefore most closely reflects
    # the C++ contract. Exact equal-key ordering can still differ between
    # standard-library implementations.
    _debug_print(
        debug,
        "[SplitMesh] Sorting faces by Morton code",
    )

    sorted_order = np.argsort(
        face_codes,
        kind="quicksort",
    )

    _debug_print(
        debug,
        "[SplitMesh] Applying sorted face order",
    )

    sorted_face_indices = face_indices[sorted_order]
    sorted_face_codes = face_codes[sorted_order]
    sorted_original_faces = original_faces[sorted_order]

    # Preserve the originalFace field even though the supplied C++ function
    # does not use it after sorting.
    del sorted_original_faces
    del original_faces
    del sorted_order
    del face_indices
    del face_codes

    _debug_print(
        debug,
        "[SplitMesh] Locating boundaries between Morton-code chunks",
    )

    code_changes = np.flatnonzero(
        sorted_face_codes[1:] != sorted_face_codes[:-1]
    )

    _debug_print(
        debug,
        "[SplitMesh] Constructing chunk start offsets",
    )

    chunk_starts = np.empty(
        code_changes.size + 2,
        dtype=np.uint64,
    )

    chunk_starts[0] = 0

    if code_changes.size:
        chunk_starts[1:-1] = (
            code_changes.astype(np.uint64) + 1
        )

    chunk_starts[-1] = num_faces

    num_chunks = chunk_starts.size - 1

    _debug_print(
        debug,
        (
            f"[SplitMesh] Found {num_chunks:,} distinct Morton-code "
            "chunks"
        ),
    )

    submeshes: list[Optional[MeshData]] = [None] * num_chunks

    _debug_print(
        debug,
        "[SplitMesh] Building output submeshes",
    )

    chunk_iterator = _debug_progress(
        range(num_chunks),
        debug=debug,
        desc="Building submeshes",
        total=num_chunks,
    )

    for chunk_index in chunk_iterator:
        chunk_start = int(chunk_starts[chunk_index])
        chunk_end = int(chunk_starts[chunk_index + 1])
        chunk_size = chunk_end - chunk_start

        if debug and tqdm is None:
            print(
                (
                    f"[SplitMesh] Building chunk "
                    f"{chunk_index + 1:,}/{num_chunks:,}: "
                    f"{chunk_size:,} faces"
                ),
                flush=True,
            )

        referenced_vertices: list[int] = []
        referenced_vertex_map: dict[int, int] = {}

        submesh_ibo = np.empty(
            chunk_size * 4,
            dtype=np.uint32,
        )

        # Avoid nested tqdm bars because there may be thousands of chunks.
        # The outer chunk progress bar tracks this operation.
        for local_face_index in range(chunk_size):
            sorted_face_index = chunk_start + local_face_index

            for corner in range(4):
                source_vertex_index = int(
                    sorted_face_indices[
                        sorted_face_index,
                        corner,
                    ]
                )

                new_index = referenced_vertex_map.get(
                    source_vertex_index
                )

                if new_index is None:
                    new_index = len(referenced_vertices)
                    referenced_vertices.append(
                        source_vertex_index
                    )
                    referenced_vertex_map[
                        source_vertex_index
                    ] = new_index

                submesh_ibo[
                    local_face_index * 4 + corner
                ] = np.uint32(new_index)

        referenced_vertex_array = np.asarray(
            referenced_vertices,
            dtype=np.intp,
        )

        # Advanced indexing returns copies, matching ManagedImage assignment
        # into newly allocated buffers.
        submesh_vbo = mesh.vbo[
            referenced_vertex_array
        ].copy()

        submesh_nbo = mesh.nbo[
            referenced_vertex_array
        ].copy()

        submeshes[chunk_index] = MeshData(
            polygon_stride=4,
            vbo=submesh_vbo,
            ibo=submesh_ibo,
            nbo=submesh_nbo,
            # The C++ function never initializes or copies cbo.
            cbo=np.empty(
                (0, 4),
                dtype=np.uint8,
            ),
        )

        if debug and tqdm is not None:
            chunk_iterator.set_postfix(
                faces=chunk_size,
                vertices=len(referenced_vertices),
                refresh=False,
            )

    if debug and tqdm is None:
        _debug_print(
            debug,
            (
                "[SplitMesh] Completed construction of "
                f"{num_chunks:,} submeshes"
            ),
        )

    _debug_print(
        debug,
        "[SplitMesh] Removing uninitialized submesh entries",
    )

    result = [
        submesh
        for submesh in submeshes
        if submesh is not None
    ]

    total_output_vertices = sum(
        submesh.vbo.shape[0]
        for submesh in result
    )

    total_output_faces = sum(
        submesh.ibo.size // 4
        for submesh in result
    )

    _debug_print(
        debug,
        (
            "[SplitMesh] Complete: "
            f"{len(result):,} submeshes, "
            f"{total_output_vertices:,} copied vertices, "
            f"{total_output_faces:,} faces"
        ),
    )

    return result


# C++-style alias.
SplitMesh = split_mesh