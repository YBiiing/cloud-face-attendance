from dataclasses import dataclass
import numpy as np


class FaceError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class FaceFeature:
    embedding: np.ndarray
    model_version: str
    quality: float
