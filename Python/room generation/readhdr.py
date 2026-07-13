import matplotlib.pyplot as plt
import numpy as np

from pathlib import Path
import numpy as np


def load_replica_hdr(path):
    path = Path(path)

    raw = np.fromfile(path, dtype=np.float16)

    if raw.size % 3 != 0:
        raise ValueError(
            f"File contains {raw.size} half-floats, which is not divisible by 3."
        )

    pixel_count = raw.size // 3
    dim = int(round(np.sqrt(pixel_count)))

    if dim * dim != pixel_count:
        raise ValueError(
            f"Texture is not square: {pixel_count} pixels cannot form a square."
        )

    return raw.reshape(dim, dim, 3)

image = load_replica_hdr(r"E:\DVSim\Python\room generation\replica\frl_apartment_0\textures\13-color-ptex.hdr").astype(np.float32)

print(image.shape)
print(image.dtype)
print(image.min(), image.max())

exposure = 1.0

display = image * exposure
display = display / (1.0 + display)  # Reinhard tone mapping
display = np.clip(display, 0.0, 1.0)

plt.imshow(display)
plt.axis("off")
plt.show()