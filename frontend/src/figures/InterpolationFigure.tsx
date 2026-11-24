import type { Car, Point } from '../race/load'
import { CarTrack } from '../replay/carTrack'
import { catmullRom, linear, sampleAt } from '../replay/interpolate'
import type { Projection } from '../track/projection'

const WIDTH = 720
const HEIGHT = 480
const PAD = 24
/** room at the top for the title and the legend */
const TOP = 88
/** how often the two lines are drawn between samples */
const STEP_MS = 10

// Okabe-Ito blue and vermillion, which colour-blind readers can tell apart; lighter in dark mode.
// The straight line is dashed as well, so the two never differ by colour alone.
const STYLE = `
svg { --paper: #ffffff; --ink: #1f2328; --muted: #59636e; --curve: #0072b2; --line: #d55e00; }
@media (prefers-color-scheme: dark) {
  svg { --paper: #0d1117; --ink: #e6edf3; --muted: #9198a1; --curve: #56b4e9; --line: #e69f00; }
}
text { font: 14px system-ui, sans-serif; fill: var(--muted); }
.title { font-size: 16px; font-weight: 600; fill: var(--ink); }
.curve, .line { fill: none; stroke-width: 2.5; stroke-linejoin: round; }
.curve { stroke: var(--curve); }
.line { stroke: var(--line); stroke-dasharray: 6 4; }
.sample { fill: var(--ink); }
.scale { stroke: var(--ink); stroke-width: 2; }
`

interface InterpolationFigureProps {
  readonly car: Car
  readonly projection: Projection
  /** the first and the last of the car's samples to draw */
  readonly first: number
  readonly last: number
}

/**
 * One car through one corner: its samples, the straight lines between them, and the Catmull-Rom
 * curve through them, both drawn by the same `CarTrack` the race view uses. A standalone SVG for
 * docs/figures, written by `pnpm figure`.
 */
export function InterpolationFigure({ car, projection, first, last }: InterpolationFigureProps) {
  const from = sampleAt(car.t, first)
  const to = sampleAt(car.t, last)
  if (!(from < to)) {
    throw new RangeError(`samples ${String(first)} to ${String(last)} run backwards`)
  }
  // where the track puts the car every STEP_MS; a gap would need a break in the line, so the
  // figure is only drawn where there's none
  const on = (track: CarTrack): Point[] => {
    const points: Point[] = []
    const steps = Math.ceil((to - from) / STEP_MS)
    // the last step lands exactly on the last sample, even when it's not a whole STEP_MS on
    for (let k = 0; k <= steps; k++) {
      const ms = Math.min(from + k * STEP_MS, to)
      const position = track.positionAt(ms)
      if (position === null) {
        throw new RangeError(`car ${String(car.number)} wasn't seen at ${String(ms)} ms`)
      }
      points.push(projection.project(...position))
    }
    return points
  }
  const curve = on(new CarTrack(car, catmullRom))
  const line = on(new CarTrack(car, linear))
  const samples: Point[] = []
  for (let i = first; i <= last; i++) {
    samples.push(projection.project(sampleAt(car.x, i), sampleAt(car.y, i)))
  }
  // the curve can bulge past the samples, so it's fitted in too
  const { toPixels, perMetre } = fit([...samples, ...curve, ...line])
  const name = `Car ${String(car.number)} (${car.acronym})`
  const title = `${name} through a corner, ${String(samples.length)} samples`
  const description = `${title}: straight lines between them cut the corner, the curve follows it`
  const path = (points: Point[]) =>
    points
      .map((point, i) => {
        const [x, y] = toPixels(point)
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`
      })
      .join(' ')

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${String(WIDTH)} ${String(HEIGHT)}`}
      role="img"
      aria-label={description}
    >
      <style>{STYLE}</style>
      <rect width={WIDTH} height={HEIGHT} fill="var(--paper)" />
      <text className="title" x={PAD} y={PAD + 8}>
        {title}
      </text>
      <g transform={`translate(${String(PAD)} ${String(PAD + 36)})`}>
        <circle className="sample" cx={6} cy={-5} r={4} />
        <text x={18} y={0}>
          samples
        </text>
        <path className="line" d="M100 -5 H136" />
        <text x={144} y={0}>
          straight lines (linear)
        </text>
        <path className="curve" d="M320 -5 H356" />
        <text x={364} y={0}>
          Catmull-Rom
        </text>
      </g>
      <path className="line" d={path(line)} />
      <path className="curve" d={path(curve)} />
      <g transform={`translate(${String(PAD)} ${String(HEIGHT - PAD)})`}>
        <path className="scale" d={`M0 0 H${String(perMetre)}`} />
        <text x={0} y={-8}>
          1 m
        </text>
      </g>
      {samples.map((point, i) => {
        const [x, y] = toPixels(point)
        return <circle key={i} className="sample" cx={x} cy={y} r={4} />
      })}
    </svg>
  )
}

/**
 * Placing points (in dm) into the drawing area, scaled to fill it and keeping their shape, and how
 * many pixels a metre comes to.
 */
function fit(points: readonly Point[]) {
  const xs = points.map(([x]) => x)
  const ys = points.map(([, y]) => y)
  const [minX, minY] = [Math.min(...xs), Math.min(...ys)]
  const [spanX, spanY] = [Math.max(...xs) - minX, Math.max(...ys) - minY]
  const [width, height] = [WIDTH - 2 * PAD, HEIGHT - TOP - PAD]
  const scale = Math.min(width / spanX, height / spanY)
  // centered in the drawing area
  const left = PAD + (width - spanX * scale) / 2
  const top = TOP + (height - spanY * scale) / 2
  return {
    toPixels: ([x, y]: Point): Point => [left + (x - minX) * scale, top + (y - minY) * scale],
    perMetre: 10 * scale,
  }
}
