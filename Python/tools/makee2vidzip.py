from eventstream import EventStream

stream = EventStream.from_unity(r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\camera 2\events.npz')

from pathlib import Path
import zipfile
from tqdm import tqdm

out = Path(__file__).parent / "stream.zip"

chunk_size = 250_000
n = len(stream.t)

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
    with z.open("stream.txt", "w", force_zip64=True) as f:
        for start in tqdm(range(0, n, chunk_size), total=(n + chunk_size - 1) // chunk_size):
            end = min(start + chunk_size, n)

            buf = "".join(
                f"{t:.17g} {int(x)} {int(y)} {int(p)}\n"
                for t, x, y, p in zip(
                    stream.t[start:end],
                    stream.x[start:end],
                    stream.y[start:end],
                    stream.p[start:end],
                )
            )

            f.write(buf.encode())