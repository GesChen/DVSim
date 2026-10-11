import sys

import Imath
import matplotlib.pyplot as plt
import numpy as np
import OpenEXR


def read_exr_channel(path: str, channel: str) -> np.ndarray:
    exr = OpenEXR.InputFile(path)
    header = exr.header()

    if channel not in header["channels"]:
        raise ValueError(f"EXR has no {channel!r} channel")

    window = header["dataWindow"]
    width = window.max.x - window.min.x + 1
    height = window.max.y - window.min.y + 1

    data = exr.channel(
        channel,
        Imath.PixelType(Imath.PixelType.FLOAT),
    )
    exr.close()

    return np.frombuffer(data, dtype=np.float32).reshape(height, width)


def uint_to_rgb(ids: np.ndarray) -> np.ndarray:
    x = ids.astype(np.uint32).copy()

    x ^= x >> np.uint32(16)
    x *= np.uint32(0x7FEB352D)
    x ^= x >> np.uint32(15)
    x *= np.uint32(0x846CA68B)
    x ^= x >> np.uint32(16)

    return np.stack(
        (
            (x >> 16) & 255,
            (x >> 8) & 255,
            x & 255,
        ),
        axis=-1,
    ).astype(np.uint8)


def main(path: str) -> None:
    green = read_exr_channel(path, "G")

    # Reinterpret the float32 bits as uint32.
    ids = green.view(np.uint32)

    colors = uint_to_rgb(ids)
    colors[ids == 0] = 0

    plt.imshow(colors)
    plt.axis("off")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main(r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\camera 2\framedata\00000.exr')