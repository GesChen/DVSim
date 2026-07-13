from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image


def read_raw_ptex_hdr(path: str | Path) -> np.ndarray:
    """Read Replica's raw RGB-half-float PTex atlas as (H, W, 3) float32."""
    path = Path(path)
    byte_count = path.stat().st_size
    if byte_count == 0 or byte_count % 6 != 0:
        raise ValueError(f"{path} is not a packed RGB float16 image")

    pixel_count = byte_count // 6
    dimension = math.isqrt(pixel_count)
    if dimension * dimension != pixel_count:
        raise ValueError(
            f"{path} contains {pixel_count} RGB pixels, which is not square"
        )

    rgb = np.fromfile(path, dtype="<f2")
    return rgb.reshape(dimension, dimension, 3).astype(np.float32)


def apply_saturation(rgb: np.ndarray, saturation: float) -> np.ndarray:
    """Match the saturation operation used by Replica's atlas shader."""
    weights = np.asarray((0.299, 0.587, 0.114), dtype=np.float32)
    magnitude = np.sqrt(np.sum(rgb * rgb * weights, axis=-1, keepdims=True))
    return magnitude + (rgb - magnitude) * np.float32(saturation)


def convert_hdr_array_to_srgb8(
    rgb: np.ndarray,
    *,
    exposure: float = 0.025,
    gamma: float = 1.6969,
    saturation: float = 1.5,
    tone_map: str = "clip",
) -> np.ndarray:
    """Convert linear HDR RGB to an 8-bit display texture."""
    if gamma <= 0:
        raise ValueError("gamma must be greater than zero")
    if tone_map not in {"clip", "reinhard"}:
        raise ValueError("tone_map must be 'clip' or 'reinhard'")

    out = np.maximum(np.asarray(rgb, dtype=np.float32), 0.0)
    out *= np.float32(exposure)
    out = apply_saturation(out, saturation)
    out = np.maximum(out, 0.0)

    if tone_map == "reinhard":
        out = out / (1.0 + out)

    out = np.power(out, np.float32(1.0 / gamma))
    out = np.clip(out, 0.0, 1.0)
    return np.rint(out * 255.0).astype(np.uint8)


def convert_hdr_file(
    source: str | Path,
    destination: str | Path,
    *,
    exposure: float = 0.025,
    gamma: float = 1.6969,
    saturation: float = 1.5,
    tone_map: str = "clip",
    flip_vertical: bool = True,
) -> Path:
    """Convert one ``*-color-ptex.hdr`` file to a same-named PNG atlas."""
    source = Path(source)
    destination = Path(destination)

    rgb = read_raw_ptex_hdr(source)
    rgb8 = convert_hdr_array_to_srgb8(
        rgb,
        exposure=exposure,
        gamma=gamma,
        saturation=saturation,
        tone_map=tone_map,
    )

    # OpenGL treats the first raw row as y=0 (the bottom row). PNG treats its
    # first row as the top row, so flip to preserve the shader's atlas layout.
    if flip_vertical:
        rgb8 = np.flipud(rgb8)

    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb8, mode="RGB").save(destination)
    return destination


def convert_hdr_folder(
    source_folder: str | Path,
    output_folder: str | Path,
    *,
    exposure: float = 0.025,
    gamma: float = 1.6969,
    saturation: float = 1.5,
    tone_map: str = "clip",
    overwrite: bool = False,
) -> list[Path]:
    source_folder = Path(source_folder)
    output_folder = Path(output_folder)
    sources = sorted(source_folder.glob("*-color-ptex.hdr"))
    if not sources:
        raise FileNotFoundError(f"No *-color-ptex.hdr files found in {source_folder}")

    outputs: list[Path] = []
    for index, source in enumerate(sources, 1):
        destination = output_folder / f"{source.stem}.png"
        if destination.exists() and not overwrite:
            print(f"[{index}/{len(sources)}] exists: {destination.name}")
        else:
            print(f"[{index}/{len(sources)}] converting: {source.name}")
            convert_hdr_file(
                source,
                destination,
                exposure=exposure,
                gamma=gamma,
                saturation=saturation,
                tone_map=tone_map,
            )
        outputs.append(destination)

    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert raw Replica RGB-float16 PTex atlases to PNG."
    )
    parser.add_argument("source_folder", type=Path)
    parser.add_argument("output_folder", type=Path)
    parser.add_argument("--exposure", type=float, default=0.025)
    parser.add_argument("--gamma", type=float, default=1.6969)
    parser.add_argument("--saturation", type=float, default=1.5)
    parser.add_argument("--tone-map", choices=("clip", "reinhard"), default="clip")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    convert_hdr_folder(
        args.source_folder,
        args.output_folder,
        exposure=args.exposure,
        gamma=args.gamma,
        saturation=args.saturation,
        tone_map=args.tone_map,
        overwrite=args.overwrite,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
