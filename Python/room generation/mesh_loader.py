from __future__ import annotations

from pathlib import Path

import numpy as np
from plyfile import PlyData

from mesh_data import MeshData

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


def load_ply_mesh(
    path: str | Path,
    debug: bool = False,
) -> MeshData:
    path = Path(path)

    if debug:
        print(f"Reading PLY: {path}", flush=True)

    ply = PlyData.read(str(path))

    if "vertex" not in ply:
        raise ValueError("PLY file has no vertex element.")

    vertices = ply["vertex"].data
    vertex_fields = set(vertices.dtype.names or ())

    required_positions = {"x", "y", "z"}

    if not required_positions.issubset(vertex_fields):
        raise ValueError(
            "PLY vertex data must contain x, y, and z fields."
        )

    vertex_count = len(vertices)

    if debug:
        print(f"Loading {vertex_count:,} vertices", flush=True)

    # Vertex positions: x, y, z, w=1
    vbo = np.empty((vertex_count, 4), dtype=np.float32)
    vbo[:, 0] = vertices["x"]
    vbo[:, 1] = vertices["y"]
    vbo[:, 2] = vertices["z"]
    vbo[:, 3] = 1.0

    # Vertex normals: nx, ny, nz, w=0
    if {"nx", "ny", "nz"}.issubset(vertex_fields):
        nbo = np.empty((vertex_count, 4), dtype=np.float32)
        nbo[:, 0] = vertices["nx"]
        nbo[:, 1] = vertices["ny"]
        nbo[:, 2] = vertices["nz"]
        nbo[:, 3] = 0.0
    else:
        nbo = None

    # Vertex colors: red, green, blue, alpha
    if {"red", "green", "blue"}.issubset(vertex_fields):
        cbo = np.empty((vertex_count, 4), dtype=np.uint8)
        cbo[:, 0] = vertices["red"]
        cbo[:, 1] = vertices["green"]
        cbo[:, 2] = vertices["blue"]

        if "alpha" in vertex_fields:
            cbo[:, 3] = vertices["alpha"]
        else:
            cbo[:, 3] = 255
    else:
        cbo = None

    if "face" not in ply:
        raise ValueError("PLY file has no face element.")

    face_data = ply["face"].data
    face_fields = set(face_data.dtype.names or ())

    if "vertex_indices" in face_fields:
        index_property = "vertex_indices"
    elif "vertex_index" in face_fields:
        index_property = "vertex_index"
    else:
        raise ValueError(
            "PLY face data has neither 'vertex_indices' nor "
            "'vertex_index'."
        )

    face_lists = face_data[index_property]
    face_count = len(face_lists)

    if debug:
        print(f"Loading {face_count:,} faces", flush=True)

    if face_count == 0:
        polygon_stride = 0
        ibo = np.empty((0,), dtype=np.uint32)
    else:
        polygon_stride = len(face_lists[0])

        face_iterator = enumerate(face_lists)

        if debug and tqdm is not None:
            face_iterator = tqdm(
                face_iterator,
                total=face_count,
                desc="Validating faces",
                unit="face",
                dynamic_ncols=True,
            )

        converted_faces: list[np.ndarray] = []

        for face_index, face in face_iterator:
            if len(face) != polygon_stride:
                raise ValueError(
                    "Mixed polygon sizes are not supported: "
                    f"face 0 has {polygon_stride} vertices, but face "
                    f"{face_index} has {len(face)}."
                )

            converted_faces.append(
                np.asarray(face, dtype=np.uint32)
            )

        if debug and tqdm is None:
            print("Face validation complete", flush=True)

        if debug:
            print("Building index buffer", flush=True)

        face_matrix = np.stack(
            converted_faces,
            axis=0,
        )

        ibo = face_matrix.reshape(-1)

    if debug:
        print(
            f"PLY loaded: {vertex_count:,} vertices, "
            f"{face_count:,} faces, stride {polygon_stride}",
            flush=True,
        )

    return MeshData(
        vbo=vbo,
        ibo=ibo,
        nbo=nbo,
        cbo=cbo,
        polygon_stride=polygon_stride,
    )