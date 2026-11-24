import type { Car, Point } from '../race/load'

/** One car's samples, one column each: race time in ms, and position in dm. */
export type Samples = Pick<Car, 't' | 'x' | 'y'>

/** values[i], for an index already checked by the caller. Outside, typed arrays give undefined. */
export function sampleAt(values: Float64Array, i: number): number {
  const value = values[i]
  if (value === undefined) {
    throw new RangeError(`no sample ${String(i)} in ${String(values.length)}`)
  }
  return value
}

/**
 * Where a car is at race time `ms`, between samples `from` and `to`, with t[from] < ms < t[to].
 *
 * `before` and `after` are the samples either side of that pair, so a curve can see which way the
 * car was heading. Where there is none to use (the car's first or last sample, or one across a
 * gap), they're `from` and `to` themselves. A straight line doesn't need them.
 */
export type Interpolator = (
  samples: Samples,
  ms: number,
  from: number,
  to: number,
  before: number,
  after: number,
) => Point

/** A straight line from sample `from` to sample `to`, at a constant speed. */
export const linear: Interpolator = (samples, ms, from, to) => {
  const t0 = sampleAt(samples.t, from)
  const f = (ms - t0) / (sampleAt(samples.t, to) - t0)
  return [lerp(samples.x, from, to, f), lerp(samples.y, from, to, f)]
}

/** The value fraction `f` of the way from sample `from` to sample `to`. */
function lerp(values: Float64Array, from: number, to: number, f: number): number {
  const a = sampleAt(values, from)
  return a + (sampleAt(values, to) - a) * f
}
