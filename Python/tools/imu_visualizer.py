#!/usr/bin/env python3
"""Plot IMU channels and componentwise time integrals from a CSV/TSV file.

Expected headers:
  time (ns), wx (rad/s), wy (rad/s), wz (rad/s),
  ax (m/s^2), ay (m/s^2), az (m/s^2)

Usage:
  python imu_visualizer.py imu.csv
  python imu_visualizer.py imu.csv --save plots.png --export integrated.csv
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

AXES = "xyz"
TIME_COLUMN = "time (ns)"
GYRO_COLUMNS = [f"w{axis} (rad/s)" for axis in AXES]
ACCEL_COLUMNS = [f"a{axis} (m/s^2)" for axis in AXES]


def integrate(values: np.ndarray, time_s: np.ndarray) -> np.ndarray:
    """Cumulative trapezoidal integration, initialized at zero."""
    result = np.zeros_like(values, dtype=np.float64)
    dt = np.diff(time_s)
    result[1:] = np.cumsum(0.5 * (values[1:] + values[:-1]) * dt[:, None], axis=0)
    return result


def load_imu(path: Path):
    data = pd.read_csv(path, sep=None, engine="python")  # comma or tab-separated
    data.columns = data.columns.str.strip()
    required = [TIME_COLUMN, *GYRO_COLUMNS, *ACCEL_COLUMNS]
    missing = [name for name in required if name not in data.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}\nFound: {list(data.columns)}")
    if len(data) < 2:
        raise ValueError("At least two IMU samples are required.")

    times_ns = pd.to_numeric(data[TIME_COLUMN], errors="raise").to_numpy(dtype=np.int64)
    if np.any(np.diff(times_ns) <= 0):
        raise ValueError("'time (ns)' must be strictly increasing with no duplicates.")
    time_s = (times_ns - times_ns[0]).astype(np.float64) / 1e9

    gyro = data[GYRO_COLUMNS].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    accel = data[ACCEL_COLUMNS].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    if not (np.isfinite(gyro).all() and np.isfinite(accel).all()):
        raise ValueError("Gyroscope and accelerometer channels must contain finite numbers.")
    return time_s, gyro, accel


def visualize(time_s, gyro, accel, angles, velocity, position, save_path=None):
    rows = [
        (gyro, "Angular velocity", "rad/s"),
        (angles, "Integrated angular rate", "rad"),
        (accel, "Acceleration", "m/s²"),
        (velocity, "Integrated acceleration", "m/s"),
        (position, "Integrated velocity", "m"),
    ]
    fig, plots = plt.subplots(5, 3, figsize=(15, 13), sharex=True, layout="constrained")
    for row_i, (values, name, unit) in enumerate(rows):
        for col_i, axis in enumerate(AXES):
            ax = plots[row_i, col_i]
            ax.plot(time_s, values[:, col_i], linewidth=1.2)
            ax.set_title(f"{name}: {axis.upper()} axis")
            ax.set_ylabel(unit)
            ax.grid(True, alpha=0.3)
            if row_i == len(rows) - 1:
                ax.set_xlabel("Time since first sample (s)")
    fig.suptitle("IMU signals and time integrals", fontsize=16)
    if save_path:
        fig.savefig(save_path, dpi=160)
    plt.show()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="CSV/TSV containing IMU samples")
    parser.add_argument("--save", type=Path, help="Save graph to PNG/PDF/SVG")
    parser.add_argument("--export", type=Path, help="Export integrated signals to CSV")
    args = parser.parse_args()

    time_s, gyro, accel = load_imu(args.csv)
    angles = integrate(gyro, time_s)
    velocity = integrate(accel, time_s)
    position = integrate(velocity, time_s)

    if args.export:
        columns = {"time (s)": time_s}
        for i, axis in enumerate(AXES):
            columns[f"theta_{axis} (rad)"] = angles[:, i]
            columns[f"v{axis} (m/s)"] = velocity[:, i]
            columns[f"p{axis} (m)"] = position[:, i]
        pd.DataFrame(columns).to_csv(args.export, index=False)

    visualize(time_s, gyro, accel, angles, velocity, position, args.save)


if __name__ == "__main__":
    main()
