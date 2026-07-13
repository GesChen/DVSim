from __future__ import annotations

import copy
import mmap
from pathlib import Path
from typing import Optional

import numpy as np


class PLYParseError(AssertionError):
    pass


def _assert(condition: bool, message: str = "PLY parser assertion failed") -> None:
    if not condition:
        raise PLYParseError(message)


class MeshData:
    """
    Python equivalent of the C++ MeshData structure.

    Arrays:
        vbo: float32, shape (num_vertices, 4)
        ibo: uint32, shape (num_faces * polygon_stride,)
        nbo: float32, shape (num_vertices, 4), or None
        cbo: uint8,   shape (num_vertices, 4), or None
    """

    def __init__(self, polygon_stride: int = 3) -> None:
        self.vbo: Optional[np.ndarray] = None
        self.ibo: Optional[np.ndarray] = None
        self.nbo: Optional[np.ndarray] = None
        self.cbo: Optional[np.ndarray] = None
        self.polygonStride = int(polygon_stride)

    @property
    def polygon_stride(self) -> int:
        return self.polygonStride

    @polygon_stride.setter
    def polygon_stride(self, value: int) -> None:
        self.polygonStride = int(value)

    def __copy__(self) -> MeshData:
        result = MeshData(self.polygonStride)

        if self.vbo is not None:
            result.vbo = self.vbo.copy()

        if self.ibo is not None:
            result.ibo = self.ibo.copy()

        if self.nbo is not None:
            result.nbo = self.nbo.copy()

        if self.cbo is not None:
            result.cbo = self.cbo.copy()

        return result

    def __deepcopy__(self, memo: dict) -> MeshData:
        result = self.__copy__()
        memo[id(self)] = result
        return result

    def copy(self) -> MeshData:
        return copy.copy(self)


def PLYParse(meshData: MeshData, filename: str | Path) -> None:
    """
    Parse the same restricted binary PLY format as the supplied C++ parser.

    This intentionally preserves the original parser's assumptions:

    - Only binary_little_endian files are supported.
    - Vertex properties may only be float, uchar, or uint8.
    - Face indices must be `list uchar int`.
    - Positions must be x, y, z, optionally w.
    - Normals must be nx, ny, nz.
    - Colors must be red, green, blue, optionally alpha.
    - All faces are assumed to have the same size as the first face.
    - Only triangular and quad faces are supported.
    - The per-face list count is not individually validated.
    - Extra or missing face packets are handled using the same predicted-face
      calculation as the C++ implementation.
    """

    filename = Path(filename)

    comments: list[str] = []
    obj_info: list[str] = []

    last_element = ""
    last_property = ""

    POSITION = 0
    NORMAL = 1
    COLOR = 2

    num_vertices = 0

    position_dimensions = 0
    normal_dimensions = 0
    color_dimensions = 0

    vertex_layout: list[int] = []

    num_faces = 0
    post_header = 0

    # Read the header in binary mode so the byte offset after end_header is
    # exact, including files using either LF or CRLF line endings.
    with filename.open("rb") as file:
        while True:
            raw_line = file.readline()

            _assert(raw_line != b"", "Unexpected end of file before end_header")

            try:
                line = raw_line.rstrip(b"\r\n").decode("ascii")
            except UnicodeDecodeError as exc:
                raise PLYParseError("PLY header is not ASCII") from exc

            tokens = line.split()
            token = tokens[0] if tokens else ""

            if token in ("ply", "PLY", ""):
                continue

            if token == "comment":
                # Equivalent to line.erase(0, 8).
                comments.append(line[8:])
                continue

            if token == "format":
                _assert(len(tokens) >= 2, "Malformed format declaration")

                format_name = tokens[1]

                _assert(
                    format_name == "binary_little_endian",
                    "Can only parse binary files... why are you using ASCII anyway?",
                )
                continue

            if token == "element":
                _assert(len(tokens) >= 3, "Malformed element declaration")

                name = tokens[1]

                try:
                    size = int(tokens[2])
                except ValueError as exc:
                    raise PLYParseError(
                        f"Invalid element size: {tokens[2]!r}"
                    ) from exc

                _assert(size >= 0, "Element size cannot be negative")

                if name == "vertex":
                    num_vertices = size
                elif name == "face":
                    num_faces = size
                else:
                    raise PLYParseError(f"Can't parse element ({name})")

                last_element = name
                continue

            if token == "property":
                _assert(len(tokens) >= 3, "Malformed property declaration")

                token_index = 1
                property_type = tokens[token_index]
                token_index += 1

                is_list = False

                if property_type == "list":
                    is_list = True

                    _assert(
                        len(tokens) >= 5,
                        "Malformed list property declaration",
                    )

                    count_type = tokens[token_index]
                    token_index += 1

                    property_type = tokens[token_index]
                    token_index += 1

                    _assert(
                        count_type in ("uchar", "uint8"),
                        f"Don't understand count type ({count_type})",
                    )

                    _assert(
                        property_type == "int",
                        f"Don't understand index type ({property_type})",
                    )

                    _assert(
                        last_element == "face",
                        (
                            "Only expecting list after face element, "
                            f"not after ({last_element})"
                        ),
                    )

                _assert(
                    property_type in ("float", "int", "uchar", "uint8"),
                    f"Don't understand type ({property_type})",
                )

                _assert(
                    token_index < len(tokens),
                    "Property has no name",
                )

                name = tokens[token_index]

                if last_element == "vertex":
                    _assert(
                        property_type != "int",
                        "Don't support 32-bit integer properties",
                    )

                    # Position properties
                    if name == "x":
                        position_dimensions = 1
                        vertex_layout.append(POSITION)

                        _assert(
                            property_type == "float",
                            "Don't support 8-bit integer positions",
                        )

                    elif name == "y":
                        _assert(
                            last_property == "x",
                            "Properties should follow x, y, z, (w) order",
                        )
                        position_dimensions = 2

                    elif name == "z":
                        _assert(
                            last_property == "y",
                            "Properties should follow x, y, z, (w) order",
                        )
                        position_dimensions = 3

                    elif name == "w":
                        _assert(
                            last_property == "z",
                            "Properties should follow x, y, z, (w) order",
                        )
                        position_dimensions = 4

                    # Normal properties
                    if name == "nx":
                        normal_dimensions = 1
                        vertex_layout.append(NORMAL)

                        _assert(
                            property_type == "float",
                            "Don't support 8-bit integer normals",
                        )

                    elif name == "ny":
                        _assert(
                            last_property == "nx",
                            "Properties should follow nx, ny, nz order",
                        )
                        normal_dimensions = 2

                    elif name == "nz":
                        _assert(
                            last_property == "ny",
                            "Properties should follow nx, ny, nz order",
                        )
                        normal_dimensions = 3

                    # Color properties
                    if name == "red":
                        color_dimensions = 1
                        vertex_layout.append(COLOR)

                        _assert(
                            property_type in ("uchar", "uint8"),
                            "Don't support non-8-bit integer colors",
                        )

                    elif name == "green":
                        _assert(
                            last_property == "red",
                            (
                                "Properties should follow "
                                "red, green, blue, (alpha) order"
                            ),
                        )
                        color_dimensions = 2

                    elif name == "blue":
                        _assert(
                            last_property == "green",
                            (
                                "Properties should follow "
                                "red, green, blue, (alpha) order"
                            ),
                        )
                        color_dimensions = 3

                    elif name == "alpha":
                        _assert(
                            last_property == "blue",
                            (
                                "Properties should follow "
                                "red, green, blue, (alpha) order"
                            ),
                        )
                        color_dimensions = 4

                elif last_element == "face":
                    _assert(
                        is_list,
                        "No idea what to do with properties following faces",
                    )

                else:
                    raise PLYParseError(
                        "No idea what to do with properties before elements"
                    )

                last_property = name
                continue

            if token == "obj_info":
                # Equivalent to line.erase(0, 9).
                obj_info.append(line[9:])
                continue

            if token == "end_header":
                post_header = file.tell()
                break

            raise PLYParseError(f"Unrecognized PLY header token: {token!r}")

    _assert(num_vertices > 0, "PLY contains no vertices")
    _assert(
        position_dimensions > 0,
        "PLY contains no recognized position properties",
    )

    # Equivalent to filling each Eigen::Vector4f with (0, 0, 0, 1).
    meshData.vbo = np.zeros((num_vertices, 4), dtype=np.float32)
    meshData.vbo[:, 3] = 1.0

    if normal_dimensions:
        meshData.nbo = np.zeros((num_vertices, 4), dtype=np.float32)
        meshData.nbo[:, 3] = 1.0
    else:
        meshData.nbo = None

    if color_dimensions:
        meshData.cbo = np.zeros((num_vertices, 4), dtype=np.uint8)
        meshData.cbo[:, 3] = 255
    else:
        meshData.cbo = None

    meshData.ibo = None

    position_bytes = position_dimensions * 4
    normal_bytes = normal_dimensions * 4
    color_bytes = color_dimensions

    vertex_packet_size_bytes = (
        position_bytes
        + normal_bytes
        + color_bytes
    )

    position_offset_bytes = 0
    normal_offset_bytes = 0
    color_offset_bytes = 0

    offset_so_far_bytes = 0

    for layout_entry in vertex_layout:
        if layout_entry == POSITION:
            position_offset_bytes = offset_so_far_bytes
            offset_so_far_bytes += position_bytes

        elif layout_entry == NORMAL:
            normal_offset_bytes = offset_so_far_bytes
            offset_so_far_bytes += normal_bytes

        elif layout_entry == COLOR:
            color_offset_bytes = offset_so_far_bytes
            offset_so_far_bytes += color_bytes

        else:
            raise PLYParseError("Invalid internal vertex-layout entry")

    file_size = filename.stat().st_size

    _assert(
        post_header <= file_size,
        "Header offset is beyond the end of the file",
    )

    with filename.open("rb") as file:
        if file_size == 0:
            raise PLYParseError("Cannot memory-map an empty PLY file")

        with mmap.mmap(
            file.fileno(),
            length=0,
            access=mmap.ACCESS_READ,
        ) as mapped:
            vertex_data_end = (
                post_header
                + vertex_packet_size_bytes * num_vertices
            )

            _assert(
                vertex_data_end <= file_size,
                "PLY file ends before all declared vertices are present",
            )

            for i in range(num_vertices):
                packet_offset = (
                    post_header
                    + vertex_packet_size_bytes * i
                )

                position = np.frombuffer(
                    mapped,
                    dtype="<f4",
                    count=position_dimensions,
                    offset=packet_offset + position_offset_bytes,
                )

                meshData.vbo[i, :position_dimensions] = position

                if normal_dimensions:
                    normal = np.frombuffer(
                        mapped,
                        dtype="<f4",
                        count=normal_dimensions,
                        offset=packet_offset + normal_offset_bytes,
                    )

                    meshData.nbo[i, :normal_dimensions] = normal

                if color_dimensions:
                    color = np.frombuffer(
                        mapped,
                        dtype=np.uint8,
                        count=color_dimensions,
                        offset=packet_offset + color_offset_bytes,
                    )

                    meshData.cbo[i, :color_dimensions] = color

            bytes_so_far = vertex_data_end
            face_data_offset = vertex_data_end

            if num_faces > 0:
                _assert(
                    face_data_offset < file_size,
                    "PLY declares faces but contains no face data",
                )

                face_dimensions = mapped[face_data_offset]

                _assert(
                    face_dimensions in (3, 4),
                    (
                        "Only triangular and quad faces are supported; "
                        f"first face contains {face_dimensions} indices"
                    ),
                )

                count_bytes = 1
                face_bytes = face_dimensions * 4
                face_packet_size_bytes = count_bytes + face_bytes

                predicted_faces = (
                    file_size - bytes_so_far
                ) // face_packet_size_bytes

                num_faces = min(num_faces, predicted_faces)

                meshData.ibo = np.empty(
                    num_faces * face_dimensions,
                    dtype=np.uint32,
                )

                for i in range(num_faces):
                    packet_offset = (
                        face_data_offset
                        + face_packet_size_bytes * i
                    )

                    indices = np.frombuffer(
                        mapped,
                        dtype="<u4",
                        count=face_dimensions,
                        offset=packet_offset + count_bytes,
                    )

                    output_start = i * face_dimensions
                    output_end = output_start + face_dimensions

                    meshData.ibo[output_start:output_end] = indices

                meshData.polygonStride = face_dimensions

            else:
                meshData.polygonStride = 0


# Conventional snake_case alias.
ply_parse = PLYParse