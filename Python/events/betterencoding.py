from eventstream import EventStream
from raggedutil import *
import numpy as np
from tqdm import tqdm

data = EventStream.from_unity_raw(r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0_0\drone\events.npz')
# data = EventStream.from_unity_raw(r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0_0\camera 2\events.npz')

res = (1280, 720)

# put events into the grid
# grid = [[[] for x in range(res[0])] for y in range(res[1])]
grid = np.empty(res[::-1], dtype=object)
grid.fill(None)
for y in range(res[1]):
    for x in range(res[0]):
        grid[y, x] = []

for i, (x, y) in tqdm(enumerate(zip(data.x, data.y)), total=len(data.t)):
    grid[y, x].append(i)

# compute deltas + polarity combined
for y in range(res[1]):
    for x in range(res[0]):
        events = grid[y, x]

        last_t = np.uint64(0)
        for i, e in enumerate(events):
            t = data.t[e]
            delta = t - last_t
            # last_t = t # experiment- remove this to use the raw times not deltas
            polarity = 1 if data.p[e] else -1
            
            grid[y, x][i] = polarity * delta

save_ragged(r'./output/test.npz', grid)