import type { Car, Point } from '../race/load'

/**
 * Two samples further apart than this mean the car wasn't seen in between (in the garage, retired,
 * or the signal dropped). The car is hidden there instead of sliding in a straight line across.
 */
export const MAX_GAP_MS = 5000

/** values[i], for an index already checked by the caller. Outside, typed arrays give undefined. */
export function sampleAt(values: Float64Array, i: number): number {
  const value = values[i]
  if (value === undefined) {
    throw new RangeError(`no sample ${String(i)} in ${String(values.length)}`)
  }
  return value
}

/**
 * One car's position at any race time, interpolated linearly between its samples.
 *
 * Finding the two samples around a time is a binary search, O(log n). During playback the next
 * frame's time is almost always in the same pair of samples or the next one, so the last answer is
 * kept as a `cursor` and tried first: O(1) per frame while playing, and still right after a seek.
 */
export class CarTrack {
  private readonly t: Float64Array
  private readonly x: Float64Array
  private readonly y: Float64Array
  private cursor = 0

  constructor(car: Pick<Car, 't' | 'x' | 'y'>) {
    if (car.t.length !== car.x.length || car.t.length !== car.y.length) {
      throw new RangeError('t, x, and y must have the same length')
    }
    this.t = car.t
    this.x = car.x
    this.y = car.y
  }

  /** Where the car is at race time `ms`: null before its first sample, after its last, in a gap. */
  positionAt(ms: number): Point | null {
    const last = this.t.length - 1
    if (last < 0 || !(ms >= sampleAt(this.t, 0) && ms <= sampleAt(this.t, last))) {
      return null
    }
    // the last sample has no pair after it, so it's looked up on its own
    const i = ms === sampleAt(this.t, last) ? last : this.segmentAt(ms, last)
    const t0 = sampleAt(this.t, i)
    // on a sample, the car is exactly there, even next to a gap
    if (ms === t0) {
      return [sampleAt(this.x, i), sampleAt(this.y, i)]
    }
    const t1 = sampleAt(this.t, i + 1)
    if (t1 - t0 > MAX_GAP_MS) {
      return null
    }
    const f = (ms - t0) / (t1 - t0)
    return [this.lerp(this.x, i, f), this.lerp(this.y, i, f)]
  }

  /** The index i with t[i] <= ms < t[i + 1]. `ms` is within the samples and before the last one. */
  private segmentAt(ms: number, last: number): number {
    // the usual case while playing: the same pair as the last frame, or the next one
    for (const i of [this.cursor, this.cursor + 1]) {
      if (i < last && sampleAt(this.t, i) <= ms && ms < sampleAt(this.t, i + 1)) {
        this.cursor = i
        return i
      }
    }
    // after a seek: binary search, keeping t[lo] <= ms < t[hi]
    let lo = 0
    let hi = last
    while (hi - lo > 1) {
      const mid = (lo + hi) >>> 1
      if (sampleAt(this.t, mid) <= ms) {
        lo = mid
      } else {
        hi = mid
      }
    }
    this.cursor = lo
    return lo
  }

  /** The point fraction `f` of the way from sample i to sample i + 1. */
  private lerp(values: Float64Array, i: number, f: number): number {
    const a = sampleAt(values, i)
    return a + (sampleAt(values, i + 1) - a) * f
  }
}
