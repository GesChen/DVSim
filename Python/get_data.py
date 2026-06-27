import numpy as np
import csv
import h5py
import hdf5plugin
from pathlib import Path

def sortdata(x, y, t, p):
    print('sorting...')
    order = np.argsort(t, kind='stable')
    print('sorted')
    return x[order], y[order], t[order], p[order]

def load_occlusions_dataset():
    print('loading occlusions ds...')

    src = r'D:\Tools\Programming\Python\Event Camera\data\IROS_Dataset-2018-independent-motion\IROS_Dataset\occlusions\events.txt'

    # stupid python longdouble doesnt work its just float64
    # hacky timestamp string truncation to have precision :(
    def hackstrvalue(v):
        return np.longdouble(str(v)[8:])
    def hackdata(array): return [hackstrvalue(array[0]), array[1], array[2], array[3]]

    with open(src, 'r') as f:
        data = np.array([hackdata(r.strip().split(' ')) for r in f.readlines()], dtype=np.longdouble)

    time_start = 1519689694
    time_end = 1519689696

    time_start, time_end = hackstrvalue(time_start), hackstrvalue(time_end)

    filt = lambda t: (t > time_start) & (t < time_end)
    data = data[filt(data[:, 0])]
    x, y, t = data[:, 1], data[:, 2], data[:, 0]
    # col = np.where(data[:, 3] == 1, 'red', 'blue')
    # col = np.where(data[:, 3, None] == 1, [255, 0, 0], [0, 0, 255])

    print('loaded')
    return (x, y, t, data[:, 3])

def load_interlaken_dataset():
    print('loading interlaken dataset...')

    src = r'D:\Tools\Programming\Python\Event Camera\data\interlaken_00_c_events_left\events.h5'
    with h5py.File(src, 'r') as f:
        x = np.array(f['events']['x'])
        y = np.array(f['events']['y'])
        t = np.array(f['events']['t']) / 1e6 # scaled for micro sec scale
        p = np.array(f['events']['p'])

        # col = np.where(p == 1, 'red', 'blue')
        # col = np.where(p[:, None] == 1, [255, 0, 0], [0, 0, 255])

        print('loaded')

        return (x, y, t, p)
    
def load_simulated_dataset(src):
    print('loading simulated ds...')
    
    # src = r'D:\Tools\Programming\Python\Event Camera\data\simulated.npy'

    data = np.load(src)
    x = data[:, 0].astype(np.uint16)
    y = data[:, 1].astype(np.uint16)
    t = data[:, 2].astype(np.float64)
    p = data[:, 3].astype(np.int8)

    print('loaded')
    return x, y, t, p
    
# pass the events folder
def load_umd_dataset(src):
    print('loading umd ds...')
    src = Path(src)

    xy = np.load(src / 'events_xy.npy').astype(np.uint16)
    t = np.load(src / 'events_t.npy').astype(np.float64) / 1e6 # microsecs again
    p = np.load(src / 'events_p.npy').astype(np.int8)

    print('loaded')

    return xy[:, 0], xy[:, 1], t, p

def load_unity_raw_dataset(path):
    print('loading dataset...')

    data = np.loadtxt(path, delimiter=',')

    x = data[:, 0].astype(np.int32)
    y = data[:, 1].astype(np.int32)
    t = data[:, 2].astype(np.float64) / 1e9
    p = data[:, 3].astype(np.int8)

    print('loaded')

    return (x, y, t, p)

def load_unity_dataset(path):
    data = np.load(path)['arr_0']
    
    x = data['x'].astype(np.int32)
    y = data['y'].astype(np.int32)
    t = data['t'].astype(np.float64) / 1e9
    p = data['p'].astype(np.bool)
    p = np.where(p, 1, -1)

    print('loaded')
    return (x, y, t, p)