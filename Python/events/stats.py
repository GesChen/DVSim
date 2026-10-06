from eventstream import EventStream
from pathlib import Path

target = Path(r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\drone editor ref\events.npz')

stream = EventStream.from_unity(target)

print(len(stream.p))