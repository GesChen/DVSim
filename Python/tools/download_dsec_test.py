import argparse
from pathlib import Path
import os
import shutil
from typing import Optional

from requests import get
from tqdm import tqdm


TEST_SEQUENCES = [
    "interlaken_00_b",
    "interlaken_01_a",
    "thun_01_a",
    "thun_01_b",
    "zurich_city_12_a",
    "zurich_city_14_c",
    "zurich_city_15_a",
]

BASE_TEST_URL = "https://download.ifi.uzh.ch/rpg/DSEC/test/"
TEST_FLOW_TIMESTAMPS_URL = (
    "https://download.ifi.uzh.ch/rpg/DSEC/test_forward_optical_flow_timestamps.zip"
)


def download(url: str, filepath: Path, skip: bool = True, chunk_size: int = 8192) -> bool:
    if skip and filepath.exists():
        print(f"{filepath} already exists. Skipping download.")
        return True

    response = get(url, stream=True)
    total = int(response.headers.get("content-length", 0))

    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "wb") as fl, tqdm(
        total=total,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=filepath.name,
    ) as pbar:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                fl.write(chunk)
                pbar.update(len(chunk))

    return response.ok


def unzip(file_: Path, delete_zip: bool = True, skip: bool = True) -> Path:
    assert file_.exists()
    assert file_.suffix == ".zip"

    output_dir = file_.parent / file_.stem

    if skip and output_dir.exists():
        print(f"{output_dir} already exists. Skipping unzipping operation.")
    else:
        shutil.unpack_archive(file_, output_dir)

    if delete_zip and file_.exists():
        os.remove(file_)

    return output_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory")
    args = parser.parse_args()

    output_dir = Path(args.output_directory) / "test"
    output_dir.mkdir(parents=True, exist_ok=True)

    test_timestamps_file = output_dir / "test_forward_flow_timestamps.zip"

    assert download(TEST_FLOW_TIMESTAMPS_URL, test_timestamps_file), TEST_FLOW_TIMESTAMPS_URL
    test_timestamps_dir = unzip(test_timestamps_file)

    for seq_name in tqdm(TEST_SEQUENCES, desc="DSEC test sequences"):
        seq_path = output_dir / seq_name
        seq_path.mkdir(parents=True, exist_ok=True)

        img_timestamps_url = (
            BASE_TEST_URL + seq_name + "/" + seq_name + "_image_timestamps.txt"
        )
        img_timestamps_file = seq_path / "image_timestamps.txt"

        if not img_timestamps_file.exists():
            assert download(img_timestamps_url, img_timestamps_file), img_timestamps_url

        test_timestamps_file_destination = seq_path / "test_forward_flow_timestamps.csv"

        if not test_timestamps_file_destination.exists():
            shutil.move(
                test_timestamps_dir / f"{seq_name}.csv",
                test_timestamps_file_destination,
            )

        events_left_url = (
            BASE_TEST_URL + seq_name + "/" + seq_name + "_events_left.zip"
        )
        events_left_file = seq_path / "events_left.zip"
        events_left_dir = events_left_file.parent / events_left_file.stem

        if not events_left_dir.exists():
            assert download(events_left_url, events_left_file), events_left_url
            unzip(events_left_file)

    shutil.rmtree(test_timestamps_dir)