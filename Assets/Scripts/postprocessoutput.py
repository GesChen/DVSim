import numpy as np
import sys
from pathlib import Path
from tqdm import tqdm 
from send2trash import send2trash

outsubfolder = "Permutations"
processing_chunk_size = 10000000

event_dtype = np.dtype([
    ("x", np.uint16),
    ("y", np.uint16),
    ("t", np.uint64),
    ("p", np.bool),
], align=False)

def process(camfilepath, permutation, disable_tqdm):
    basename = Path(camfilepath).stem
    permfoldername = '_'.join(str(num) for num in permutation)

    path = Path(camfilepath).parent / outsubfolder / permfoldername
    path.mkdir(parents=True, exist_ok=True)

    with open(camfilepath, 'r') as rawfile:
        print('reading lines...')
        lines = rawfile.readlines()

    bin = path / (basename + '.bin')
    with open(bin, 'wb') as bfile:
        print("loading file...")
        pbar = tqdm(total=len(lines), disable=disable_tqdm)

        i = 0
        while i < len(lines): 
            eventrows = []
            for c in tqdm(range(processing_chunk_size), leave=False, disable=disable_tqdm):
                row = lines[i]
                event = [int(item) for item in row.split(',')]
                event[3] = True if event[3] == 1 else False
                event = tuple(event)

                eventrows.append(event)

                i += 1
                if i >= len(lines): break
            pbar.update(processing_chunk_size)

            eventsarr = np.array(eventrows, dtype=event_dtype)
            eventsarr.tofile(bfile)

    print("saving as npz...")

    data = np.fromfile(bin, dtype=event_dtype)
    outfile = path / (basename + ".npz" )
    np.savez_compressed(outfile, data)

    send2trash(bin)

    print("done")

if __name__ == "__main__":
    camfilepath = sys.argv[1]
    permutation = sys.argv[2].split(',')

    process(camfilepath, permutation, False)