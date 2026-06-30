# exr_to_video.py
# Configure here when running from VSCode/editor.
EDITOR_MODE = True

INPUT_DIR = r"E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\Main Camera\frames"
OUTPUT_DIR = r"E:\DVSim\Assets\.Output\Videos"
OUTPUT_NAME = "video.mp4"
FPS = 60
EXPOSURE = 1.0  # Larger = darker

import os
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"

from pathlib import Path
import argparse
import cv2
import numpy as np
from tqdm import tqdm

def render_exr_video(in_dir, out_dir, fps=30, exposure=10.0, name="out.mp4"):
    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.glob("*.exr"), key=lambda p: int(p.stem))
    if not files:
        raise FileNotFoundError("No EXR files found.")

    first = cv2.imread(str(files[0]), cv2.IMREAD_UNCHANGED)
    h, w = first.shape[:2]

    writer = cv2.VideoWriter(
        str(out_dir / name),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (w, h)
    )

    for f in tqdm(files):
        img = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)

        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img = img[:, :, :3]

        # Simple exposure adjustment
        img = np.clip(img / exposure, 0.0, 1.0)
        img = (img * 255).astype(np.uint8)

        writer.write(img)

    writer.release()


if __name__ == "__main__":
    if EDITOR_MODE:
        render_exr_video(
            INPUT_DIR,
            OUTPUT_DIR,
            FPS,
            EXPOSURE,
            OUTPUT_NAME,
        )
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("input_dir")
        parser.add_argument("output_dir")
        parser.add_argument("--fps", type=float, default=30)
        parser.add_argument("--exposure", type=float, default=10.0)
        parser.add_argument("--name", default="video.mp4")
        args = parser.parse_args()

        render_exr_video(
            args.input_dir,
            args.output_dir,
            args.fps,
            args.exposure,
            args.name,
        )