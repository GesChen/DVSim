import json
import subprocess
import shutil
import hashlib
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm


def grayscale_to_rgb(video: np.ndarray) -> np.ndarray:
    if video.ndim != 2:
        raise ValueError("video must have shape (height, width)")
    return np.repeat(video[..., None], 3, axis=-1).astype(np.float32)


def depth_to_rgb(video, maxdepth=None):
    if maxdepth is None:
        maxdepth = np.max(video)
    scaled = video.astype(np.float32) / maxdepth
    return grayscale_to_rgb(scaled)


def hashes_to_rgb(hashes: np.ndarray) -> np.ndarray:
    if hashes.ndim != 2:
        raise ValueError("hashes must have shape (height, width)")

    values = hashes.astype(np.uint64)
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


def read_ffv1_mkv(path, fps=30.0, mode="depth"):
    path = Path(path)

    cache = path.parent / ".cache"
    cache.mkdir(exist_ok=True)

    key = hashlib.sha1(
        f"{path.resolve()}:{path.stat().st_mtime_ns}:{mode}:{fps}".encode()
    ).hexdigest()[:16]

    video_path = cache / f"{key}.mkv"

    if video_path.exists():
        print("using cached video..")
        return video_path

    frame_cache = cache / f"{key}_frames"
    frame_cache.mkdir(parents=True, exist_ok=True)

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

    total_frames = stream.get("nb_frames")
    total_frames = int(total_frames) if total_frames not in (None, "N/A") else None

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
    frame_index = 0
    maxdepth = 0

    with tqdm(total=total_frames, desc="reading", unit="frame") as bar:
        while True:
            data = process.stdout.read(frame_bytes)

            if not data:
                break

            if len(data) != frame_bytes:
                raise RuntimeError("Incomplete frame read")

            frame = np.frombuffer(data, dtype="<u2").reshape(height, width, 4)

            if mode == "depth":
                maxdepth = max(maxdepth, int(frame[..., 0].max()))

            frame.tofile(frame_cache / f"{frame_index:08d}.raw")
            frame_index += 1
            bar.update(1)

    if process.wait() != 0:
        raise RuntimeError("FFmpeg decoding failed")

    for i in tqdm(range(frame_index), desc="converting", unit="frame"):
        raw_path = frame_cache / f"{i:08d}.raw"

        frame = np.fromfile(raw_path, dtype="<u2").reshape(height, width, 4)

        if mode == "depth":
            rgb = depth_to_rgb(frame[..., 0], maxdepth)
        elif mode == "hashes":
            rgb = hashes_to_rgb(frame[..., 1])
        else:
            raise ValueError("mode must be 'depth' or 'hashes'")

        plt.imsave(frame_cache / f"{i:08d}.png", rgb)
        raw_path.unlink()

    process = subprocess.Popen(
        [
            "ffmpeg",
            "-v", "error",
            "-y",
            "-framerate", str(fps),
            "-i", str(frame_cache / "%08d.png"),
            "-c:v", "ffv1",
            "-pix_fmt", "rgb24",
            "-progress", "pipe:1",
            "-nostats",
            str(video_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    with tqdm(total=frame_index, desc="merging", unit="frame") as bar:
        last_frame = 0

        for line in process.stdout:
            if line.startswith("frame="):
                current = int(line.split("=", 1)[1])
                bar.update(current - last_frame)
                last_frame = current

    if process.wait() != 0:
        raise RuntimeError(process.stderr.read())

    shutil.rmtree(frame_cache)

    return video_path

def play_video(video) -> None:
    subprocess.Popen([
        "vlc",
        str(video),
    ])

video = read_ffv1_mkv(
    r"E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\camera 2\data.mkv",
    fps=60,
    mode="depth",
)

# video = read_ffv1_mkv(
#     r"E:\DVSim\Assets\.Output\Permutations\0\_0_0_0_0\camera 2\data.mkv",
#     fps=60,
#     mode="hashes",
# )

play_video(video)