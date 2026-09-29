from app.face.gallery import Gallery
from app.face.matcher import match_face
from app.face.types import FaceError
from app.services.attendance import finish_checkin

gallery = Gallery()


def recognize_checkin(factory, task_id, attempt, feature, settings):
    for _ in range(3):
        version, candidates = gallery.load(factory)
        match = None
        rejection = None
        try:
            match = match_face(feature, candidates, settings.match_threshold, settings.match_margin)
        except FaceError as error:
            rejection = error.code
        if finish_checkin(factory, task_id, attempt, version, match, rejection, feature.model_version):
            return
    # A rapidly changing gallery must not produce a decision from stale data.
    raise RuntimeError('Gallery changed repeatedly')
