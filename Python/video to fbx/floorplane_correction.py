from pathlib import Path

import cv2
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import numpy as np


def pick_ref_frames(video_path, ref_count):
    video_path = Path(video_path)

    if ref_count < 3:
        raise ValueError("ref_count must be at least 3 to define a plane.")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count <= 0:
        cap.release()
        raise RuntimeError("Could not determine video frame count.")

    refs = [None] * ref_count
    cur_frame = 0
    closed_by_done = False

    def read_frame(i):
        i = max(0, min(frame_count - 1, int(i)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f"Could not read frame {i}")
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def refs_text():
        return " | ".join(f"Ref {i + 1}: {r}" for i, r in enumerate(refs))

    fig, ax = plt.subplots()
    plt.subplots_adjust(bottom=0.35)

    img = ax.imshow(read_frame(cur_frame))
    title = ax.set_title(f"Frame 0 | {refs_text()}")
    ax.axis("off")

    slider_ax = plt.axes([0.15, 0.25, 0.70, 0.03])
    frame_slider = Slider(slider_ax, "Frame", 0, frame_count - 1, valinit=0, valstep=1)

    prev_ax = plt.axes([0.15, 0.15, 0.10, 0.05])
    next_ax = plt.axes([0.27, 0.15, 0.10, 0.05])
    done_ax = plt.axes([0.72, 0.15, 0.13, 0.05])

    prev_btn = Button(prev_ax, "-1")
    next_btn = Button(next_ax, "+1")
    done_btn = Button(done_ax, "Done")

    ref_buttons = []
    button_w = min(0.12, 0.70 / ref_count)
    start_x = 0.15

    for i in range(ref_count):
        ref_ax = plt.axes([start_x + i * button_w, 0.06, button_w * 0.9, 0.05])
        ref_buttons.append(Button(ref_ax, f"Set {i + 1}"))

    def update_title():
        title.set_text(f"Frame {cur_frame} | {refs_text()}")

    def show_frame(i):
        nonlocal cur_frame
        cur_frame = max(0, min(frame_count - 1, int(i)))
        img.set_data(read_frame(cur_frame))
        update_title()
        fig.canvas.draw_idle()

    def step(delta):
        new_frame = max(0, min(frame_count - 1, cur_frame + delta))
        if new_frame != cur_frame:
            frame_slider.set_val(new_frame)

    def set_ref(index):
        refs[index] = cur_frame
        update_title()
        fig.canvas.draw_idle()

    def done(_event):
        nonlocal closed_by_done
        closed_by_done = True
        plt.close(fig)

    frame_slider.on_changed(lambda val: show_frame(int(val)))
    prev_btn.on_clicked(lambda _event: step(-1))
    next_btn.on_clicked(lambda _event: step(1))
    done_btn.on_clicked(done)

    for i, btn in enumerate(ref_buttons):
        btn.on_clicked(lambda _event, i=i: set_ref(i))

    plt.show()
    cap.release()

    if not closed_by_done:
        raise RuntimeError("Window closed before pressing Done.")

    if any(r is None for r in refs):
        raise RuntimeError("All reference frames must be set before pressing Done.")

    return tuple(refs)


def realign_ground_plane(anim, ref_frames, ref_points, up_axis=1, visualize=True):
    """
    anim:       ndarray, shape (frames, points, 3)
    ref_frames: tuple/list of N frame indices
    ref_points: tuple/list of N point indices
    up_axis:    axis to become vertical after alignment: 0=x, 1=y, 2=z

    Each reference sample is:
        anim[ref_frames[i], ref_points[i]]

    Returns:
        aligned_anim, rotation_matrix, ground_normal
    """

    anim = np.asarray(anim, dtype=np.float64)

    if anim.ndim != 3 or anim.shape[2] != 3:
        raise ValueError("anim must have shape (frames, points, 3)")

    # if len(ref_frames) != len(ref_points):
    #     raise ValueError("ref_frames and ref_points must have the same length.")

    # if len(ref_frames) < 3:
    #     raise ValueError("At least 3 reference samples are required to define a plane.")

    ref_frames = tuple(int(f) for f in ref_frames)
    ref_points = tuple(int(p) for p in ref_points)

    samples = np.array(
        [anim[f, p] for f in ref_frames for p in ref_points],
        dtype=np.float64,
    )

    origin = samples.mean(axis=0)

    centered = samples - origin

    _, s, vh = np.linalg.svd(centered, full_matrices=False)

    if s[-1] < 1e-12 and np.linalg.matrix_rank(centered) < 2:
        raise ValueError("Reference samples are degenerate; cannot define a plane.")

    ground_normal = vh[-1]
    ground_normal /= np.linalg.norm(ground_normal)

    target_normal = np.zeros(3)
    target_normal[up_axis] = 1.0

    if np.dot(ground_normal, target_normal) < 0:
        ground_normal = -ground_normal

    R = rotation_from_vectors(ground_normal, target_normal)

    aligned = (anim - origin) @ R.T + origin

    if visualize:
        visualize_ground_alignment(
            anim=anim,
            aligned=aligned,
            ref_frames=ref_frames,
            ref_points=ref_points,
            origin=origin,
            ground_normal=ground_normal,
            target_normal=target_normal,
            R=R,
        )

    return aligned, R, ground_normal


def visualize_ground_alignment(
    anim,
    aligned,
    ref_frames,
    ref_points,
    origin,
    ground_normal,
    target_normal,
    R,
):
    unique_frames = tuple(dict.fromkeys(ref_frames))

    before_clouds = [anim[f] for f in unique_frames]
    after_clouds = [aligned[f] for f in unique_frames]

    before_ref_samples = np.array(
        [anim[f, p] for f, p in zip(ref_frames, ref_points)],
        dtype=np.float64,
    )
    after_ref_samples = np.array(
        [aligned[f, p] for f, p in zip(ref_frames, ref_points)],
        dtype=np.float64,
    )

    plane_center_before = before_ref_samples.mean(axis=0)
    plane_center_after = after_ref_samples.mean(axis=0)

    all_pts = np.vstack(before_clouds + after_clouds)
    spread = np.linalg.norm(all_pts.max(axis=0) - all_pts.min(axis=0))
    plane_size = spread * 0.6 if spread > 0 else 1.0

    fig = plt.figure(figsize=(12, 6))

    ax1 = fig.add_subplot(121, projection="3d")
    for f, pts in zip(unique_frames, before_clouds):
        ax1.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=18, label=f"Frame {f}")
    ax1.scatter(
        before_ref_samples[:, 0],
        before_ref_samples[:, 1],
        before_ref_samples[:, 2],
        s=80,
        marker="x",
        label="Reference samples",
    )
    plot_wire_plane(ax1, plane_center_before, ground_normal, plane_size)
    ax1.set_title("Before rotation")
    ax1.legend()

    ax2 = fig.add_subplot(122, projection="3d")
    for f, pts in zip(unique_frames, after_clouds):
        ax2.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=18, label=f"Frame {f}")
    ax2.scatter(
        after_ref_samples[:, 0],
        after_ref_samples[:, 1],
        after_ref_samples[:, 2],
        s=80,
        marker="x",
        label="Reference samples",
    )
    plot_wire_plane(ax2, plane_center_after, target_normal, plane_size)
    ax2.set_title("After rotation")
    ax2.legend()

    mid = all_pts.mean(axis=0)
    radius = np.max(np.linalg.norm(all_pts - mid, axis=1))
    if radius <= 0:
        radius = 1.0

    for ax in (ax1, ax2):
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")

        ax.set_xlim(mid[0] - radius, mid[0] + radius)
        ax.set_ylim(mid[1] - radius, mid[1] + radius)
        ax.set_zlim(mid[2] - radius, mid[2] + radius)

    plt.tight_layout()
    plt.show()


def make_plane(center, normal, size=1.0, steps=10):
    normal = normal / np.linalg.norm(normal)

    a = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(a, normal)) > 0.9:
        a = np.array([0.0, 0.0, 1.0])

    u = np.cross(normal, a)
    u /= np.linalg.norm(u)

    v = np.cross(normal, u)
    v /= np.linalg.norm(v)

    grid = np.linspace(-size, size, steps)
    lines = []

    for g in grid:
        lines.append((center + g * u - size * v, center + g * u + size * v))
        lines.append((center - size * u + g * v, center + size * u + g * v))

    return lines


def plot_wire_plane(ax, center, normal, size):
    for p0, p1 in make_plane(center, normal, size=size):
        ax.plot(
            [p0[0], p1[0]],
            [p0[1], p1[1]],
            [p0[2], p1[2]],
            linewidth=0.6,
        )


def rotation_from_vectors(src, dst):
    src = src / np.linalg.norm(src)
    dst = dst / np.linalg.norm(dst)

    v = np.cross(src, dst)
    c = np.dot(src, dst)

    if c > 1.0 - 1e-8:
        return np.eye(3)

    if c < -1.0 + 1e-8:
        axis = np.array([1.0, 0.0, 0.0])
        if abs(src[0]) > 0.9:
            axis = np.array([0.0, 1.0, 0.0])

        axis = axis - src * np.dot(src, axis)
        axis /= np.linalg.norm(axis)

        return rotation_axis_angle(axis, np.pi)

    s = np.linalg.norm(v)

    vx = np.array([
        [0,     -v[2],  v[1]],
        [v[2],   0,   -v[0]],
        [-v[1], v[0],   0],
    ])

    return np.eye(3) + vx + vx @ vx * ((1.0 - c) / (s * s))


def rotation_axis_angle(axis, angle):
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    c = np.cos(angle)
    s = np.sin(angle)
    C = 1.0 - c

    return np.array([
        [c + x*x*C,     x*y*C - z*s, x*z*C + y*s],
        [y*x*C + z*s,   c + y*y*C,   y*z*C - x*s],
        [z*x*C - y*s,   z*y*C + x*s, c + z*z*C],
    ])

import numpy as np


def normalize_bone_forward_to_up(anim, bones, up_axis=1):
    """
    anim:  ndarray, shape (frames, points, 3)
    bones: list of point-index pairs, e.g. [(0, 1), (2, 3)]
           direction is start -> end
    up_axis: target up axis: 0=x, 1=y, 2=z

    Returns:
        normalized_anim, rotation_matrix, average_forward
    """

    anim = np.asarray(anim, dtype=np.float64)

    if anim.ndim != 3 or anim.shape[2] != 3:
        raise ValueError("anim must have shape (frames, points, 3)")

    if len(bones) < 1:
        raise ValueError("bones must contain at least one point-index pair.")

    dirs = []

    for a, b in bones:
        vecs = anim[:, b, :] - anim[:, a, :]
        lens = np.linalg.norm(vecs, axis=1)

        valid = lens > 1e-8
        if np.any(valid):
            dirs.append(vecs[valid] / lens[valid, None])

    if not dirs:
        raise ValueError("All bone vectors are degenerate.")

    dirs = np.vstack(dirs)

    average_forward = dirs.mean(axis=0)
    norm = np.linalg.norm(average_forward)

    if norm < 1e-8:
        raise ValueError("Average forward vector is degenerate.")

    average_forward /= norm

    target_up = np.zeros(3)
    target_up[up_axis] = 1.0

    if np.dot(average_forward, target_up) < 0:
        average_forward = -average_forward

    R = rotation_from_vectors(average_forward, target_up)

    origin = anim.reshape(-1, 3).mean(axis=0)
    normalized = (anim - origin) @ R.T + origin

    return normalized, R, average_forward


def rotation_from_vectors(src, dst):
    src = np.asarray(src, dtype=np.float64)
    dst = np.asarray(dst, dtype=np.float64)

    src /= np.linalg.norm(src)
    dst /= np.linalg.norm(dst)

    v = np.cross(src, dst)
    c = np.dot(src, dst)

    if c > 1.0 - 1e-8:
        return np.eye(3)

    if c < -1.0 + 1e-8:
        axis = np.array([1.0, 0.0, 0.0])
        if abs(src[0]) > 0.9:
            axis = np.array([0.0, 1.0, 0.0])

        axis = axis - src * np.dot(src, axis)
        axis /= np.linalg.norm(axis)

        return rotation_axis_angle(axis, np.pi)

    s = np.linalg.norm(v)

    vx = np.array([
        [0.0,   -v[2],  v[1]],
        [v[2],   0.0,  -v[0]],
        [-v[1],  v[0],  0.0],
    ])

    return np.eye(3) + vx + vx @ vx * ((1.0 - c) / (s * s))


def rotation_axis_angle(axis, angle):
    axis = np.asarray(axis, dtype=np.float64)
    axis /= np.linalg.norm(axis)

    x, y, z = axis
    c = np.cos(angle)
    s = np.sin(angle)
    C = 1.0 - c

    return np.array([
        [c + x*x*C,     x*y*C - z*s, x*z*C + y*s],
        [y*x*C + z*s,   c + y*y*C,   y*z*C - x*s],
        [z*x*C - y*s,   z*y*C + x*s, c + z*z*C],
    ])