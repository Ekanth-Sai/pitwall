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

/**
 * A smooth curve through the samples: non-uniform Catmull-Rom, in the Barry-Goldman form.
 *
 * It bends to follow `before` and `after` as well as the pair, so the car takes corners instead of
 * cutting them, and still passes through every sample. The knots are the samples' own times, not
 * 0, 1, 2, 3: OpenF1's samples aren't evenly spaced, and a car covers more ground in a longer
 * interval. Where there's no sample beside the pair, a mirror image of the pair's other end stands
 * in, which makes the curve a straight line there.
 */
export const catmullRom: Interpolator = (samples, ms, from, to, before, after) => {
  const around = (values: Float64Array): Four => [
    outer(values, from, to, before),
    sampleAt(values, from),
    sampleAt(values, to),
    outer(values, to, from, after),
  ]
  const knots = around(samples.t)
  return [barryGoldman(around(samples.x), knots, ms), barryGoldman(around(samples.y), knots, ms)]
}

type Four = readonly [number, number, number, number]

/** values[beside]; or if there's none (`beside` is `i`), values[other] mirrored in values[i]. */
function outer(values: Float64Array, i: number, other: number, beside: number): number {
  const value = sampleAt(values, i)
  return beside === i ? 2 * value - sampleAt(values, other) : sampleAt(values, beside)
}

/**
 * Four values at four times, and the curve through them at time `ms` (between the middle two).
 * Three rounds of straight-line blends, each over a wider span of time: the pyramid in
 * docs/design/frontend.md.
 */
function barryGoldman([p0, p1, p2, p3]: Four, [t0, t1, t2, t3]: Four, ms: number): number {
  const a1 = blend(p0, t0, p1, t1, ms)
  const a2 = blend(p1, t1, p2, t2, ms)
  const a3 = blend(p2, t2, p3, t3, ms)
  const b1 = blend(a1, t0, a2, t2, ms)
  const b2 = blend(a2, t1, a3, t3, ms)
  return blend(b1, t1, b2, t2, ms)
}

/** The value at time `ms` on the straight line through `a` at time `ta` and `b` at time `tb`. */
function blend(a: number, ta: number, b: number, tb: number, ms: number): number {
  return a + ((b - a) * (ms - ta)) / (tb - ta)
}
