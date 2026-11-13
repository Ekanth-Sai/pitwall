import { z } from 'zod'

// The race file made by `make export` (docs/design/replay.md). It's checked here at the
// boundary, so the rest of the app can trust its types.

export class ReplayError extends Error {
  override name = 'ReplayError'
}

/** At most this many problems go into the error message: a broken export can have a million. */
const MAX_ISSUES = 5

const point = z.tuple([z.number(), z.number()])
const deltas = z.array(z.int())

const trackSchema = z.object({
  format: z.literal(1),
  rotation: z.number(),
  bounds: z
    .tuple([z.number(), z.number(), z.number(), z.number()])
    .refine(([minX, minY, maxX, maxY]) => minX < maxX && minY < maxY, {
      message: 'bounds must be [minX, minY, maxX, maxY] with min below max',
    }),
  circuit: z.array(point).min(3),
  pit_lane: z.array(point).min(2).nullable(),
})

const carSchema = z
  .object({
    number: z.int().positive(),
    acronym: z.string(),
    name: z.string(),
    team: z.string(),
    colour: z.string().regex(/^[0-9A-F]{6}$/),
    ink: z.enum(['black', 'white']),
    t: deltas.min(1),
    x: deltas,
    y: deltas,
  })
  .refine((car) => car.x.length === car.t.length && car.y.length === car.t.length, {
    message: 't, x and y must have the same length',
  })
  // t[0] is the first time itself, the rest are steps between samples
  .refine((car) => car.t.every((dt, i) => (i === 0 ? dt >= 0 : dt > 0)), {
    message: 'times must start at 0 or later and strictly increase',
  })

const raceSchema = z
  .object({
    format: z.literal(1),
    session: z.object({ name: z.string(), location: z.string(), year: z.int() }),
    // exactly 3 fraction digits: the one form every browser's Date is sure to read
    start: z.iso.datetime({ offset: true, precision: 3 }),
    duration_ms: z.int().positive(),
    track: trackSchema,
    cars: z.array(carSchema).min(1),
  })
  .refine((race) => new Set(race.cars.map((car) => car.number)).size === race.cars.length, {
    message: 'car numbers must be unique',
    path: ['cars'],
  })
  .refine((race) => race.cars.every((car) => sum(car.t) <= race.duration_ms), {
    message: 'every sample must be within duration_ms',
    path: ['cars'],
  })

export type Point = readonly [number, number]
export type Bounds = readonly [number, number, number, number]

export interface Track {
  readonly rotation: number
  readonly bounds: Bounds
  readonly circuit: readonly Point[]
  readonly pitLane: readonly Point[] | null
}

export interface Car {
  readonly number: number
  readonly acronym: string
  readonly name: string
  readonly team: string
  readonly colour: string
  readonly ink: 'black' | 'white'
  readonly t: Float64Array
  readonly x: Float64Array
  readonly y: Float64Array
}

export interface Race {
  readonly name: string
  readonly location: string
  readonly year: number
  readonly start: Date
  readonly durationMs: number
  readonly track: Track
  readonly cars: readonly Car[]
}

function sum(values: readonly number[]): number {
  return values.reduce((total, v) => total + v, 0)
}

/**
 * True for the error AbortSignal.timeout raises. It's checked by name, not with instanceof:
 * DOMException isn't always an Error subclass, and test runtimes have more than one DOMException.
 */
function isTimeout(error: unknown): boolean {
  return (
    typeof error === 'object' && error !== null && 'name' in error && error.name === 'TimeoutError'
  )
}

/** Running sum: [5, 1, 2] becomes [5, 6, 8]. */
export function undelta(values: readonly number[]): Float64Array {
  const out = new Float64Array(values.length)
  let sum = 0
  values.forEach((v, i) => {
    sum += v
    out[i] = sum
  })
  return out
}

/** Checks parsed JSON and turns it into a Race, or throws ReplayError. */
export function parseRace(data: unknown): Race {
  const result = raceSchema.safeParse(data)
  if (!result.success) {
    const { issues } = result.error
    const shown = z.prettifyError(new z.ZodError(issues.slice(0, MAX_ISSUES)))
    const more =
      issues.length > MAX_ISSUES ? `\n(and ${String(issues.length - MAX_ISSUES)} more)` : ''
    throw new ReplayError(`race file is not valid:\n${shown}${more}`)
  }
  const race = result.data
  return {
    name: race.session.name,
    location: race.session.location,
    year: race.session.year,
    start: new Date(race.start),
    durationMs: race.duration_ms,
    track: {
      rotation: race.track.rotation,
      bounds: race.track.bounds,
      circuit: race.track.circuit,
      pitLane: race.track.pit_lane,
    },
    cars: race.cars.map((car) => ({
      number: car.number,
      acronym: car.acronym,
      name: car.name,
      team: car.team,
      colour: `#${car.colour}`,
      ink: car.ink,
      t: undelta(car.t),
      x: undelta(car.x),
      y: undelta(car.y),
    })),
  }
}

/** Downloads and checks a race file. `fetchFn` is swappable so tests need no network. */
export async function loadRace(
  url: string,
  fetchFn: typeof fetch = fetch,
  timeoutMs = 30_000,
): Promise<Race> {
  let response: Response
  try {
    response = await fetchFn(url, { signal: AbortSignal.timeout(timeoutMs) })
  } catch (e) {
    const why = isTimeout(e) ? `timed out after ${String(timeoutMs)} ms` : String(e)
    throw new ReplayError(`could not download ${url}: ${why}`, { cause: e })
  }
  if (!response.ok) {
    throw new ReplayError(`could not download ${url}: HTTP ${String(response.status)}`)
  }
  let data: unknown
  try {
    data = await response.json()
  } catch (e) {
    // the timeout also covers reading the body, which can be slow on a slow connection
    if (isTimeout(e)) {
      throw new ReplayError(`could not download ${url}: timed out after ${String(timeoutMs)} ms`, {
        cause: e,
      })
    }
    throw new ReplayError(`${url} is not valid JSON`, { cause: e })
  }
  return parseRace(data)
}
