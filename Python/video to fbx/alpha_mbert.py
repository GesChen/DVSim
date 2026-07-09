import subprocess
from pathlib import Path
import argparse
import os
import shutil
import numpy as np
import shlex

from colorama import just_fix_windows_console
from floorplane_correction import normalize_bone_forward_to_up

here = Path(__file__).resolve().parent
inhere = here / "input"
outhere = here / "output"

parser = argparse.ArgumentParser()
parser.add_argument("input_file")

parser.add_argument("--skip-alphapose", action="store_true")
parser.add_argument("--skip-motionbert", action="store_true")
parser.add_argument("--skip-ground-plane", action="store_true")
parser.add_argument("--skip-fbx", action="store_true")
parser.add_argument("--skip-copy", action="store_true")

args = parser.parse_args()

input_path = inhere / args.input_file
if not input_path.exists():
	raise FileNotFoundError(f"File does not exist: {input_path}")

infilebase = Path(args.input_file).stem

just_fix_windows_console()


def cprint(text, rgb=(0, 255, 0)):
	print(f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m{text}\033[0m")


ap_wd = here.parent / "AlphaPose-master"
mb_wd = here.parent / "MotionBERT"

ap_out = ap_wd / "output" / "alphapose-results.json"


# 1. AlphaPose inference
if not args.skip_alphapose:
	cprint("1. alphapose")

	subprocess.run(
		[
			"python",
			"-m",
			"scripts.demo_inference",
			"--cfg",
			"configs/halpe_26/resnet/256x192_res50_lr1e-3_1x.yaml",
			"--checkpoint",
			"pretrained_models/halpe26_fast_res50_256x192.pth",
			"--video",
			str(input_path),
			"--outdir",
			"output",
		],
		cwd=str(ap_wd),
		check=True,
	)


# 2. MotionBERT
if not args.skip_motionbert:
	cprint("2. motionbert")

	shutil.copy2(
		str(input_path),
		str(mb_wd / "input" / args.input_file),
	)

	shutil.copy2(
		str(ap_out),
		str(mb_wd / "input" / f"alphapose-results-{infilebase}.json"),
	)

	subprocess.run(
		[
			# "conda",
			# "run",
			# "--no-capture-output",
			# "-n",
			# "motionbert",
			"python",
			"infer_wild_modified.py",
			"--vid_path",
			f"input/{args.input_file}",
			"--json_path",
			f"input/alphapose-results-{infilebase}.json",
			"--out_path",
			"output",
		],
		cwd=str(mb_wd),
		check=True,
	)

# 3. Ground plane alignment
if not args.skip_ground_plane:
	cprint("3. ground plane alignment")

	motions = np.load(str(mb_wd / "output" / "X3D.npy"))

	spine_points = [
		(0, 7),
		(7, 8),
		(8, 10)
	]

	aligned_motions = normalize_bone_forward_to_up(
		motions,
		spine_points,
		1
	)

	print(f'aligned with average forward of {aligned_motions[2]}')

	aligned_motions = aligned_motions[0]

	np.save(str(outhere / f"X3D-{infilebase}.npy"), aligned_motions)


# 4. FBX conversion
if not args.skip_fbx:
	cprint("4. fbx conversion")

	blender_path = r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe'
	fbxout = outhere / f'skeleton-{infilebase}.fbx'

	import cv2
	def get_video_fps(path):
		path = Path(path)

		cap = cv2.VideoCapture(str(path))
		if not cap.isOpened():
			raise FileNotFoundError(f"Could not open video: {path}")

		try:
			fps = cap.get(cv2.CAP_PROP_FPS)
			if fps <= 0:
				raise RuntimeError("Could not determine FPS.")
			return fps
		finally:
			cap.release()

	src_fps = int(get_video_fps(inhere / args.input_file))

	subprocess.run(
		[
			blender_path, '--background', '--factory-startup',
			'--python', 'armature_fbx_conversion.py', '--',
			'--np', str(outhere / f'X3D-{infilebase}.npy'),
			'--armature-blend', str(here / 'armature.blend'),
			'--armature-name', "Armature",
			'--out', str(fbxout),
			'--fps', str(src_fps),
			'--scale', '1.0'
		],
		cwd=str(here),
		check=True
	)

# copy into assets
if not args.skip_copy:
	cprint("5. copy into assets", (0, 255, 0))
	shutil.copy2(
		str(fbxout),
		here.parent.parent / 'Assets/Assets/MotionBERT' / fbxout.name
	)
	print('copied into assets/motionbert')

print('done')