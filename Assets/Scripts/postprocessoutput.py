import numpy as np
import sys
from pathlib import Path
from tqdm import tqdm 

print("loading file...")

outsubfolder = "Permutations"

camfilepath = sys.argv[1]
permutation = sys.argv[2].split(',')

event_dtype = np.dtype([
    ("x", np.uint16),
    ("y", np.uint16),
    ("t", np.uint64),
    ("p", np.bool),
], align=False)

with open(camfilepath, 'r') as rawfile:
    eventrows = []
    
    for row in tqdm(rawfile.readlines(), desc="reading"):
        event = [int(item) for item in row.split(',')]
        event[3] = True if event[3] == 1 else False
        event = tuple(event)

        eventrows.append(event)

    print("saving as npz...")

    data = np.array(eventrows, dtype=event_dtype)

outfilename = Path(camfilepath).stem + "_perm_" + \
    '_'.join(str(num) for num in permutation) + ".npz"
outfile = Path(camfilepath).parent / outsubfolder / outfilename 

np.savez_compressed(outfile, data)