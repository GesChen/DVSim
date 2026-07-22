import sys

import Imath
import matplotlib.pyplot as plt
import numpy as np
import OpenEXR

file = r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\camera 2\framedata\00000.exr'

exr = OpenEXR.InputFile(file)

dw = exr.header()["dataWindow"]
w = dw.max.x - dw.min.x + 1
h = dw.max.y - dw.min.y + 1

depth = np.frombuffer(
    exr.channel("R", Imath.PixelType(Imath.PixelType.FLOAT)),
    dtype=np.float32,
).reshape(h, w).copy()

depth /= depth.max()

plt.imshow(depth, cmap="gray", vmin=0, vmax=1)
plt.axis("off")
plt.show()