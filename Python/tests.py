import get_data
import numpy as np

(x, y, t, p) = get_data.load_unity_dataset(r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\Main Camera.npz')
(x, y, t, p) =  get_data.sortdata(x, y, t, p)
# t*= 1e9

mask = (x == 518) & (y == 347)
t = t[mask]

diff = np.empty_like(t)
diff[0] = 0            # or arr[0], or np.nan for float arrays
diff[1:] = t[1:] - t[:-1]

import matplotlib.pyplot as plt
# diff= np.random.normal(170, 10, 250)
plt.hist(diff, bins=1000, log=True)
plt.xlabel("Difference")
plt.ylabel("Count")
plt.show()