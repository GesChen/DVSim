import json
import subprocess
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle
from matplotlib.widgets import Button, Slider


# Edit these values and run this file from the IDE.
VIDEO_PATH = Path(r"E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\camera 2\color.mp4")
BBOX_PATH = Path(r"E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\camera 2\bboxes.json")

TIMESCALE = 1_000_000_000
VIDEO_START_TIME = 0              # Video frame 0 timestamp, in TIMESCALE units.

# Used only for .mkv data backgrounds: "id", "depth", or "rgb".
DATA_MKV_VIEW = "id"
DATA_ID_CHANNEL = 1
DATA_DEPTH_CHANNEL = 0
DATA_RGB_CHANNELS = (0, 1, 2)

BBOX_LINE_WIDTH = 2.0
TEXT_OFFSET_PX = 6
DIST_DECIMALS = 3


class VideoSource:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.suffix = self.path.suffix.lower()

        if self.suffix == ".mkv":
            self.frames, self.fps = read_data_mkv(self.path)
            self.frame_count = len(self.frames)
            self.height, self.width = self.frames.shape[1:3]
            self.capture = None
        else:
            self.capture = cv2.VideoCapture(str(self.path))
            if not self.capture.isOpened():
                raise RuntimeError(f"Could not open video: {self.path}")

            self.fps = float(self.capture.get(cv2.CAP_PROP_FPS))
            self.frame_count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.frames = None

        if self.fps <= 0:
            raise RuntimeError("Video FPS is missing or invalid")
        if self.frame_count <= 0:
            raise RuntimeError("Video contains no frames")

    def get_frame(self, index: int) -> np.ndarray:
        index = int(np.clip(index, 0, self.frame_count - 1))

        if self.frames is not None:
            return data_frame_to_rgb(self.frames[index])

        self.capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = self.capture.read()
        if not ok:
            raise RuntimeError(f"Could not decode video frame {index}")
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()


def probe_video(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)["streams"][0]


def fraction_to_float(value: str) -> float:
    numerator, denominator = value.split("/")
    denominator_value = float(denominator)
    return float(numerator) / denominator_value if denominator_value else 0.0


def read_data_mkv(path: Path) -> tuple[np.ndarray, float]:
    """Decode a 16-bit FFV1 MKV as (frames, height, width, 4) uint16."""
    stream = probe_video(path)
    width = int(stream["width"])
    height = int(stream["height"])
    fps = fraction_to_float(stream.get("avg_frame_rate", "0/1"))
    if fps <= 0:
        fps = fraction_to_float(stream.get("r_frame_rate", "0/1"))

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
        raw = process.stdout.read(frame_bytes)
        if not raw:
            break
        if len(raw) != frame_bytes:
            process.kill()
            raise RuntimeError("Incomplete MKV frame read")
        frames.append(
            np.frombuffer(raw, dtype="<u2")
            .reshape(height, width, 4)
            .copy()
        )

    if process.wait() != 0:
        raise RuntimeError("FFmpeg MKV decoding failed")
    if not frames:
        raise RuntimeError("MKV contains no decoded frames")

    return np.stack(frames), fps


def mix_hash(value: int) -> int:
    value = int(value) & 0xFFFFFFFFFFFFFFFF
    value ^= value >> 30
    value = (value * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    value ^= value >> 27
    value = (value * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    value ^= value >> 31
    return value


def hash_color_u8(value: int) -> tuple[int, int, int]:
    mixed = mix_hash(value)
    rgb = np.array(
        [mixed & 0xFF, (mixed >> 8) & 0xFF, (mixed >> 16) & 0xFF],
        dtype=np.float32,
    )

    # Raise dark colors so overlays and text remain visible.
    rgb = 72.0 + rgb * (183.0 / 255.0)
    return tuple(rgb.astype(np.uint8))


def hash_color_float(value: int) -> tuple[float, float, float]:
    return tuple(channel / 255.0 for channel in hash_color_u8(value))


def hashes_to_rgb(hashes: np.ndarray) -> np.ndarray:
    values = hashes.astype(np.uint64)
    mixed = values.copy()
    mixed ^= mixed >> np.uint64(30)
    mixed *= np.uint64(0xBF58476D1CE4E5B9)
    mixed ^= mixed >> np.uint64(27)
    mixed *= np.uint64(0x94D049BB133111EB)
    mixed ^= mixed >> np.uint64(31)

    rgb = np.empty((*hashes.shape, 3), dtype=np.uint8)
    rgb[..., 0] = mixed & np.uint64(0xFF)
    rgb[..., 1] = (mixed >> np.uint64(8)) & np.uint64(0xFF)
    rgb[..., 2] = (mixed >> np.uint64(16)) & np.uint64(0xFF)
    rgb[values == 0] = 0
    return rgb


def data_frame_to_rgb(frame: np.ndarray) -> np.ndarray:
    if DATA_MKV_VIEW == "id":
        return hashes_to_rgb(frame[..., DATA_ID_CHANNEL])

    if DATA_MKV_VIEW == "depth":
        depth = frame[..., DATA_DEPTH_CHANNEL].astype(np.float32)
        finite = np.isfinite(depth)
        if not finite.any():
            scaled = np.zeros_like(depth, dtype=np.uint8)
        else:
            valid = depth[finite]
            low, high = np.percentile(valid, (1.0, 99.0))
            if high <= low:
                high = low + 1.0
            scaled = np.clip((depth - low) / (high - low), 0.0, 1.0)
            scaled = (scaled * 255.0).astype(np.uint8)
        return np.repeat(scaled[..., None], 3, axis=-1)

    if DATA_MKV_VIEW == "rgb":
        rgb16 = frame[..., list(DATA_RGB_CHANNELS)]
        return (rgb16 >> 8).astype(np.uint8)

    raise ValueError('DATA_MKV_VIEW must be "id", "depth", or "rgb"')


def load_bboxes(path: Path) -> tuple[list[dict], np.ndarray]:
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not records:
        raise ValueError("Bounding-box file is empty")

    records.sort(key=lambda item: int(item["time"]))
    times = np.asarray([int(item["time"]) for item in records], dtype=np.int64)
    return records, times


def closest_bbox_index(times: np.ndarray, target_time: int) -> int:
    right = int(np.searchsorted(times, target_time, side="left"))
    if right <= 0:
        return 0
    if right >= len(times):
        return len(times) - 1

    left = right - 1
    if target_time - times[left] <= times[right] - target_time:
        return left
    return right


def frame_time(frame_index: int, fps: float) -> int:
    return VIDEO_START_TIME + round(frame_index * TIMESCALE / fps)


def choose_text_position(
    min_x: float,
    max_x: float,
    min_y: float,
    image_width: int,
) -> tuple[float, float, str]:
    if max_x + 210 < image_width:
        return max_x + TEXT_OFFSET_PX, min_y, "left"
    return min_x - TEXT_OFFSET_PX, min_y, "right"


def run_visualizer() -> None:
    video = VideoSource(VIDEO_PATH)
    bbox_records, bbox_times = load_bboxes(BBOX_PATH)

    state = {"frame": 0, "playing": False, "artists": []}

    fig, ax = plt.subplots()
    plt.subplots_adjust(bottom=0.20)
    image_artist = ax.imshow(video.get_frame(0), interpolation="nearest")
    ax.set_xlim(0, video.width)
    ax.set_ylim(video.height, 0)
    ax.axis("off")

    slider_ax = fig.add_axes((0.15, 0.075, 0.70, 0.04))
    slider = Slider(
        slider_ax,
        "Frame",
        0,
        video.frame_count - 1,
        valinit=0,
        valstep=1,
    )

    button_ax = fig.add_axes((0.43, 0.015, 0.14, 0.045))
    button = Button(button_ax, "Play")

    def clear_bbox_artists() -> None:
        for artist in state["artists"]:
            artist.remove()
        state["artists"].clear()

    def draw_bboxes(record: dict) -> None:
        clear_bbox_artists()

        for bbox in record["bboxes"]:
            bbox_id = int(bbox["id"])
            color = hash_color_float(bbox_id)
            min_x, min_y = map(float, bbox["min"])
            max_x, max_y = map(float, bbox["max"])

            min_y = video.height - min_y
            max_y = video.height - max_y

            width = max_x - min_x
            height = max_y - min_y

            rectangle = Rectangle(
                (min_x, min_y),
                width,
                height,
                fill=False,
                edgecolor=color,
                linewidth=BBOX_LINE_WIDTH,
                linestyle="-" if bbox["visible"] else "--",
                clip_on=True,
            )
            ax.add_patch(rectangle)
            state["artists"].append(rectangle)

            text_x, text_y, alignment = choose_text_position(
                min_x, max_x, min_y, video.width
            )
            text = (
                f'{bbox["label"]}\n'
                f'id: {bbox_id}\n'
                f'dist: {float(bbox["dist"]):.{DIST_DECIMALS}f}\n'
                f'visible: {bool(bbox["visible"])}'
            )
            text_artist = ax.text(
                text_x,
                text_y,
                text,
                color=color,
                fontsize=8,
                ha=alignment,
                va="top",
                clip_on=True,
                bbox={"facecolor": "black", "alpha": 0.55, "edgecolor": "none", "pad": 2},
            )
            state["artists"].append(text_artist)

    def show_frame(index: int) -> None:
        index = int(np.clip(index, 0, video.frame_count - 1))
        state["frame"] = index
        image_artist.set_data(video.get_frame(index))

        video_time = frame_time(index, video.fps)
        bbox_index = closest_bbox_index(bbox_times, video_time)
        bbox_record = bbox_records[bbox_index]
        draw_bboxes(bbox_record)

        delta = int(bbox_record["time"]) - video_time
        ax.set_title(
            f"Frame {index}/{video.frame_count - 1} | "
            f"video t={video_time} | bbox t={bbox_record['time']} | delta={delta}"
        )
        fig.canvas.draw_idle()

    def on_slider(value: float) -> None:
        show_frame(int(value))

    def toggle_play(_event) -> None:
        state["playing"] = not state["playing"]
        button.label.set_text("Pause" if state["playing"] else "Play")

    def advance() -> None:
        if not state["playing"]:
            return
        slider.set_val((state["frame"] + 1) % video.frame_count)

    def on_close(_event) -> None:
        video.close()

    slider.on_changed(on_slider)
    button.on_clicked(toggle_play)
    fig.canvas.mpl_connect("close_event", on_close)

    timer = fig.canvas.new_timer(interval=max(1, round(1000.0 / video.fps)))
    timer.add_callback(advance)
    timer.start()

    show_frame(0)
    plt.show()


if __name__ == "__main__":
    run_visualizer()