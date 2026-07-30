from eventstream import EventStream
import numpy as np
import zstandard as zstd

# data = EventStream.from_unity_raw(r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0_0\drone\events.npz')
data = EventStream.from_unity_raw(r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0_0\camera 2\events.npz')

with open("./output/array.npy.zst", "wb") as f:
    cctx = zstd.ZstdCompressor(level=3, threads=-1)
    with cctx.stream_writer(f) as compressor:
        np.save(compressor, data)
