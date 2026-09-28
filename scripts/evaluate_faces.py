"""Evaluate consented samples; output aggregate counts only, never embeddings."""
import argparse
from collections import Counter
import json
from pathlib import Path
from time import perf_counter

from app.face.engine import FaceEngine
from app.face.images import decode_image
from app.face.matcher import Candidate, match_face
from app.face.types import FaceError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--model-dir', type=Path, default=Path('/srv/models'))
    parser.add_argument('--threshold', type=float, required=True)
    parser.add_argument('--margin', type=float, required=True)
    args = parser.parse_args()
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    root=args.manifest.resolve().parent
    def extract(relative):
        target=(root/relative).resolve()
        if not target.is_relative_to(root): raise ValueError('Sample path outside manifest directory')
        return engine.extract(decode_image(target.read_bytes()))
    engine=FaceEngine(args.model_dir)
    gallery=[Candidate(int(item['user_id']), extract(item['file'])) for item in manifest['gallery']]
    if not gallery or not manifest['probes']: raise ValueError('Gallery and probes required')
    counts=Counter(); started=perf_counter()
    for item in manifest['probes']:
        expected=item.get('user_id')
        try:
            found=match_face(extract(item['file']),gallery,args.threshold,args.margin)
            counts['correct_accept' if found.user_id==expected else 'false_accept']+=1
        except FaceError as error:
            counts['correct_reject' if expected is None else 'false_reject']+=1
            counts[error.code]+=1
    print(json.dumps({'model':engine.version,'gallery_photos':len(gallery),
                      'gallery_people':len({item.user_id for item in gallery}),
                      'probe_count':len(manifest['probes']),'threshold':args.threshold,
                      'margin':args.margin,'seconds':round(perf_counter()-started,3),
                      'counts':dict(counts)},indent=2))


if __name__=='__main__': main()
