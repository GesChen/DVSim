import numpy as np
import cv2
from tqdm import tqdm
from pathlib import Path
from PIL import Image
import re

contrast_threshold = .25 # realistic is .1-.15
vid = r'D:\Tools\Programming\Python\Event Camera\data\2024-09-19_15-45-04-back.mp4'

imageseq = r'D:\Tools\Programming\Python\Event Camera\data\from umd\events\sequence_haowen1_SIDE_DYNAMIC_LIGHT_bottle\proc\flir\frame'
seqfps = 30

# dont add file format, script will handle itself 
out = r'D:\Tools\Programming\Python\Event Camera\data\simulated_umdbottle'

eps = 1e-5

denoise = True

event_dtype = np.dtype([
    ('x', np.uint16),
    ('y', np.uint16),
    ('t', np.float64),
    ('p', np.int8)
])

# (frames, height, width, channels)
def load_video():
    print('loading video...')

    cap = cv2.VideoCapture(vid)

    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # frame shape: (height, width, channels)
        frames.append(frame)

    fps = cap.get(cv2.CAP_PROP_FPS)

    cap.release()
    video_array = np.stack(frames)

    print('loaded')
    return video_array, fps


def natural_key(path):
    """
    Sorts filenames numerically:
    frame1.png, frame2.png, ..., frame10.png
    """
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split(r"(\d+)", path.name)
    ]

def load_image_sequence(directory, extensions=(".png", ".jpg", ".jpeg", ".tif", ".tiff")):
    directory = Path(directory)

    files = sorted(
        [f for f in directory.iterdir() if f.suffix.lower() in extensions],
        key=natural_key
    )

    images = [np.array(Image.open(f)) for f in files]

    # Shape: (num_frames, height, width, channels)
    return np.stack(images), seqfps

def denoise_image(image):
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    denoised_bgr = cv2.fastNlMeansDenoisingColored(
        bgr,
        None,
        h=10,                 # luminance strength
        hColor=10,            # chroma strength
        templateWindowSize=7,
        searchWindowSize=21,
    )

    denoised_rgb = cv2.cvtColor(denoised_bgr, cv2.COLOR_BGR2RGB)
    return denoised_rgb

def denoise_sequence(frames):
    denoised_frames = np.stack(
        [denoise_image(frame) for frame in tqdm(frames, desc='denoising')],
        axis=0,
    )
    return denoised_frames

def log_frame(frame): # frame shape (height, width, channels)
    I = frame[:, :, 0] * .229 + frame[:, :, 1] * .587 + frame[:, :, 2] * .114
    I = np.log(I + eps) # add epsilon
    return I

def simulate():
    # video, fps = load_video()
    frames, fps = load_image_sequence(imageseq)
    if denoise: frames = denoise_sequence(frames)

    vs = frames.shape
    height = vs[1]
    width = vs[2]

    with open(out + '.bin', 'wb') as file:
        lastlog = np.zeros((height, width), dtype=np.float64)
        for f, frame in tqdm(enumerate(frames), total=vs[0], desc='simulating'):
            # compute
            I = log_frame(frame)
            
            diff = I - lastlog

            n_on  = np.floor(diff / contrast_threshold).astype(int)
            n_off = np.floor(-diff / contrast_threshold).astype(int)

            on_mask  = n_on > 0
            off_mask = n_off > 0

            lastlog[on_mask] += n_on[on_mask] * contrast_threshold
            lastlog[off_mask] -= n_off[off_mask] * contrast_threshold

            if f == 0: continue # skip frame 0
            
            # get events
            events = [] # event values (x, y, t, p)

            t = f / fps
            for x in range(width):
                for y in range(height):
                    for _ in range(n_on[y, x]):
                        events.append((x, y, t, 1))
                    for _ in range(n_off[y, x]):
                        events.append((x, y, t, -1))
            
            # write to the bin
            eventsarr = np.array(events, dtype=event_dtype)
            eventsarr.tofile(file)
    
    # convert to npy
    print('finalizing into npy..')
    events = np.fromfile(out+'.bin', dtype=event_dtype)
    events_nx4 = np.column_stack([
        events["x"],
        events["y"],
        events["t"],
        events["p"],
    ])
    np.save(out+'.npy', events_nx4)

simulate()