"""OpenF1 endpoint survey (P0.8): a field table per endpoint and the update-rate figure.

Run from the repo root: uv run python scripts/figures/openf1.py
"""

import time
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from matplotlib.figure import Figure

from pitwall.ingest.openf1 import BASE_URL, OpenF1Client, Row, Session
from pitwall.ingest.profile import EndpointProfile
from pitwall.ingest.transport import CachedTransport, HttpTransport, Params, Response, Transport

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "openf1"
OUT = ROOT / "docs" / "figures"
CAR = 16  # Leclerc at Monza 2024, as in track.md
WINDOW = timedelta(minutes=10)  # of racing, for the per-car feeds (location, car_data)
INK = "#2b6cb0"

# whole-session endpoints, queried by session_key alone
SESSION_ENDPOINTS = ("intervals", "position", "stints", "pit", "race_control", "weather")
# these send a row when something happens, not on a clock
EVENT_FEEDS = frozenset({"position", "pit", "race_control"})


class Paced:
    """Waits between requests: OpenF1 answers a 4th request within a second with HTTP 429.

    Sits under the cache, so cached runs don't wait. The real limiter is P2.8.
    """

    def __init__(self, inner: Transport, interval: float = 0.4) -> None:
        self._inner = inner
        self._interval = interval
        self._last = 0.0

    def get(self, endpoint: str, params: Params) -> Response:
        time.sleep(max(0.0, self._last + self._interval - time.monotonic()))
        self._last = time.monotonic()
        return self._inner.get(endpoint, params)


def fetch(client: OpenF1Client) -> tuple[Session, dict[str, list[Row]]]:
    sessions = client.sessions(2024, "Monza", "Race")
    if not sessions:
        raise SystemExit("No Monza 2024 race found in OpenF1")
    session = sessions[0]
    rows = {name: client.query(name, {"session_key": session.key}) for name in SESSION_ENDPOINTS}
    # per-car feeds are big (~4 Hz): one car, a window that starts after the race start
    start = session.start + timedelta(minutes=30)
    window: Params = {
        "session_key": session.key,
        "driver_number": CAR,
        "date>": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "date<": (start + WINDOW).strftime("%Y-%m-%dT%H:%M:%S"),
    }
    rows["car_data"] = client.query("car_data", window)
    rows["location"] = client.query("location", window)
    return session, rows


def table(profile: EndpointProfile) -> str:
    """Markdown: one line per field, with its JSON types and an example value."""
    gap = profile.median_gap
    head = f"### `{profile.endpoint}`: {profile.rows} rows"
    head += "" if gap is None else f", median {gap:.3g} s between rows"
    lines = [head, "", "| Field | Types | Example |", "|---|---|---|"]
    for f in profile.fields:
        types = ", ".join(f"{name} {count}" for name, count in sorted(f.types.items()))
        lines.append(f"| `{f.name}` | {types} | `{f.example!r}` |"[:200])
    return "\n".join(lines)


def duration(seconds: float) -> str:
    return f"{seconds:.3g} s" if seconds < 60 else f"{seconds / 60:.3g} min"


def rates_figure(profiles: Sequence[EndpointProfile]) -> Figure:
    # sampled feeds below, event feeds above, each sorted by median gap
    timed = sorted(
        (p for p in profiles if p.gaps),
        key=lambda p: (p.endpoint in EVENT_FEEDS, p.median_gap or 0),
    )
    fig = Figure(figsize=(9, 0.6 * len(timed) + 1.4), layout="constrained")
    ax = fig.subplots()
    for i, p in enumerate(timed):
        # every gap as a faint tick, the median as a solid bar
        ax.scatter(p.gaps, [i] * len(p.gaps), marker="|", s=60, color=INK, alpha=0.15, lw=1)
        median = p.median_gap or 0
        ax.plot([median, median], [i - 0.3, i + 0.3], color=INK, lw=2.5)
        ax.annotate(
            duration(median),
            (median, i + 0.3),
            xytext=(4, 0),
            textcoords="offset points",
            va="bottom",
            fontsize=8,
            color="#333333",
        )
    ax.set_yticks(range(len(timed)), [f"{p.endpoint} ({p.rows} rows)" for p in timed])
    split = sum(p.endpoint not in EVENT_FEEDS for p in timed) - 0.5
    ax.axhline(split, color="#999999", lw=0.8, ls=(0, (4, 3)))
    for y, text in (
        (split - 0.1, "sampled on a clock"),
        (split + 0.1, "sent when something happens"),
    ):
        va = "top" if y < split else "bottom"
        ax.text(
            0.995,
            y,
            text,
            transform=ax.get_yaxis_transform(),
            ha="right",
            va=va,
            fontsize=8,
            color="#666666",
        )
    ax.set_xscale("log")
    ax.set_xlabel("seconds between consecutive rows (per car where rows have one; log scale)")
    ax.set_title(f"OpenF1 update intervals, Monza 2024 race (per-car feeds: car {CAR}, 10 min)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", which="major", color="#e5e5e5", lw=0.8)
    ax.set_axisbelow(True)
    return fig


def main() -> None:
    with HttpTransport.create(BASE_URL) as http:
        client = OpenF1Client(CachedTransport(Paced(http), CACHE))
        session, rows = fetch(client)
    profiles = [EndpointProfile.of(name, endpoint_rows) for name, endpoint_rows in rows.items()]

    print(f"Monza 2024 race, session {session.key}\n")
    for profile in profiles:
        print(table(profile), end="\n\n")

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "openf1_rates.png"
    # no "Software" tag: a matplotlib upgrade alone shouldn't rewrite the PNG
    rates_figure(profiles).savefig(path, dpi=150, metadata={"Software": None})
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
