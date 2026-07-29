
from pathlib import Path
import argparse
import cv2
import numpy as np


EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".tif", ".tiff",
    ".bmp", ".webp"
}


def generate_normal_map(
    image: np.ndarray,
    strength: float = 4.0,
    blur: float = 1.0,
    invert_y: bool = False,
) -> np.ndarray:
    """
    Generate a tangent-space normal map from an RGB texture.

    Output convention:
        R = X
        G = Y
        B = Z

    Default Y orientation is suitable for Unity/DirectX normal maps.
    """

    if image.ndim == 2:
        gray = image
    else:
        # OpenCV loads images as BGR.
        gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)

    gray = gray.astype(np.float32) / 255.0

    if blur > 0:
        gray = cv2.GaussianBlur(
            gray,
            ksize=(0, 0),
            sigmaX=blur,
            sigmaY=blur,
            borderType=cv2.BORDER_REFLECT101,
        )

    # Scharr gives more rotationally accurate 3x3 derivatives than Sobel.
    dx = cv2.Scharr(
        gray,
        cv2.CV_32F,
        1,
        0,
        borderType=cv2.BORDER_REFLECT101,
    )

    dy = cv2.Scharr(
        gray,
        cv2.CV_32F,
        0,
        1,
        borderType=cv2.BORDER_REFLECT101,
    )

    # Scharr's derivative scale is approximately 32.
    scale = strength / 32.0

    nx = -dx * scale
    ny = dy * scale if invert_y else -dy * scale
    nz = np.ones_like(gray)

    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx /= length
    ny /= length
    nz /= length

    # Encode [-1, 1] as [0, 255].
    normal_rgb = np.stack((nx, ny, nz), axis=-1)
    normal_rgb = np.clip(
        (normal_rgb * 0.5 + 0.5) * 255.0,
        0,
        255,
    ).astype(np.uint8)

    # Convert RGB to BGR for cv2.imwrite.
    return normal_rgb[:, :, ::-1]


def is_input_texture(path: Path) -> bool:
    stem = path.stem.lower()

    excluded_suffixes = (
        "_normal",
        "_norm",
        "_nrm",
        "_nor",
    )

    return (
        path.is_file()
        and path.suffix.lower() in EXTENSIONS
        and not stem.endswith(excluded_suffixes)
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-generate Unity tangent-space normal maps."
    )

    parser.add_argument(
        "folder",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Input folder. Defaults to the current directory.",
    )

    parser.add_argument(
        "--strength",
        type=float,
        default=4.0,
        help="Normal intensity. Default: 4.0",
    )

    parser.add_argument(
        "--blur",
        type=float,
        default=1.0,
        help="Pre-gradient Gaussian blur. Default: 1.0",
    )

    parser.add_argument(
        "--invert-y",
        action="store_true",
        help="Generate OpenGL-style Y orientation instead of Unity/DirectX.",
    )

    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Process subdirectories.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing normal maps.",
    )

    args = parser.parse_args()

    folder = args.folder.resolve()

    if not folder.is_dir():
        raise NotADirectoryError(folder)

    paths = folder.rglob("*") if args.recursive else folder.iterdir()
    inputs = sorted(path for path in paths if is_input_texture(path))

    if not inputs:
        print(f"No supported images found in: {folder}")
        return

    completed = 0
    skipped = 0
    failed = 0

    for source in inputs:
        destination = source.with_name(f"{source.stem}_normal.png")

        if destination.exists() and not args.overwrite:
            print(f"SKIP  {destination.name}")
            skipped += 1
            continue

        image = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)

        if image is None:
            print(f"FAIL  {source}")
            failed += 1
            continue

        try:
            normal = generate_normal_map(
                image,
                strength=args.strength,
                blur=args.blur,
                invert_y=args.invert_y,
            )

            if not cv2.imwrite(str(destination), normal):
                raise RuntimeError("cv2.imwrite returned False")

            print(f"OK    {source.name} -> {destination.name}")
            completed += 1

        except Exception as error:
            print(f"FAIL  {source.name}: {error}")
            failed += 1

    print(
        f"\nGenerated: {completed} | "
        f"Skipped: {skipped} | "
        f"Failed: {failed}"
    )


if __name__ == "__main__":
    main()