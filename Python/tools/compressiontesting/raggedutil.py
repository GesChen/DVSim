import numpy as np

def encode_ragged(grid):
    """
    Encodes a 2D array of variable-length arrays into values/offsets/shape.
    """

    rows = len(grid)
    cols = len(grid[0]) if rows else 0

    flat = [cell for row in grid for cell in row]

    lengths = np.fromiter((len(a) for a in flat), dtype=np.int64, count=len(flat))

    offsets = np.empty(len(flat) + 1, dtype=np.int64)
    offsets[0] = 0
    np.cumsum(lengths, out=offsets[1:])

    if offsets[-1]:
        values = np.concatenate(flat)
    else:
        dtype = flat[0].dtype if flat else np.float32
        values = np.empty(0, dtype=dtype)

    return values, offsets, np.array([rows, cols], dtype=np.int32)


def decode_ragged(values, offsets, shape):
    """
    Decodes values/offsets/shape back into a 2D object ndarray.
    """

    rows, cols = map(int, shape)

    out = np.empty((rows, cols), dtype=object)

    for i in range(rows * cols):
        y, x = divmod(i, cols)
        out[y, x] = values[offsets[i]:offsets[i + 1]]

    return out


def save_ragged(path, grid, **extra):
    values, offsets, shape = encode_ragged(grid)
    np.savez_compressed(
        path,
        values=values,
        offsets=offsets,
        shape=shape,
        **extra,
    )


def load_ragged(path):
    data = np.load(path, allow_pickle=False)
    return decode_ragged(
        data["values"],
        data["offsets"],
        data["shape"],
    )