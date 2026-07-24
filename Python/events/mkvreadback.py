import json
import subprocess
from pathlib import Path

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button

def read_ffv1_mkv(path):
    print('reading..')
    path = Path(path)

    probe = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,nb_frames",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    stream = json.loads(probe.stdout)["streams"][0]
    width = int(stream["width"])
    height = int(stream["height"])

    process = subprocess.Popen(
        [
            "ffmpeg",
            "-v", "error",
            "-i", str(path),
            "-f", "rawvideo",
            "-pix_fmt", "rgba64le",
            "-",
        ],
        stdout=subprocess.PIPE,
    )

    frame_bytes = width * height * 4 * np.dtype("<u2").itemsize
    frames = []

    while True:
        data = process.stdout.read(frame_bytes)

        if not data:
            break

        if len(data) != frame_bytes:
            raise RuntimeError("Incomplete frame read")

        frame = np.frombuffer(data, dtype="<u2").reshape(height, width, 4)
        frames.append(frame.copy())

    if process.wait() != 0:
        raise RuntimeError("FFmpeg decoding failed")

    frames = np.stack(frames)

    return frames

def play_video(video: np.ndarray, fps: float = 30.0) -> None:
    """Display a (frames, height, width, channels) ndarray with scrubber and play/pause."""
    if video.ndim != 4 or video.shape[-1] not in (3, 4):
        raise ValueError("video must have shape (frames, height, width, 3 or 4)")

    frame_count = video.shape[0]
    interval = 1.0 / fps
    state = {"playing": False, "frame": 0}

    fig, ax = plt.subplots()
    plt.subplots_adjust(bottom=0.22)

    image = ax.imshow(video[0])
    ax.axis("off")

    slider_ax = fig.add_axes((0.15, 0.08, 0.7, 0.04))
    slider = Slider(
        slider_ax,
        "Frame",
        0,
        frame_count - 1,
        valinit=0,
        valstep=1,
    )

    button_ax = fig.add_axes((0.43, 0.015, 0.14, 0.045))
    button = Button(button_ax, "Play")

    def show_frame(index: int) -> None:
        state["frame"] = index
        image.set_data(video[index])
        ax.set_title(f"Frame {index}/{frame_count - 1}")
        fig.canvas.draw_idle()

    def on_slider(value) -> None:
        show_frame(int(value))

    def toggle_play(_event) -> None:
        state["playing"] = not state["playing"]
        button.label.set_text("Pause" if state["playing"] else "Play")

    def update(_frame) -> None:
        if not state["playing"]:
            return

        next_frame = (state["frame"] + 1) % frame_count
        slider.set_val(next_frame)

    slider.on_changed(on_slider)
    button.on_clicked(toggle_play)

    animation = fig.canvas.new_timer(interval=int(interval * 1000))
    animation.add_callback(update, None)
    animation.start()

    show_frame(0)
    plt.show()

def grayscale_to_rgb(video: np.ndarray) -> np.ndarray:
    """Convert (frames, height, width) grayscale video to RGB."""
    print('converting gray to rgb.. ')
    if video.ndim != 3:
        raise ValueError("video must have shape (frames, height, width)")

    return np.repeat(video[..., None], 3, axis=-1)

def hashes_to_rgb(hashes: np.ndarray) -> np.ndarray:
    """
    Convert integer hashes shaped (frames, height, width) to deterministic RGB.

    Equal hash values always receive equal colors. Hash value 0 becomes black.
    """
    print('converting ids to rgb.. ')
    if hashes.ndim != 3:
        raise ValueError("hashes must have shape (frames, height, width)")

    values = hashes.astype(np.uint64)

    # Deterministic integer mixing.
    mixed = values.copy()
    mixed ^= mixed >> np.uint64(30)
    mixed *= np.uint64(0xBF58476D1CE4E5B9)
    mixed ^= mixed >> np.uint64(27)
    mixed *= np.uint64(0x94D049BB133111EB)
    mixed ^= mixed >> np.uint64(31)

    rgb = np.empty((*hashes.shape, 3), dtype=np.uint8)
    rgb[..., 0] = mixed & 0xFF
    rgb[..., 1] = (mixed >> np.uint64(8)) & 0xFF
    rgb[..., 2] = (mixed >> np.uint64(16)) & 0xFF

    rgb[values == 0] = 0
    return rgb

data = read_ffv1_mkv(r"E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\camera 2\data.mkv")

rgb = grayscale_to_rgb(data[..., 0])
rgb = hashes_to_rgb(data[..., 1])

play_video(rgb, 60)