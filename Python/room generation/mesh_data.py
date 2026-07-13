from __future__ import annotations

from dataclasses import dataclass
import copy
import numpy as np


@dataclass
class MeshData:
    vbo: np.ndarray | None = None      # (N, 4) float32
    ibo: np.ndarray | None = None      # (M,) uint32
    nbo: np.ndarray | None = None      # (N, 4) float32
    cbo: np.ndarray | None = None      # (N, 4) uint8
    polygon_stride: int = 3

    def __post_init__(self):
        if self.vbo is not None:
            self.vbo = np.asarray(self.vbo, dtype=np.float32).reshape(-1, 4)

        if self.ibo is not None:
            self.ibo = np.asarray(self.ibo, dtype=np.uint32).reshape(-1)

        if self.nbo is not None:
            self.nbo = np.asarray(self.nbo, dtype=np.float32).reshape(-1, 4)

        if self.cbo is not None:
            self.cbo = np.asarray(self.cbo, dtype=np.uint8).reshape(-1, 4)

        self.polygon_stride = int(self.polygon_stride)

    def copy(self) -> "MeshData":
        return MeshData(
            vbo=None if self.vbo is None else self.vbo.copy(),
            ibo=None if self.ibo is None else self.ibo.copy(),
            nbo=None if self.nbo is None else self.nbo.copy(),
            cbo=None if self.cbo is None else self.cbo.copy(),
            polygon_stride=self.polygon_stride,
        )