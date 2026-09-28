"""Only initialize inside the inference process; no downloads at request time."""
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from insightface.model_zoo import get_model


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

