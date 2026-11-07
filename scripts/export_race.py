"""Export one race for the browser replay (P1.1): every car's positions, drivers and the track.

Run from the repo root: uv run python scripts/export_race.py --year 2024 --circuit Monza
"""

import argparse
import gzip
import re
import sys
from pathlib import Path

from pitwall.errors import PitwallError
from pitwall.files import write_atomic
from pitwall.ingest.openf1 import BASE_URL, OpenF1Client
from pitwall.ingest.transport import CachedTransport, HttpTransport, PacedTransport
from pitwall.replay.export import RaceReplay
from pitwall.track.outline import TrackOutline

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "openf1"
RACES = ROOT / "frontend" / "public" / "races"


def export(client: OpenF1Client, year: int, circuit: str, car: int) -> RaceReplay:
    sessions = client.sessions(year, circuit, "Race")
    if not sessions:
        raise SystemExit(f"No {circuit} {year} race found in OpenF1")
    session = sessions[0]
    laps = client.laps(session.key)
    start, end = RaceReplay.window(laps)
    samples = client.locations(session.key, start, end)
    track = TrackOutline.build(
        [lap for lap in laps if lap.driver == car], [s for s in samples if s.driver == car]
    )
    return RaceReplay.build(session, client.drivers(session.key), laps, samples, track)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--circuit", required=True, help="OpenF1 circuit_short_name, e.g. Monza")
    parser.add_argument("--car", type=int, default=16, help="whose laps draw the track outline")
    parser.add_argument("--out", type=Path, help="default: frontend/public/races/<circuit>-<year>")
    args = parser.parse_args(argv[1:])
    slug = re.sub(r"\s+", "-", args.circuit.strip().lower())  # Las Vegas: las-vegas
    out: Path = args.out or RACES / f"{slug}-{args.year}.json"

    try:
        with HttpTransport.create(BASE_URL) as http:
            client = OpenF1Client(CachedTransport(PacedTransport(http), CACHE))
            replay = export(client, args.year, args.circuit, args.car)
    except PitwallError as e:
        print(f"export_race: {e}", file=sys.stderr)
        return 1

    text = replay.to_json().encode()
    write_atomic(out, text)
    samples = sum(len(car.t) for car in replay.cars)
    print(f"wrote {out}: {len(replay.cars)} cars, {samples} samples")
    print(f"size: {len(text) / 1e6:.2f} MB, {len(gzip.compress(text)) / 1e6:.2f} MB gzipped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
