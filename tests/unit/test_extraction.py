import numpy as np
import pytest
from app.face.engine import FaceEngine
from app.face.types import FaceError


def engine_with(boxes, points=None):
    engine=FaceEngine.__new__(FaceEngine)
    class Detector:
        def detect(self,image,max_num): return np.asarray(boxes), points
    engine.detector=Detector()
    return engine


def test_detection_rejections():
    image=np.zeros((200,200,3),dtype=np.uint8)
    for boxes,code in [([], 'NO_FACE'), ([[0,0,80,80,1],[90,90,190,190,1]],'MULTIPLE_FACES'), ([[0,0,20,20,1]],'LOW_QUALITY')]:
        with pytest.raises(FaceError,match=code): engine_with(boxes).extract(image)


def test_feature_validation_and_normalization():
    engine=engine_with([[0,0,150,150,1]], np.array([[[38,52],[74,52],[56,72],[42,92],[70,92]]],dtype=np.float32))
    class Recognizer:
        def get_feat(self,image): return np.ones((1,512),dtype=np.float32)
    engine.recognizer=Recognizer(); engine.version='test'
    image=np.random.default_rng(1).integers(0,256,(200,200,3),dtype=np.uint8)
    result=engine.extract(image)
    assert result.embedding.shape==(512,)
    assert np.isclose(np.linalg.norm(result.embedding),1)
    engine.recognizer.get_feat=lambda image: np.full((1,512),np.nan)
    with pytest.raises(RuntimeError,match='Invalid model output'): engine.extract(image)
