from pathlib import Path
from PIL import Image
from tqdm import tqdm

folder = Path(r"SMPLitex-textures")
overlay = Image.open("bettereyes.png").convert("RGBA")

for f in tqdm(folder.iterdir()):
    if (
        f.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
        or f.stem.endswith("_normal")
        or f.stem.endswith("_eyes")
        or f.name == "overlay.png"
    ):
        continue

    img = Image.open(f).convert("RGBA")
    out = Image.alpha_composite(img, overlay)
    out.save(f.with_stem(f.stem + "_eyes"))