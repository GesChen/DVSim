# mesh_visualizer.py

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np
import pyvista as pv

if TYPE_CHECKING:
    from mesh_data import MeshData


def _normalize_mesh_input(
    meshes: MeshData | Sequence[MeshData],
) -> list[MeshData]:
    if hasattr(meshes, "vbo") and hasattr(meshes, "ibo"):
        return [meshes]

    result = list(meshes)

    if not result:
        raise ValueError("No meshes were provided.")

    for index, mesh in enumerate(result):
        if not hasattr(mesh, "vbo") or not hasattr(mesh, "ibo"):
            raise TypeError(
                f"Item {index} is not a MeshData-compatible object."
            )

    return result


def _validate_mesh(mesh: MeshData, mesh_index: int) -> None:
    if mesh.vbo is None:
        raise ValueError(f"Mesh {mesh_index} has no VBO.")

    if mesh.ibo is None:
        raise ValueError(f"Mesh {mesh_index} has no IBO.")

    if mesh.vbo.ndim != 2 or mesh.vbo.shape[1] < 3:
        raise ValueError(
            f"Mesh {mesh_index} VBO must have shape (N, 3+) but has "
            f"{mesh.vbo.shape}."
        )

    if mesh.ibo.ndim != 1:
        raise ValueError(
            f"Mesh {mesh_index} IBO must be one-dimensional."
        )

    if mesh.polygon_stride < 3:
        raise ValueError(
            f"Mesh {mesh_index} polygon_stride must be at least 3."
        )

    if mesh.ibo.size % mesh.polygon_stride != 0:
        raise ValueError(
            f"Mesh {mesh_index} IBO length {mesh.ibo.size} is not divisible "
            f"by polygon_stride {mesh.polygon_stride}."
        )

    if mesh.ibo.size > 0:
        largest_index = int(np.max(mesh.ibo))

        if largest_index >= len(mesh.vbo):
            raise IndexError(
                f"Mesh {mesh_index} references vertex {largest_index}, "
                f"but contains only {len(mesh.vbo)} vertices."
            )


def _select_faces(
    mesh: MeshData,
    max_face_count: int | None,
) -> np.ndarray:
    faces = mesh.ibo.reshape(-1, mesh.polygon_stride)

    if max_face_count is None or len(faces) <= max_face_count:
        return faces

    if max_face_count <= 0:
        raise ValueError("max_face_count must be greater than zero.")

    selected = np.linspace(
        0,
        len(faces) - 1,
        max_face_count,
        dtype=np.int64,
    )

    return faces[selected]


def _make_padded_faces(
    faces: np.ndarray,
    polygon_stride: int,
) -> np.ndarray:
    """
    Convert:

        [[0, 1, 2, 3],
         [4, 5, 6, 7]]

    into PyVista/VTK padded connectivity:

        [4, 0, 1, 2, 3,
         4, 4, 5, 6, 7]
    """
    padded = np.empty(
        (len(faces), polygon_stride + 1),
        dtype=np.int64,
    )

    padded[:, 0] = polygon_stride
    padded[:, 1:] = faces.astype(np.int64, copy=False)

    return padded.reshape(-1)


def _normalize_rgba(colors: np.ndarray) -> np.ndarray:
    rgba = np.asarray(colors)

    if rgba.ndim != 2 or rgba.shape[1] not in (3, 4):
        raise ValueError(
            f"Color array must have shape (N, 3) or (N, 4), got "
            f"{rgba.shape}."
        )

    if rgba.dtype == np.uint8:
        if rgba.shape[1] == 3:
            alpha = np.full(
                (len(rgba), 1),
                255,
                dtype=np.uint8,
            )
            rgba = np.concatenate((rgba, alpha), axis=1)

        return rgba.copy()

    rgba = rgba.astype(np.float32, copy=True)

    if rgba.size > 0 and np.max(rgba) <= 1.0:
        rgba *= 255.0

    rgba = np.clip(rgba, 0.0, 255.0).astype(np.uint8)

    if rgba.shape[1] == 3:
        alpha = np.full(
            (len(rgba), 1),
            255,
            dtype=np.uint8,
        )
        rgba = np.concatenate((rgba, alpha), axis=1)

    return rgba


def _prepare_random_colors(
    mesh_count: int,
    seed: int | None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)

    # Avoid colors that are nearly black.
    return rng.uniform(
        low=0.2,
        high=1.0,
        size=(mesh_count, 3),
    )


def _normal_sample_indices(
    normal_count: int,
    max_normal_count: int,
) -> np.ndarray:
    if max_normal_count <= 0:
        raise ValueError("max_normal_count must be greater than zero.")

    if normal_count <= max_normal_count:
        return np.arange(normal_count, dtype=np.int64)

    return np.linspace(
        0,
        normal_count - 1,
        max_normal_count,
        dtype=np.int64,
    )


def visualize_mesh(
    meshes: MeshData | Sequence[MeshData],
    *,
    title: str = "MeshData Visualizer",
    show_vertices: bool = False,
    show_wireframe: bool = False,
    show_normals: bool = False,
    use_vertex_colors: bool = True,
    separate_mesh_colors: bool = False,
    random_seed: int | None = None,
    face_alpha: float = 1.0,
    edge_alpha: float = 0.5,
    vertex_size: float = 4.0,
    normal_length: float | None = None,
    max_normal_count: int = 2000,
    max_face_count: int | None = None,
    background: str | tuple[float, float, float] | None = None,
    window_size: tuple[int, int] = (1280, 800),
    smooth_shading: bool = False,
    show_axes: bool = True,
    show_bounds: bool = False,
    block: bool = True,
) -> pv.Plotter:
    """
    Visualize one MeshData object or a sequence of MeshData objects.

    Color priority
    --------------
    1. If separate_mesh_colors is True, each mesh receives one random
       uniform color. This overrides CBO vertex colors.
    2. Otherwise, if use_vertex_colors is True and valid CBO data exists,
       the stored vertex colors are used.
    3. Otherwise, PyVista's default mesh color is used.

    Parameters
    ----------
    meshes:
        One MeshData instance or a sequence of MeshData instances.

    show_vertices:
        Draw the vertex positions as points.

    show_wireframe:
        Draw polygon edges over the surfaces.

    show_normals:
        Draw sampled vertex-normal arrows.

    separate_mesh_colors:
        Assign each mesh one random color. Overrides vertex colors.

    random_seed:
        Optional deterministic random-color seed.

    max_face_count:
        Maximum number of source polygons displayed per mesh. Polygons are
        sampled uniformly when this limit is exceeded.

    block:
        Passed to PyVista's interactive update mode. If True, show() blocks
        until the window closes.

    Returns
    -------
    pyvista.Plotter
        The created plotter.
    """
    mesh_list = _normalize_mesh_input(meshes)

    for mesh_index, mesh in enumerate(mesh_list):
        _validate_mesh(mesh, mesh_index)

    if not 0.0 <= face_alpha <= 1.0:
        raise ValueError("face_alpha must be between 0 and 1.")

    if not 0.0 <= edge_alpha <= 1.0:
        raise ValueError("edge_alpha must be between 0 and 1.")

    plotter = pv.Plotter(
        title=title,
        window_size=window_size,
    )

    if background is not None:
        plotter.set_background(background)

    if show_axes:
        plotter.add_axes()

    random_colors = None

    if separate_mesh_colors:
        random_colors = _prepare_random_colors(
            len(mesh_list),
            random_seed,
        )

    all_positions = np.concatenate(
        [mesh.vbo[:, :3] for mesh in mesh_list],
        axis=0,
    )

    if normal_length is None:
        extent = np.ptp(all_positions, axis=0)
        diagonal = float(np.linalg.norm(extent))
        normal_length = diagonal * 0.02 if diagonal > 0.0 else 0.1

    for mesh_index, mesh in enumerate(mesh_list):
        positions = np.asarray(
            mesh.vbo[:, :3],
            dtype=np.float32,
        )

        selected_faces = _select_faces(
            mesh,
            max_face_count,
        )

        padded_faces = _make_padded_faces(
            selected_faces,
            mesh.polygon_stride,
        )

        pv_mesh = pv.PolyData(
            positions,
            padded_faces,
        )

        has_vertex_colors = (
            mesh.cbo is not None
            and len(mesh.cbo) == len(mesh.vbo)
        )

        add_mesh_kwargs = {
            "opacity": face_alpha,
            "show_edges": show_wireframe,
            "edge_opacity": edge_alpha,
            "smooth_shading": smooth_shading,
            "show_scalar_bar": False,
            "name": f"mesh_{mesh_index}",
        }

        if separate_mesh_colors:
            add_mesh_kwargs["color"] = random_colors[mesh_index]

        elif use_vertex_colors and has_vertex_colors:
            rgba = _normalize_rgba(mesh.cbo)
            pv_mesh.point_data["rgba"] = rgba

            add_mesh_kwargs["scalars"] = "rgba"
            add_mesh_kwargs["rgba"] = True

        plotter.add_mesh(
            pv_mesh,
            **add_mesh_kwargs,
        )

        if show_vertices:
            point_kwargs = {
                "point_size": vertex_size,
                "render_points_as_spheres": True,
                "show_scalar_bar": False,
                "name": f"vertices_{mesh_index}",
            }

            if separate_mesh_colors:
                point_kwargs["color"] = random_colors[mesh_index]

            elif use_vertex_colors and has_vertex_colors:
                point_cloud = pv.PolyData(positions)
                point_cloud.point_data["rgba"] = _normalize_rgba(mesh.cbo)

                plotter.add_points(
                    point_cloud,
                    scalars="rgba",
                    rgba=True,
                    **point_kwargs,
                )
            else:
                plotter.add_points(
                    positions,
                    **point_kwargs,
                )

        if (
            show_normals
            and mesh.nbo is not None
            and len(mesh.nbo) == len(mesh.vbo)
        ):
            normal_indices = _normal_sample_indices(
                len(mesh.nbo),
                max_normal_count,
            )

            normal_positions = positions[normal_indices]
            normal_vectors = np.asarray(
                mesh.nbo[normal_indices, :3],
                dtype=np.float32,
            )

            lengths = np.linalg.norm(
                normal_vectors,
                axis=1,
            )

            valid = lengths > 1e-12

            normal_positions = normal_positions[valid]
            normal_vectors = normal_vectors[valid]
            lengths = lengths[valid]

            if len(normal_vectors) > 0:
                normal_vectors = normal_vectors / lengths[:, None]

                arrow_kwargs = {
                    "name": f"normals_{mesh_index}",
                }

                if separate_mesh_colors:
                    arrow_kwargs["color"] = random_colors[mesh_index]

                plotter.add_arrows(
                    normal_positions,
                    normal_vectors,
                    mag=normal_length,
                    **arrow_kwargs,
                )

    if show_bounds:
        plotter.show_bounds(
            grid="back",
            location="outer",
            all_edges=True,
        )

    plotter.reset_camera()

    if block:
        plotter.show()
    else:
        plotter.show(
            interactive_update=True,
            auto_close=False,
        )

    return plotter


def visualize_meshes(
    meshes: MeshData | Sequence[MeshData],
    **kwargs,
) -> pv.Plotter:
    return visualize_mesh(meshes, **kwargs)