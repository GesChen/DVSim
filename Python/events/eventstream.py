from pathlib import Path
import numpy as np


class EventStream:
    def __init__(self, x, y, t, p):
        self.x = np.asarray(x, dtype=np.int32)
        self.y = np.asarray(y, dtype=np.int32)
        self.t = self._to_seconds(np.asarray(t, dtype=np.float64))
        self.p = np.asarray(p).astype(bool)

        n = len(self.x)
        if not (len(self.y) == len(self.t) == len(self.p) == n):
            raise ValueError("x, y, t, and p must have equal lengths")

    @staticmethod
    def _to_seconds(t):
        if t.size == 0:
            return t

        magnitude = np.max(np.abs(t))

        # Assumes relative timestamps rather than Unix timestamps.
        if magnitude >= 1e12:
            return t / 1e9       # nanoseconds
        if magnitude >= 1e9:
            return t / 1e6       # microseconds
        if magnitude >= 1e6:
            return t / 1e3       # milliseconds

        return t                  # seconds

    @classmethod
    def from_unity(cls, path):
        print("loading dataset...")

        data = np.load(Path(path))["arr_0"]

        stream = cls(
            x=data["x"],
            y=data["y"],
            t=data["t"] / 1e9,
            p=data["p"],
        )

        print("loaded")
        return stream

    @classmethod
    def from_unity_raw(cls, path):
        print("loading dataset...")

        data = np.load(Path(path))["arr_0"]

        print("loaded")
        return data

    @classmethod
    def from_v2e(cls, path):
        print("loading dataset...")

        data = np.load(Path(path))["events"]

        stream = cls(
            x=data[:, 1],
            y=data[:, 2],
            t=data[:, 0],
            p=data[:, 3],
        )

        print("loaded")
        return stream

    def __len__(self):
        return len(self.t)