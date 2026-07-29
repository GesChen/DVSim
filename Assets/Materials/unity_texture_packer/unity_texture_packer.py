from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps


DEFAULT_METALLIC = 0
DEFAULT_OCCLUSION = 255
DEFAULT_SMOOTHNESS = 128


def optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    value = value.strip().strip('"')
    return Path(value) if value else None


def first_existing(paths: Iterable[Path | None]) -> Path:
    for path in paths:
        if path is not None and path.is_file():
            return path
    raise FileNotFoundError("At least one valid input texture is required.")


def open_resized(path: Path, size: tuple[int, int], mode: str) -> Image.Image:
    with Image.open(path) as source:
        image = source.convert(mode)
    if image.size != size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    return image


def grayscale(path: Path | None, size: tuple[int, int], default: int) -> Image.Image:
    if path is None:
        return Image.new("L", size, default)
    return open_resized(path, size, "L")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pack common PBR textures for Unity URP Lit materials."
    )
    parser.add_argument("--color", help="Base color/albedo texture")
    parser.add_argument("--opacity", help="Opacity/alpha texture")
    parser.add_argument("--metallic", help="Metallic texture")
    parser.add_argument("--ao", help="Ambient occlusion texture")
    parser.add_argument("--roughness", help="Roughness texture; inverted into smoothness")
    parser.add_argument("--smoothness", help="Smoothness texture; used if roughness is omitted")
    parser.add_argument("--normal", help="Optional normal texture to copy/convert to PNG")
    parser.add_argument("--height", help="Optional height/displacement texture to copy/convert to PNG")
    parser.add_argument("--output-dir", help="Output directory; defaults beside the first input")
    parser.add_argument("--name", help="Output base name; defaults to the first input stem")
    args = parser.parse_args()

    color = optional_path(args.color)
    opacity = optional_path(args.opacity)
    metallic = optional_path(args.metallic)
    ao = optional_path(args.ao)
    roughness = optional_path(args.roughness)
    smoothness = optional_path(args.smoothness)
    normal = optional_path(args.normal)
    height = optional_path(args.height)

    supplied = [color, opacity, metallic, ao, roughness, smoothness, normal, height]
    missing = [str(path) for path in supplied if path is not None and not path.is_file()]
    if missing:
        raise FileNotFoundError("Input file(s) not found:\n" + "\n".join(missing))

    reference = first_existing(supplied)
    with Image.open(reference) as ref_image:
        size = ref_image.size

    output_dir = optional_path(args.output_dir) or reference.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    name = args.name.strip() if args.name else reference.stem

    # Base map: RGB = base color, A = opacity.
    if color is not None:
        base_rgb = open_resized(color, size, "RGB")
    else:
        base_rgb = Image.new("RGB", size, (255, 255, 255))
    alpha = grayscale(opacity, size, 255)
    base_map = base_rgb.copy()
    base_map.putalpha(alpha)

    # URP packed map: R = metallic, G = occlusion, B = unused, A = smoothness.
    metal_channel = grayscale(metallic, size, DEFAULT_METALLIC)
    ao_channel = grayscale(ao, size, DEFAULT_OCCLUSION)
    unused_channel = Image.new("L", size, 0)
    if roughness is not None:
        smooth_channel = ImageOps.invert(grayscale(roughness, size, 255 - DEFAULT_SMOOTHNESS))
    else:
        smooth_channel = grayscale(smoothness, size, DEFAULT_SMOOTHNESS)
    mask_map = Image.merge("RGBA", (metal_channel, ao_channel, unused_channel, smooth_channel))

    base_path = output_dir / f"{name}_BaseMap.png"
    mask_path = output_dir / f"{name}_MaskMap.png"
    base_map.save(base_path, optimize=True)
    mask_map.save(mask_path, optimize=True)

    written = [base_path, mask_path]

    if normal is not None:
        normal_out = output_dir / f"{name}_Normal.png"
        open_resized(normal, size, "RGB").save(normal_out, optimize=True)
        written.append(normal_out)

    if height is not None:
        height_out = output_dir / f"{name}_Height.png"
        grayscale(height, size, 0).save(height_out, optimize=True)
        written.append(height_out)

    print("\nCreated:")
    for path in written:
        print(path)
    print("\nUnity import settings:")
    print("- BaseMap: sRGB enabled")
    print("- MaskMap: sRGB disabled; assign the same texture to Metallic and Occlusion")
    print("- Normal: Texture Type = Normal map")
    print("- Height: sRGB disabled")


if __name__ == "__main__":
    main()
