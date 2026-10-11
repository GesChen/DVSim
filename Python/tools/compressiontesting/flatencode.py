from eventstream import EventStream
import numpy as np

data = EventStream.from_unity_raw(
    r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0_0\drone\events.npz'
)

width, height = 1280, 720
pixel_count = width * height

# Flatten (x, y) into one pixel index.
pixel = data.y.astype(np.int64) * width + data.x.astype(np.int64)

# Group events by pixel while preserving event order within each pixel.
order = np.argsort(pixel, kind="stable")
sorted_pixel = pixel[order]
sorted_t = data.t[order].astype(np.uint64, copy=False)
sorted_p = data.p[order]

# CSR-style offsets.
counts = np.bincount(sorted_pixel, minlength=pixel_count)
offsets = np.empty(pixel_count + 1, dtype=np.uint64)
offsets[0] = 0
np.cumsum(counts, out=offsets[1:])

# Compute timestamp deltas independently within each pixel.
values = sorted_t.copy()

starts = offsets[:-1]
nonempty = counts != 0
starts = starts[nonempty]

# First event in each pixel is relative to zero.
first_times = values[starts].copy()

# Global diff, then repair boundaries between pixels.
values[1:] -= sorted_t[:-1]
values[starts] = first_times

# Combine polarity with time/delta.
# Requires a signed type because negative polarity is represented by negatives.
values = values.astype(np.int64)
values *= np.where(sorted_p, 1, -1)

np.savez_compressed(
    r'./output/test.npz',
    values=values,
    offsets=offsets,
    shape=np.array([height, width], dtype=np.uint32),
)