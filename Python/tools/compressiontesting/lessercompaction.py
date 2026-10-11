from eventstream import EventStream
import numpy as np

data = EventStream.from_unity_raw(r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0_0\drone\events.npz')
# data = EventStream.from_unity_raw(r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0_0\camera 2\events.npz')

res = (1280, 720)

compactPos = data.x + res[0] * data.y
compactT = np.where(data.p, data.t, -data.t)

np.savez_compressed('./output/test.npz', xy=compactPos, tp=compactT)