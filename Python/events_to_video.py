import sys
from pathlib import Path
from tqdm import tqdm

import cv2
import numpy as np

import get_data


COLOR_MODE = "col"  # "col" or "bw"

FPS = 60
DATASET_PATH = r"E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\camera 2\events.npz"
RES = (1280, 720)
OUTNAME = "eventvideo"

OUTPUT_DIR = Path(r"E:\DVSim\Assets\.Output\Videos")

LOAD_FUNC = get_data.load_unity_dataset


if COLOR_MODE not in ("col", "bw"):
    raise ValueError('COLOR_MODE must be "col" or "bw"')

def apply_cli_args():
    global COLOR_MODE, FPS, DATASET_PATH, RES

    args = sys.argv[1:]

    if len(args) >= 1:
        COLOR_MODE = args[0]

    if len(args) >= 2:
        FPS = int(args[1])

    if len(args) >= 3:
        DATASET_PATH = args[2]

    if len(args) >= 5:
        RES = (int(args[3]), int(args[4]))

    if COLOR_MODE not in ("col", "bw"):
        raise ValueError('COLOR_MODE must be "col" or "bw"')


def infer_time_scale(t):
    duration = float(t.max() - t.min())

    if duration > 1e9:
        return 1e9
    if duration > 1e6:
        return 1e6
    if duration > 1e3:
        return 1e3

    return 1.0


def make_frame(x, y, p, lo, hi, res):
    if COLOR_MODE == "col":
        img = np.zeros((res[1], res[0], 3), dtype=np.uint8)
    else:
        img = np.full((res[1], res[0], 3), 127, dtype=np.uint8)

    xs = x[lo:hi]
    ys = y[lo:hi]
    ps = p[lo:hi]

    valid = (
        (xs >= 0) & (xs < res[0]) &
        (ys >= 0) & (ys < res[1])
    )

    xs = xs[valid].astype(np.int32)
    ys = ys[valid].astype(np.int32)
    ps = ps[valid]

    pos = ps == 1
    neg = ~pos

    # OpenCV BGR
    if COLOR_MODE == "col":
        img[ys[pos], xs[pos]] = (0, 0, 255)
        img[ys[neg], xs[neg]] = (255, 0, 0)
    else:
        img[ys[pos], xs[pos]] = (255, 255, 255)
        img[ys[neg], xs[neg]] = (0, 0, 0)

    return cv2.flip(img, 0)


def write_video():
    apply_cli_args()

    dataset_path = Path(DATASET_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base_name = f"{OUTNAME}_{COLOR_MODE}"
    out_path = OUTPUT_DIR / f"{base_name}.avi"

    if out_path.exists():
        i = 1
        while True:
            candidate = OUTPUT_DIR / f"{base_name}_{i}.avi"
            if not candidate.exists():
                out_path = candidate
                break
            i += 1

    x, y, t, p = LOAD_FUNC(str(dataset_path))
    x, y, t, p = get_data.sortdata(x, y, t, p)

    x = np.asarray(x)
    y = np.asarray(y)
    t = np.asarray(t)
    p = np.asarray(p)

    time_scale = infer_time_scale(t)
    slice_width = time_scale / FPS

    start_t = t.min()
    end_t = t.max()

    frame_count = int(np.ceil((end_t - start_t) / slice_width))

    writer = cv2.VideoWriter(
        str(out_path),
        cv2.VideoWriter_fourcc(*"FFV1"),
        FPS,
        RES
    )

    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {out_path}")

    for i in tqdm(range(frame_count)):
        center_t = start_t + i * slice_width

        lo = np.searchsorted(t, center_t - slice_width / 2)
        hi = np.searchsorted(t, center_t + slice_width / 2)

        frame = make_frame(x, y, p, lo, hi, RES)
        writer.write(frame)

    writer.release()

    print(f"Wrote video: {out_path}")
    print(f"color_mode={COLOR_MODE}")
    print(f"fps={FPS}")
    print(f"res={RES}")
    print(f"frames={frame_count}")
    print(f"slice_width={slice_width}")


if __name__ == "__main__":
    write_video()