"""Only initialize inside the inference process; no downloads at request time."""
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from insightface.model_zoo import get_model
from insightface.utils.face_align import norm_crop
import cv2
from app.face.types import FaceFeature, FaceError


class FaceEngine:
    def __init__(self, model_dir: Path, threads: int = 1):
        root = model_dir / "buffalo_l"
        names = ("det_10g.onnx", "w600k_r50.onnx")
        if not all((root / name).is_file() for name in names) or not (root / "manifest.json").is_file():
            raise RuntimeError("Model files missing; run python -m scripts.prepare_models")
        manifest = json.loads((root / "manifest.json").read_text(encoding='utf-8'))
        hashes = []
        for name in names:
            with (root / name).open('rb') as source:
                digest = hashlib.file_digest(source, 'sha256').hexdigest()
            if manifest['sha256'].get(name) != digest:
                raise RuntimeError("Model checksum mismatch")
            hashes.append(digest)
        self.version = 'buffalo_l:' + hashlib.sha256(''.join(hashes).encode()).hexdigest()[:16] + ':align-v1'
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        providers = ['CPUExecutionProvider']
        self.detector = get_model(str(root / names[0]), providers=providers, sess_options=options)
        self.recognizer = get_model(str(root / names[1]), providers=providers, sess_options=options)
        self.detector.prepare(ctx_id=-1, input_size=(640, 640))
        self.recognizer.prepare(ctx_id=-1)
        self.detector.detect(np.zeros((640, 640, 3), dtype=np.uint8))
        self.recognizer.get_feat(np.zeros((112, 112, 3), dtype=np.uint8))

    def extract(self, image: np.ndarray) -> FaceFeature:
        boxes, points = self.detector.detect(image, max_num=0)
        if len(boxes) == 0:
            raise FaceError('NO_FACE')
        if len(boxes) != 1:
            raise FaceError('MULTIPLE_FACES')
        x1, y1, x2, y2 = boxes[0, :4].astype(int)
        if min(x2-x1, y2-y1) < 60 or points is None:
            raise FaceError('LOW_QUALITY')
        crop = image[max(0, y1):min(image.shape[0], y2), max(0, x1):min(image.shape[1], x2)]
        if crop.size == 0:
            raise FaceError('LOW_QUALITY')
        sharpness = float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        if sharpness < 20:
            raise FaceError('LOW_QUALITY')
        aligned = norm_crop(image, landmark=points[0], image_size=112)
        feature = np.asarray(self.recognizer.get_feat(aligned), dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(feature))
        if feature.shape != (512,) or not np.isfinite(feature).all() or norm < 1e-8:
            raise RuntimeError('Invalid model output')
        return FaceFeature(feature / norm, self.version, sharpness)
