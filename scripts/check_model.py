import os
from pathlib import Path
from time import perf_counter
from app.face.engine import FaceEngine


def main():
    started = perf_counter()
    engine = FaceEngine(Path(os.getenv('MODEL_DIR', 'models')))
    print({'version': engine.version, 'detector': engine.detector.session.get_providers(),
           'recognizer': engine.recognizer.session.get_providers(), 'load_seconds': round(perf_counter()-started, 3)})


if __name__ == '__main__':
    main()
