import numpy as np
import pytest
from app.face.matcher import Candidate, match_face
from app.face.types import FaceError, FaceFeature


def vector(score, version='test'):
    data=np.zeros(512, dtype=np.float32); data[0]=score; data[1]=np.sqrt(1-score**2)
    return FaceFeature(data, version, 100)


def test_group_same_person_and_threshold():
    query=vector(1)
    assert match_face(query, [Candidate(1, vector(.8)), Candidate(1, vector(.8))], .5, .1).user_id == 1
    assert match_face(query, [Candidate(2, vector(.5))], .5, .1).user_id == 2
    with pytest.raises(FaceError, match='UNKNOWN_PERSON'):
        match_face(query, [Candidate(2, vector(.49))], .5, .1)


def test_empty_tie_margin_and_version():
    query=vector(1)
    with pytest.raises(FaceError, match='UNKNOWN_PERSON'): match_face(query, [], .5, .1)
    with pytest.raises(FaceError, match='AMBIGUOUS_PERSON'):
        match_face(query, [Candidate(1, vector(.8)), Candidate(2, vector(.8))], .5, .1)
    assert match_face(query, [Candidate(1, vector(.9)), Candidate(2, vector(.6))], .5, .1).user_id == 1
    with pytest.raises(RuntimeError, match='Mixed model'):
        match_face(query, [Candidate(1, vector(.8, 'other'))], .5, .1)
