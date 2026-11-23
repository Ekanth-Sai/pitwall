# Frontend

The browser app: React + TypeScript, built with Vite, in `frontend/`. P1.2 set up the tooling and
the gates. P1.3 onwards fill it: the track, the dots, the clock and the controls. It gets the same
standards as the Python code: strict types, a linter that uses those types, a formatter, tests
with an 85% coverage gate, and a CI job.

## Stack

| Tool | Version | Job | Python equivalent |
|---|---|---|---|
| Node.js | 22 (`.nvmrc`), at least 22.22.2 (`engines`) | Runs the tools: the browser runs the built app, not Node | the interpreter |
| pnpm | 12.17.0 (`packageManager` in `package.json`) | Installs packages from `pnpm-lock.yaml` | uv |
| Vite | 8.3 | Dev server with instant reload; bundles the app for production | (none) |
| React | 19.3 | Builds the page from components | (none) |
| TypeScript | 6.0 | Types; `tsc` only checks, Vite strips the types when building | mypy |
| ESLint + typescript-eslint | 10.14 + 8.72 | Lint rules, many of them using the types | ruff check |
| Prettier | 3.9 | Formatting | ruff format |
| Vitest + Testing Library | 5.0 + 16.3 | Tests in a simulated browser (jsdom), with v8 coverage | pytest + coverage |
| user-event | 14.6 | Tests click and type the way a user does (P1.5) | (none) |

## Layout

```text
frontend/
├── index.html            the one page; loads src/main.tsx
├── package.json          dependencies and scripts; pins pnpm
├── pnpm-lock.yaml        exact versions of everything installed (commit it, like uv.lock)
├── pnpm-workspace.yaml   pnpm settings: the supply-chain guards below
├── vite.config.ts        Vite + Vitest config, including the coverage gate
├── eslint.config.js      lint rules
├── tsconfig.json         points at the two configs below
├── tsconfig.app.json     types for src/ (the browser code)
├── tsconfig.node.json    types for vite.config.ts (runs in Node)
├── public/               copied as-is into the build: favicon, races/monza-2024.json (P1.1)
└── src/
    ├── main.tsx          entry point: mounts App into index.html's #root
    ├── App.tsx           the top component: downloads the race, then shows it
    ├── RaceView.tsx      the controls and the track with every car on it, playing
    ├── index.css         page-wide styles
    ├── controls/
    │   ├── Controls.tsx  play/pause, 1×/10×, the space bar, race time
    │   └── raceTime.ts   race time as m:ss or h:mm:ss
    ├── race/load.ts      downloads and checks the race file, decodes the deltas
    ├── replay/
    │   ├── clock.ts      PlaybackClock: race time from wall time, speed, play/pause/seek
    │   ├── carTrack.ts   CarTrack: one car's position at any race time
    │   ├── usePlayback.ts  a hook: one clock for the view, and what the controls can do to it
    │   └── useAnimationFrame.ts  a hook that calls back once per screen refresh, while active
    ├── track/
    │   ├── projection.ts world coordinates (decimetres, y up) to SVG coordinates
    │   ├── TrackMap.tsx  the circuit and the dashed pit lane
    │   └── CarDot.tsx    one car: team colour, number in the ink colour
    └── test/
        ├── setup.ts      runs before every test file
        └── frames.ts     FakeFrames: screen refreshes a test steps by hand
```

Tests sit next to the code they test, as `*.test.ts` or `*.test.tsx`.

## Scripts

Run from `frontend/` as `pnpm <script>`, or from the repo root through the Makefile.

| Script | Make target | Does |
|---|---|---|
| `install --frozen-lockfile` | `make web-install` | Installs exactly what the lockfile says, or fails |
| `dev` | | Dev server on http://localhost:5173, reloads on save |
| `format` | `make web-fmt` | Prettier rewrites files |
| `check` | `make web-check` | The gate, below |
| `build` | `make web-build` | Type check, then bundle into `dist/` |
| `preview` | | Serves `dist/` locally, to try the production build |

`pnpm check` runs the same steps as CI, stopping at the first failure:

```mermaid
flowchart LR
    A["prettier --check"] --> B["eslint<br/>no warnings allowed"]
    B --> C["tsc -b<br/>strict types"]
    C --> D["vitest run --coverage<br/>85% gate"]
```

Every gate was checked to fail on purpose with a planted file:
- `xs[0]` returned as a `number` fails `tsc`, because of `noUncheckedIndexedAccess`;
- a `fetch` nobody awaits fails ESLint (`no-floating-promises`);
- an untested function fails the coverage gate.

## Decisions

1. **TypeScript 6.0, not 7.** TypeScript 7 (the compiler rewritten in Go) is out, and the Vite
   template now defaults to it. typescript-eslint 8.72 only supports TypeScript below 6.1, though,
   and type-aware lint rules are worth more here than a faster compiler: the project is small, and
   a cold `tsc` run takes about 3 s. Dependabot ignores TypeScript's minor and major releases
   (its first grouped PR, #151, bumped to 7 and failed CI), so the move is made by hand. Patch
   releases still come through.
   - **When to move:** every phase review runs `pnpm view typescript-eslint peerDependencies`. Once
     the `typescript` range includes a newer version, bump it on a branch of its own.
   - **Cost:** the ignore rule also blocks Dependabot *security* updates for those versions. The risk
     is low because TypeScript is a build tool and never ships to the browser. If an advisory ever
     names it, the phase-review check comes early.
   - **Not chosen:** a separate Dependabot group for the TypeScript toolchain. It would open a red PR
     every week until typescript-eslint caught up, and hold back typescript-eslint's own fixes in
     the meantime.
2. **ESLint, not oxlint.** The template now ships oxlint, a fast linter written in Rust. ESLint
   with typescript-eslint's `strictTypeChecked` preset has the rules that catch real bugs, such as a
   promise nobody awaits or a value typed `any` leaking through. Prettier owns formatting, and
   `eslint-config-prettier` turns off the lint rules that would fight it.
3. **Strictness.** `strict` plus three flags it leaves out:
   - `noUncheckedIndexedAccess`: `xs[i]` has the type `T | undefined`, because the index may be out
     of range. This is the TypeScript version of Python's `IndexError`, caught before running.
   - `exactOptionalPropertyTypes`: an optional property may be missing, but can't be set to
     `undefined` on purpose.
   - `noImplicitOverride`: a method that replaces a parent's must say `override`.
4. **Supply chain.** npm packages have been hijacked to publish malicious versions, and most were
   caught within days. So:
   - `minimumReleaseAge: 10080` (7 days): pnpm won't install a version younger than a week.
     The first install already picked vite 8.3.5 and vitest 5.0.5 over newer releases for this
     reason. The rule covers pnpm itself too: pnpm installs the version named in
     `packageManager`, so that pin is 12.17.0, not the 3-day-old 12.18.0.
   - `strictDepBuilds`: no dependency may run an install script unless it's listed. None needs one.
   - `--frozen-lockfile` in CI, and `pnpm audit --prod` for the packages that ship to the browser.
   - Dependabot opens weekly grouped updates for `frontend/`, like it does for Python, with a
     7-day `cooldown`. CI installs from the lockfile, so pnpm's age check never sees what
     Dependabot writes there; the cooldown applies the same rule on Dependabot's side.
5. **Style.** Prettier with no semicolons and single quotes (the Vite template's style), and 100
   columns to match ruff.
6. **Tests import `describe`, `it` and `expect` from `vitest`** instead of using globals, so every
   name in a test file comes from an import a reader can follow.
7. **Coverage leaves out `main.tsx`.** It only mounts `App` into the page. The tests render `App`
   directly.
8. **pnpm is installed with npm into `~/.local`** (`npm install -g pnpm@12.17.0 --prefix
   ~/.local`). Ubuntu's corepack (0.24) is too old for pnpm 12's layout and fails with
   `Cannot find module …/pnpm.cjs`.
9. **Node floor.** `engines` asks for Node 22.22.2 or later (or 24.15+), because jsdom's
   dependencies do. CI gets the newest 22.x from `.nvmrc`. Ubuntu's own package is 22.22.1, one
   patch behind: the tests pass on it, and pnpm only warns.
10. **Pre-commit.** Prettier formats only the staged files, so a file still being written is left
    alone. ESLint and `tsc` check all of `frontend/` whenever anything in it changes, because a
    change to a config file can break every other file. `make check` stays Python-only: the
    frontend gate is `make web-check`, and both run in CI.
11. **ESLint also checks `.js` files** (`js.configs.recommended`, Node globals), so the config file
    itself and any later script get linted too.
12. **`@types/node` stays on Node 22's types.** `engines` allows Node 22 and 24+, so the types
    follow the oldest of them: code that type-checks then runs on every supported Node, and an API
    that only Node 24 has is a type error. Dependabot ignores their major releases. The major moves
    by hand, in the same PR that raises `.nvmrc` and the `engines` floor.

## Drawing the race (P1.3)

The page downloads `races/monza-2024.json` (the file `make export` writes,
[replay.md](replay.md)), checks it, and draws every car at its first sample. P1.4 makes them
move.

```mermaid
flowchart LR
    A["monza-2024.json<br/>4.08 MB"] --> B["loadRace<br/>fetch, 30 s timeout"]
    B --> C["parseRace<br/>zod check, undo the deltas"]
    C --> D["Race<br/>typed, Float64Array per car"]
    D --> E["RaceView"]
    E --> F["TrackMap<br/>circuit, pit lane"]
    E --> G["CarDot x 20"]
```

`App` is in exactly one of three states and shows only that one:

```mermaid
flowchart LR
    L["loading<br/>Loading the race…"] -->|"race checked"| R["ready<br/>RaceView"]
    L -->|"download or check failed"| E["error<br/>the reason, as an alert"]
```

1. **The race file is checked when it arrives.** It's input from outside the code, like
   `TrackOutline.from_json` on the Python side. zod checks every field: the format version, a
   start time with exactly 3 fraction digits, bounds with min below max, hex colours, unique car
   numbers, integer columns of equal length, and times that start at 0 or later, strictly
   increase and end within `duration_ms`. Anything wrong becomes a `ReplayError` with zod's
   description of the first 5 problems and a count of the rest (a bad export could have a
   million), and the page shows it instead of drawing something broken. A timeout says "timed
   out", even when it hits while the body is still arriving. Past that point the rest of the app
   trusts the types.
2. **One projection for everything.** `Projection` rotates world points counter-clockwise by the
   export's `rotation`, then flips y, because SVG's y axis points down. The viewBox comes from the
   export's bounds plus a 400 dm margin, so dots at the edges fit. Only positions are projected,
   never the dot itself, so the numbers stay upright.
3. **Sizes are in world units.** The SVG scales the whole track to the window, and a dot (radius
   220 dm, about 44 m across) scales with it. Lines are the exception: they use
   `vector-effect: non-scaling-stroke`, so the circuit is the same 6 px wide at any size.
4. **The loader is passed in.** `App` takes an optional `load` function, which defaults to
   downloading Monza; `loadRace` takes `fetch` the same way. Tests swap in their own and need no
   network, like the swappable transports on the Python side.
5. **A late download is ignored.** The effect that downloads the race clears a flag in its
   cleanup. If `load` changes, or the page goes away, before the download finishes, the old result
   is dropped instead of replacing newer state. A test proves it: it fails when the flag is
   removed.
6. **A car with no samples is left out.** The export never writes one and `parseRace` rejects it,
   but the `Car` type allows empty columns, so `RaceView` checks instead of assuming.
7. **Dots overlap.** At the start, 20 cars sit within about 200 m on the grid, so their numbers
   cover each other. Spreading labels apart is P5.7 (label collisions).
8. **Left for later** (from the P1.3 code review):
   - *P1.7:* the cleanup ignores a late download but doesn't cancel it, so it still finishes and
     runs the check. That only costs anything when `load` changes mid-download, which doesn't
     happen yet, and in development, where `StrictMode` runs the effect twice. Cancelling means
     passing an `AbortController`'s signal down to `fetch`, combined with the timeout.
   - *P1.7:* the check itself (below).
   - *P4.8 (scrubber and race choice):* when `load` changes, the old race stays on screen until
     the new one arrives. It should go back to "loading" once there's a way to pick another race.

### Measured (Monza)

| | |
|---|---|
| `JSON.parse` of the race file | about 40 ms |
| zod check and undoing the deltas | 310 to 400 ms (Node 22 on this laptop; Chrome runs the same V8 engine) |
| Bundle | 312.5 kB JS (95.3 kB gzipped); zod adds 92.6 kB (26.5 kB gzipped) |
| `pnpm check` | 49 tests, 100% coverage |

The check is the slow part, because zod looks at each of about a million integers one at a time.
It's a one-off cost at load, not per frame. P1.7 decides whether a faster check (for example one
plain loop per column) is worth it.

## Playing the race (P1.4)

The cars now move. Three pieces, each tested on its own:

- **`PlaybackClock`** turns wall time into race time.
- **`CarTrack`** gives one car's position at any race time.
- **`useAnimationFrame`** runs a callback once per screen refresh.

Every frame goes through the same steps:

```mermaid
sequenceDiagram
    participant B as Browser
    participant H as useAnimationFrame
    participant V as RaceView
    participant C as PlaybackClock
    participant T as CarTrack (one per car)
    B->>H: requestAnimationFrame callback
    H->>V: onFrame()
    V->>C: time()
    C-->>V: race time in ms
    V->>V: setTime, which re-renders
    V->>T: positionAt(time)
    T-->>V: [x, y] or null
    V->>V: project, then draw a CarDot
    H->>B: requestAnimationFrame(next)
```

The clock has two states. Every change moves its anchor to now first, so race time never
jumps:

```mermaid
stateDiagram-v2
    [*] --> Paused: created at 0
    Paused --> Playing: play()
    Playing --> Paused: pause()
    Playing --> Paused: time() reaches the end
    Paused --> Paused: seek(t), setSpeed(s)
    Playing --> Playing: seek(t), setSpeed(s)
```

1. **Race time comes from one anchor.** The clock keeps "race time `anchorRace` at wall time
   `anchorWall`", and works out race time = anchorRace + (now − anchorWall) × speed. Pausing,
   seeking and changing speed first move the anchor to the current moment, so none of them makes
   the cars jump. It stops at the end and pauses there; `play()` at the end starts again from 0.
   Wall time is `performance.now()`, which, unlike `Date.now()`, never jumps when the system clock
   is set. It's passed in, so tests move time by hand.
2. **Finding a car's two samples.** `positionAt` binary-searches the car's times, O(log n), but
   first tries the pair of samples it used last time and the next pair. While playing, the next
   frame is almost always in one of those, so it's O(1) per frame; after a seek it falls back to
   the search. Between the two samples, it interpolates in a straight line. A test checks it
   against a brute-force scan over the whole Monza race, playing forwards and seeking around.
3. **When a car isn't drawn.** Before its first sample, after its last, and between two samples
   more than 5 s apart (`MAX_GAP_MS`): a gap that long means the car wasn't seen (garage, retired,
   signal lost), and sliding it across in a straight line would be wrong. Exactly on a sample, the
   car is always drawn, even next to a gap.
4. **What survives between frames.** `RaceView` runs again on every frame, so anything built in
   it would be rebuilt 60 times a second:
   - `Projection` and the `CarTrack`s are kept with `useMemo`. Losing one would only cost a
     cursor, so a cache is enough.
   - The clock is kept with a lazy `useState`, built once for the view's whole life. Rebuilding it
     would restart the race. An effect starts it when the view appears and pauses it when the view
     goes away.
   - The race time is state. `setTime` each frame is what re-renders, and React skips the render
     when the value hasn't changed, as after the clock stops at the end.
5. **The frame loop.** `useAnimationFrame` asks for a frame, and each frame asks for the next.
   Each request gets a new id, so the loop keeps the latest one for its cleanup to cancel when the
   view goes away. `useEffectEvent` (React 19.2) lets the loop always call the latest callback
   without restarting. The browser pauses `requestAnimationFrame` in a hidden tab, so a
   background tab costs nothing; the clock still runs on wall time, so the race has moved on when
   the tab comes back.
6. **Tests step frames by hand.** `setup.ts` replaces `requestAnimationFrame` with `FakeFrames`
   before every test, so no frame runs unless a test calls `step`. Real frames would arrive at
   random moments and make the `App` tests flaky.
7. **It plays on its own, at 1×.** Playback starts when the view appears. Play/pause and 10× are
   P1.5. No Monza car has a sample at exactly 0 (the first ones are 0 to 56 ms in), so the very
   first frame is empty for under a frame's time.
8. **Re-rendering every frame is a choice to check later.** 20 dots re-rendered by React 60 times
   a second is the simple way. `TrackMap` re-renders with them, because the cars are its children,
   so it keeps its circuit and pit-lane path strings with `useMemo`: the track never changes, and
   projecting its 500 points every frame would be wasted. P1.7 measures the rest, and moves the
   positions to direct DOM updates through refs if it doesn't fit in 16.7 ms.
9. **Left for later** (from the P1.4 code review):
   - *P1.5 (controls), done:* the frame loop kept running after the clock stopped at the end.
     `useAnimationFrame` now has an `active` flag, and the loop runs only while the race plays
     ([below](#controlling-the-race-p15)).
   - *P4.8 (scrubber and race choice):* the clock is built once from the first race's
     `durationMs`. A different race passed to the same `RaceView` would keep the old clock. With
     only one race that can't happen; once a race can be picked, `App` gives `RaceView` a `key`
     per race, so each race gets a new view and a new clock.
   - *Not changed:* reading samples through `sampleAt` (a checked read) instead of `t[i]!`. The
     lint rules forbid `!`, and all 20 cars still take about 2 µs a frame.

### Measured (Monza)

| | |
|---|---|
| `positionAt` for all 20 cars, one frame at 1× | about 2 µs (275,000 frames over the 76.5 min window) |
| The same at 10× (167 ms of race per frame) | about 4 µs |
| A random seek, all 20 cars | about 11 µs (binary search) |
| Bundle | 315.5 kB JS (96.3 kB gzipped), 3 kB more than P1.3 |
| `pnpm check` | 86 tests, 100% coverage |

The lookups are a tiny part of the 16.7 ms frame budget. Rendering is what P1.7 has to measure,
in a real browser.

## Controlling the race (P1.5)

A row above the track: Play/Pause, 1× and 10×, and the race time out of the race's length
(`0:42 / 1:16:32`). The space bar plays and pauses too.

The clock moved out of `RaceView` into a hook, `usePlayback`, which hands the controls what they
can do. `Controls` itself holds no state: it shows what it's given and reports clicks.

```mermaid
flowchart LR
    R["RaceView"] --> P["usePlayback<br/>the clock, time, playing, speed"]
    P --> C["PlaybackClock"]
    P --> F["useAnimationFrame<br/>active while playing"]
    R --> K["Controls<br/>buttons, space bar, race time"]
    K -->|"onPlayPause, onSpeed"| P
    R --> T["TrackMap and CarDots<br/>at playback.time"]
```

A click goes through the clock first, then into React state:

```mermaid
sequenceDiagram
    participant U as User
    participant K as Controls
    participant P as usePlayback
    participant C as PlaybackClock
    participant H as useAnimationFrame
    U->>K: click Pause, or space
    K->>P: onPlayPause()
    P->>C: pause()
    P->>P: setTime(clock.time()), setPlaying(false)
    P->>H: active = false
    H->>H: cleanup cancels the next frame
    U->>K: click Play
    K->>P: onPlayPause()
    P->>C: play()
    P->>P: setPlaying(true)
    P->>H: active = true
    H->>H: the loop starts again
```

1. **The clock holds the truth; React state copies it.** `PlaybackClock` is plain TypeScript, and
   React can't see it change. So `usePlayback` copies `time`, `playing` and `speed` into state,
   because a state change is what makes React draw again. Every action changes the clock first
   and then copies from it, so the two never disagree. The functions it returns are typed as
   arrow-function properties, not methods: they're passed around on their own as click handlers,
   and the `unbound-method` lint rule only trusts that for functions that don't use `this`.
2. **The frame loop runs only while playing.** `useAnimationFrame(onFrame, active)` has `active`
   in its effect's dependencies. When it turns false, React runs the cleanup, which cancels the
   pending frame, and the new run starts nothing. A paused race asks for no frames at all. The
   clock pauses itself at the end of the race, so each frame also copies `clock.playing`, and the
   loop stops there too. Play at the end starts again from 0 (the P1.4 rule), and the time is
   copied at once, so the display goes back to 0:00 without waiting for a frame.
3. **The space bar.** One `keydown` listener on `window`, so space works wherever the focus is.
   It's added once: `useEffectEvent` gives it the latest `onPlayPause` without adding it again
   every render. It skips:
   - other keys, and a held-down space (`event.repeat`), which would toggle many times a second;
   - space on a focused button, because the browser already clicks that button on space, and
     toggling as well would undo the click.

   Otherwise it calls `preventDefault()`, because space also scrolls the page down.
4. **Accessibility.**
   - The row is `role="group"` named "Playback", so a screen reader announces the buttons as a set.
   - The speed buttons carry `aria-pressed`, so "1×, pressed" is read out. The style for the speed
     that's on comes from the same attribute (`button[aria-pressed='true']`), so what's seen and
     what's heard can't drift apart.
   - The race time is a plain `<span>`, not an `<output>`. `<output>` is a live region, and a
     screen reader would read the time out every second.
   - The Play/Pause label says what a click will do, the usual pattern for a toggle.
5. **Race time.** `formatRaceTime` rounds down to the second, as timing screens do: `m:ss` under
   an hour, `h:mm:ss` from one. A negative, `NaN` or infinite time is a bug upstream, so it throws
   a `RangeError` instead of showing nonsense. The digits use `tabular-nums`, so the time doesn't
   wobble as it counts, and the buttons have a minimum width, so the row doesn't shift when Play
   becomes Pause.
6. **Testing like a user.** The `Controls` tests use user-event, which clicks and presses keys the
   way a browser does: focus moves, and space on a focused button clicks it. Two checks need
   `fireEvent` instead, because it returns whether the event was cancelled: that space doesn't
   scroll the page, and that space on a focused button is left alone. Mutation testing found both
   were untested before those two were written. One `RaceView` test goes through the real
   buttons: pause holds the cars still, and 10× moves them 200 ms of race in 20 ms.
7. **Left for later:**
   - *P4.8 (scrubber):* a seek bar will be an `<input type="range">`, which uses the arrow keys,
     not space; the space check stays as it is unless the scrubber needs it.
   - *P5.9 (mobile and accessibility):* keyboard shortcuts for the speeds, and checking the row
     with a real screen reader.

### Measured (Monza)

| | |
|---|---|
| Bundle | 317.0 kB JS (96.9 kB gzipped), 1.5 kB more than P1.4; CSS 1.0 kB |
| `pnpm check` | 113 tests, 100% coverage; mutation testing caught all 13 mutants in the new code |

## Measured (P1.2, empty app)

| | |
|---|---|
| `pnpm check` | 15.2 s |
| `pnpm build` | 4.5 s |
| Bundle | 219.9 kB JS (68.8 kB gzipped), almost all React itself |
| `node_modules` | 167 MB, 238 packages; none ships to the browser except React |
