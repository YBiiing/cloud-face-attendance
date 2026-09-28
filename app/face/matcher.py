from dataclasses import dataclass
import numpy as np
from app.face.types import FaceError, FaceFeature


@dataclass(frozen=True)
class Candidate:
    user_id: int
    feature: FaceFeature


@dataclass(frozen=True)
class Match:
    user_id: int
    score: float


def match_face(query: FaceFeature, candidates: list[Candidate], threshold: float, margin: float) -> Match:
    if not 0 <= threshold <= 1 or not 0 <= margin <= 2:
        raise ValueError('Invalid matching thresholds')
    scores = {}
    for candidate in candidates:
        if candidate.feature.model_version != query.model_version:
            raise RuntimeError('Mixed model versions')
        for vector in (query.embedding, candidate.feature.embedding):
            if vector.shape != (512,) or not np.isfinite(vector).all() or not np.isclose(np.linalg.norm(vector), 1, atol=1e-4):
                raise RuntimeError('Invalid embedding')
        score = float(query.embedding @ candidate.feature.embedding)
        scores[candidate.user_id] = max(scores.get(candidate.user_id, -1.0), score)
    ranked = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    if not ranked or ranked[0][1] < threshold:
        raise FaceError('UNKNOWN_PERSON')
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < margin:
        raise FaceError('AMBIGUOUS_PERSON')
    return Match(*ranked[0])
