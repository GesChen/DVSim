## POST PROCESSOR FOR ONE DVS SENSOR-
# each sensor calls this for itself 

import shutil
import numpy as np
import sys
from pathlib import Path
from tqdm import tqdm 
import json
import OpenEXR
import Imath
import numpy as np
import re
import cv2
import subprocess
import datetime

# preload 
meta = {}
config = {}
path = Path()

quiet_ffmpeg = True

event_dtype = np.dtype([
	("x", np.uint16),
	("y", np.uint16),
	("t", np.uint64),
	("p", bool),
], align=False)

class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()

    def isatty(self):
        return any(getattr(s, "isatty", lambda: False)() for s in self.streams)

def setupStdout():
	log = open(Path(__file__).with_suffix(".log"), "a", encoding="utf-8")
	log.write("\n" + "=" * 20
		    + "Run:" + datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
			+ '=' * 20 + "\n")
	log.flush()

	sys.stdout = Tee(sys.__stdout__, log)
	sys.stderr = Tee(sys.__stderr__, log)

def processbin():
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

	outfile = path / config["eventsOut"]
	np.savez_compressed(outfile, data)
	
	# TODO: frame rescaling based on a value from config json
	# dont need yet     

	print("done")

def processfasterbin():
	camfilepath = meta['outfilepath']

	print("reading faster bin...")

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

	outfile = path / config["eventsOut"]
	np.savez_compressed(outfile, data)
	
	# TODO: frame rescaling based on a value from config json
	# dont need yet     

	print("done")

def load_exr(path) -> np.ndarray:
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

def load_byteframe(path):
	width, height = config['resolution']['x'], config['resolution']['y']
	pixels = np.fromfile(path, dtype=np.float32)

	channels = pixels.size // (height * width)
	pixels = pixels.reshape(height, width, channels)
	pixels = np.flipud(pixels)
	return pixels;

def load_fc(path): return (load_exr if config['useEXR'] else load_byteframe)(path)

def loadexrfolder(path: Path, channel=None) -> np.ndarray:
	print(f'loading exrs in \'{path.parts[-1]}\' {f"channel {channel}" if channel is not None else ''}')

	files = sorted(
		path.glob("*.exr"),
		key=lambda p: int(re.search(r"\d+", p.stem).group())
	)

	if not files:
		return None

	# preallocate one ndarray instead of list temporary -> stack = double allocate
	first = load_exr(files[0])

	if channel is not None:
		first = first[..., channel]

	frames = np.empty((len(files), *first.shape), dtype=first.dtype)
	frames[0] = first

	for i, f in enumerate(tqdm(files[1:]), start=1):
		img = load_exr(f)

		if channel is not None:
			img = img[..., channel]

		frames[i] = img

	return frames

def getexrfiles(path: Path) -> list[Path]:
	return sorted(
		path.glob("*.exr"),
		key=lambda p: int(re.search(r"\d+", p.stem).group())
	)

def getbytesfiles(path):
	return sorted(
		path.glob("*.bytes"),
		key=lambda p: int(re.search(r"\d+", p.stem).group())
	)

def getFCfiles(path):
	exr = config['useEXR']
	if exr: return getexrfiles(path)
	else: return getbytesfiles(path)

# never write code ever again. 
def getFCfileswtf(path): return (getexrfiles if config['useEXR'] else getbytesfiles)(path)

def calculate_exposure(
	files: list[Path],
	n_samples=16,
	percentile=99.5,
	target=0.9
) -> float:
	print(f'finding exposure from {min(n_samples, len(files))} representative frames')

	# Evenly distribute samples across the entire sequence.
	indices = np.linspace(
		0,
		len(files) - 1,
		min(n_samples, len(files)),
		dtype=int
	)

	luminance_samples = []

	for i in tqdm(indices, desc='exposure samples'):
		img = load_fc(files[i])[..., :3]

		lum = (
			0.2126 * img[..., 0] +
			0.7152 * img[..., 1] +
			0.0722 * img[..., 2]
		)

		luminance_samples.append(lum.ravel())

	scene_level = np.percentile(
		np.concatenate(luminance_samples),
		percentile
	)

	return max(scene_level / target, np.finfo(np.float32).eps)

def linear_to_srgb(img: np.ndarray) -> np.ndarray:
    """Convert linear RGB in [0,1] to sRGB in [0,1]."""
    img = np.clip(img, 0.0, 1.0)

    return np.where(
        img <= 0.0031308,
        img * 12.92,
        1.055 * np.power(img, 1.0 / 2.4) - 0.055
    )

def processcolorframes():
	frame_path = path / config["frameCapSubFolder"]
	files = getFCfileswtf(frame_path)

	if not files:
		print('no color frames in folder')
		return

	exposure = calculate_exposure(
		files,
		n_samples=32,
		# percentile=99,
		# target=.95
	)

	first = load_fc(files[0])
	h, w = first.shape[:2]
	del first

	writer = cv2.VideoWriter(
		str(path / config["colorVidOut"]),
		cv2.VideoWriter_fourcc(*"mp4v"),
		config['frameCapFPS'],
		(w, h)
	)

	if not writer.isOpened():
		raise RuntimeError('failed to open video writer')

	print('writing color frames...')

	try:
		for file in tqdm(files):
			img = load_fc(file)[..., :3]

			img = np.clip(img / exposure, 0.0, 1.0)
			img = linear_to_srgb(img)
			img = (img * 255).astype(np.uint8)

			# EXR is RGB; OpenCV VideoWriter expects BGR.
			writer.write(img[..., ::-1])
	finally:
		writer.release()
	
def resolveIDremapping(): 
	remappath = path.parent.parent.parent / config["idRemapFile"]
	uniqueids = meta['uniqueids']

	if remappath.exists():
		with remappath.open('r') as f:
			existing = json.load(f)
	else: existing = []

	# force sky to 0
	if '0' not in existing:
		existing.insert(0, '0')
	elif existing[0] != '0':
		existing.remove('0')
		existing.insert(0, '0')

	for id in uniqueids:
		if id not in existing:
			existing.append(id)

	with remappath.open('w') as w:
		json.dump(existing, w)

	return existing
	
def processdataframes():
	print('processing data frames...')

	remap = resolveIDremapping()

	files = getFCfileswtf(path / config["frameCapDataSubFolder"])

	if not files or len(files) == 0:
		print('no data files, skipping..')
		return;

	first = load_fc(files[0])
	h, w = first.shape[:2]
	fps = config['frameCapFPS']

	ffmpeg = subprocess.Popen(
		[
			"ffmpeg", "-y",
				*(['-hide_banner',
				"-loglevel", "warning",
				"-stats"] if quiet_ffmpeg else []),
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
			str(path / config["dataVidOut"]),
		],
		stdin=subprocess.PIPE,
	)
	
	def convert_r(channel):
		return np.clip(channel * config["depthScale"], 0, 65535).astype(np.uint16)

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
			data = load_fc(framepath)

			frame = np.empty((h, w, 4), dtype=np.uint16)
			frame[..., 0] = convert_r(data[..., 0])
			frame[..., 1] = convert_g(data[..., 1])
			frame[..., 2] = convert_b(data[..., 2])
			frame[..., 3] = convert_a(data[..., 3])

			ffmpeg.stdin.write(frame.astype("<u2", copy=False).tobytes())
	finally:
		ffmpeg.stdin.close()
		if ffmpeg.wait() != 0:
			raise RuntimeError("FFmpeg encoding failed")

def loadviscompDF(time):
	dataindex = int(time * config['frameCapFPS'])
	loadviscompDF.sf_time = time
	ext = 'exr' if config['useEXR'] else 'bytes'
	exrpath = path / config["frameCapDataSubFolder"] \
		/ (f'%0{config["frameNumDigits"]}d.{ext}' % dataindex)

	# if frame cap runs at different fps than extra data, it may lag behind
	while not exrpath.exists():
		dataindex -= 1
		exrpath = path / config["frameCapDataSubFolder"] \
			/ (f'%0{config["frameNumDigits"]}d.{ext}' % dataindex)
		
	exr = load_fc(exrpath)
	loadviscompDF.segframe = exr[..., 1].view(np.uint32)

loadviscompDF.segframe = None
loadviscompDF.sf_time = -1

def computevisibility(bbobj):
	id = bbobj['ID']
	time = bbobj['time'] / config['timeScale']

	if loadviscompDF.segframe is None or loadviscompDF.sf_time != time:
		loadviscompDF(time)

	return bool(np.any(loadviscompDF.segframe == id))

def processbboxes():
	print('processing bboxes..')
	if not config['recordBboxes']: 
		print('bboxes not recorded, skipped')
		return
	
	if not (path / config["frameCapDataSubFolder"]).exists():
		print('frame captures are required for bbox visibility checking, cannot process bboxes')
		return
	
	data = json.loads((path / config['bboxFileName']).read_text())

	'''
	structure:
		[
		{time:
		bboxes:[
			{
			id: label:
			min:[] max:[]
			dist: visible:
			}
		]} -- remove non rendered
		]
	'''
	out = []

	for frame in tqdm(data, 'frame'):
		if len(frame) == 0: continue

		bbs = []
		for o in frame:
			if not o['rendered']: continue

			visible = computevisibility(o)
			bb = {
				'id' : o['ID'], 'label' : o['label'],
				'min' : [o['min']['x'], o['min']['y']],
				'max' : [o['max']['x'], o['max']['y']],
				'dist' : o['distance'],
				'visible' : visible
			}

			bbs.append(bb)

		item = {
			'time' : frame[0]['time'],
			'bboxes' : bbs
		}
		out.append(item)

	with (path / config["bboxesOut"]).open('w') as w:
		json.dump(out, w)

if __name__ == "__main__":
	setupStdout()
	jsonpath = sys.argv[1]

	with open(jsonpath, "r") as f:
		meta = json.load(f)
	config = meta['config']

	camfilepath = meta['outfilepath']
	camname = Path(camfilepath).stem

	permutation = meta['permutation']
	permfoldername = '_'.join(str(num) for num in permutation)

	path = Path(camfilepath).parent / config["outSubfolder"] / permfoldername / camname
	path.mkdir(parents=True, exist_ok=True)

	processbin()

	processcolorframes()

	processdataframes()

	processbboxes()

	if config['deleteFrameCapsAfterPostProcess']:
		shutil.rmtree(str(path / config["frameCapSubFolder"]), ignore_errors=True)
		shutil.rmtree(str(path / config["frameCapDataSubFolder"]), ignore_errors=True)