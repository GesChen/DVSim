## POST PROCESSOR FOR ONE DVS SENSOR-
# each sensor calls this for itself 

import shutil
import numpy as np
import sys
from pathlib import Path
from tqdm import tqdm 
from send2trash import send2trash
import json
import OpenEXR
import Imath
import numpy as np
import re
import cv2
import subprocess

outsubfolder = "Permutations"
idremapfile = 'allids.json'
colorvidout = 'color.mp4'
datavidout = 'data.mkv'
depthscale = 1000

event_dtype = np.dtype([
	("x", np.uint16),
	("y", np.uint16),
	("t", np.uint64),
	("p", bool),
], align=False)

def processbin(meta, path):
	camfilepath = meta['outfilepath']

	print("reading bin...")

	raw_event_dtype = np.dtype([
		("x", "<i4"),
		("y", "<i4"),
		("t", "<u8"),
		("p", "u1"),
	])

	data = np.fromfile(camfilepath, dtype=raw_event_dtype)

	data = data.astype(event_dtype, copy=False)
	data["p"] = data["p"].astype(bool)

	print("saving as npz...")

	outfile = path / "events.npz"
	np.savez_compressed(outfile, data)
	
	# TODO: frame rescaling based on a value from config json
	# dont need yet     

	print("done")

def load_exr(path: Path) -> np.ndarray:
	exr = OpenEXR.InputFile(str(path))
	dw = exr.header()["dataWindow"]

	w = dw.max.x - dw.min.x + 1
	h = dw.max.y - dw.min.y + 1

	pt = Imath.PixelType(Imath.PixelType.FLOAT)

	channels = []
	for c in ("R", "G", "B", "A"):
		if c in exr.header()["channels"]:
			ch = np.frombuffer(exr.channel(c, pt), dtype=np.float32)
			channels.append(ch.reshape(h, w))

	return np.stack(channels, axis=-1)

def loadexrfolder(path, channel=None) -> np.ndarray:
	print(f'loading exrs in \'{path.parts[-1]}\' {f"channel {channel}" if channel is not None else ''}')

	files = sorted(
		path.glob("*.exr"),
		key=lambda p: int(re.search(r"\d+", p.stem).group())
	)

	if not files:
		return None

	frames = []

	for f in tqdm(files):
		img = load_exr(f)

		if channel is not None:
			img = img[..., channel]

		frames.append(img)

	return np.stack(frames, axis=0)

def find_exposure(exrs, percentile=99.5, target=0.9) -> float:
	lum = (
		0.2126 * exrs[..., 0] +
		0.7152 * exrs[..., 1] +
		0.0722 * exrs[..., 2] 
	)

	scene_level = np.percentile(lum, percentile)
	return scene_level / target

def processcolorframes(meta, path):
	print('calculating exposure')
	exrvideo = loadexrfolder(path / "frames")
	if exrvideo is None:
		print('no color frames in folder')
		return

	exposure = find_exposure(exrvideo)

	h, w = exrvideo.shape[1:3]

	writer = cv2.VideoWriter(
		str(path / colorvidout),
		cv2.VideoWriter_fourcc(*"mp4v"),
		meta['config']['frameCapFPS'],
		(w, h)
	)

	print('processing color frames...')
	for img in tqdm(exrvideo):
		img = img[:, :, :3] # has alpha channel

		img = np.clip(img / exposure, 0.0, 1.0)
		img = (img * 255).astype(np.uint8)

		writer.write(img)

	writer.release()

	if meta['config']['deleteFrameCapsAfterPostProcess']:
		shutil.rmtree(str(path / 'frames'))

def resolveIDremapping(meta, path : Path): 
	remappath = path.parent.parent.parent / idremapfile
	uniqueids = meta['uniqueids']

	if remappath.exists():
		with remappath.open('r') as f:
			existing = json.load(f)
	else: existing = []

	for id in uniqueids:
		if id not in existing:
			existing.append(id)

	with remappath.open('w') as w:
		json.dump(existing, w)

	return existing
	
def processdataframes(meta, path):
	print('processing data frames...')

	remap = resolveIDremapping(meta, path)

	files = sorted(
		(path / 'data').glob("*.exr"),
		key=lambda p: int(p.stem),
	)

	first = load_exr(files[0])
	h, w = first.shape[:2]
	fps = meta['config']['frameCapFPS']

	ffmpeg = subprocess.Popen(
		[
			"ffmpeg", "-y",
			"-f", "rawvideo",
			"-pixel_format", "rgba64le",
			"-video_size", f"{w}x{h}",
			"-framerate", str(fps),
			"-i", "-",
			"-c:v", "ffv1",
			"-level", "3",
			"-coder", "1",
			"-context", "1",
			"-slicecrc", "1",
			str(path / datavidout),
		],
		stdin=subprocess.PIPE,
	)

	
	def convert_r(channel):
		return np.clip(channel * depthscale, 0, 65535).astype(np.uint16)

	def convert_g(channel):
		lookup = {s: i for i, s in enumerate(remap)}
		channel = channel.view(np.uint32)
		return np.vectorize(lambda x: lookup[str(x)], otypes=[np.uint16])(channel)

	def convert_b(channel):
		return np.zeros_like(channel, dtype=np.uint16)

	def convert_a(channel):
		return np.zeros_like(channel, dtype=np.uint16)

	try:
		for framepath in files:
			exr = load_exr(framepath)

			frame = np.empty((h, w, 4), dtype=np.uint16)
			frame[..., 0] = convert_r(exr[..., 0])
			frame[..., 1] = convert_g(exr[..., 1])
			frame[..., 2] = convert_b(exr[..., 2])
			frame[..., 3] = convert_a(exr[..., 3])

			ffmpeg.stdin.write(frame.astype("<u2", copy=False).tobytes())
	finally:
		ffmpeg.stdin.close()
		if ffmpeg.wait() != 0:
			raise RuntimeError("FFmpeg encoding failed")

	if meta['config']['deleteFrameCapsAfterPostProcess']:
		shutil.rmtree(str(path / 'data'))

if __name__ == "__main__":
	jsonpath = sys.argv[1]

	with open(jsonpath, "r") as f:
		meta = json.load(f)

	camfilepath = meta['outfilepath']
	camname = Path(camfilepath).stem

	permutation = meta['permutation']
	permfoldername = '_'.join(str(num) for num in permutation)

	path = Path(camfilepath).parent / outsubfolder / permfoldername / camname
	path.mkdir(parents=True, exist_ok=True)

	processbin(meta, path)

	processcolorframes(meta, path)

	processdataframes(meta, path)