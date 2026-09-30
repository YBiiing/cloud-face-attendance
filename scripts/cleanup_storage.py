"""Preview managed photo cleanup; --apply is required to remove files."""
import argparse
import json
from app.config import Settings
from app.database import make_engine, make_session_factory
from app.services.storage_lifecycle import cleanup


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--retention-hours',type=int,default=24)
    args=parser.parse_args();settings=Settings.from_env();engine=make_engine(settings)
    try:print(json.dumps(cleanup(make_session_factory(engine),settings.storage_dir,apply=args.apply,retention_hours=args.retention_hours),indent=2))
    finally:engine.dispose()


if __name__=='__main__':main()
