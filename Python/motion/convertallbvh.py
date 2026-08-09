from pathlib import Path
import subprocess
from tqdm import tqdm

bvhs = Path(r'E:\DVSim\Assets\Assets\Mocap\cmu mocap bvhs\\').glob("**/*.bvh")

for bvh in tqdm(list(bvhs)):
    subprocess.run([
        'convert_bvh_to_fbx.bat',
        str(bvh)
    ], check=True, capture_output=True)
