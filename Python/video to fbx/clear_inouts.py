import shutil
from pathlib import Path

def clear(path):
    shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)

pyroot = Path(__file__).resolve().parent.parent

ap = pyroot / 'AlphaPose-master'
clear(ap / 'input')
clear(ap / 'output')

mb = pyroot / 'MotionBERT'
clear(mb / 'input')
clear(mb / 'output')

here = Path(__file__).resolve().parent
clear(here / 'output')

print('cleared')