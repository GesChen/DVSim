import numpy as np

width = 1280
height = 720

frames = np.fromfile(r"E:\DVSim\Assets\.Output\drone_eframes.bin", dtype=np.float32)
frames = frames.reshape((-1, height, width))

np.savez_compressed('./output/frames.npz', frames)