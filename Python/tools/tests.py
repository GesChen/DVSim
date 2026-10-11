from eventstream import EventStream
import numpy as np

stream = EventStream.from_unity(r"E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\camera 2 noskipping ref\events.npz")

print(f'{len(stream.t)=}')

on = np.count_nonzero(stream.p == 1)
off = len(stream.p) - on

print(f'{on=} {off=} {on/off=}')
