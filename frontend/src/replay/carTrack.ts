import type { Point } from '../race/load'
import { type Interpolator, linear, sampleAt, type Samples } from './interpolate'

/**
 * Two samples further apart than this mean the car wasn't seen in between (in the garage, retired,
 * or the signal dropped). The car is hidden there instead of sliding in a straight line across.
 */
export const MAX_GAP_MS = 5000

/**
 * One car's position at any race time, between its samples, by an `Interpolator` (a straight line
 * unless told otherwise).
 *
 * Finding the two samples around a time is a binary search, O(log n). During playback the next
 * frame's time is almost always in the same pair of samples or the next one, so the last answer is
 * kept as a `cursor` and tried first: O(1) per frame while playing, and still right after a seek.
 */
export class CarTrack {
  private readonly samples: Samples
  private readonly t: Float64Array
  private readonly interpolate: Interpolator
  private cursor = 0

  constructor(car: Samples, interpolate: Interpolator = linear) {
    if (car.t.length !== car.x.length || car.t.length !== car.y.length) {
      throw new RangeError('t, x, and y must have the same length')
    }
    this.samples = car
    this.t = car.t
    this.interpolate = interpolate
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
      return [sampleAt(this.samples.x, i), sampleAt(this.samples.y, i)]
    }
    if (sampleAt(this.t, i + 1) - t0 > MAX_GAP_MS) {
      return null
    }
    const before = this.beside(i, i - 1)
    const after = this.beside(i + 1, i + 2)
    return this.interpolate(this.samples, ms, i, i + 1, before, after)
  }

  /** Sample `next`, beside sample `i`, if there is one and it isn't across a gap; otherwise `i`. */
  private beside(i: number, next: number): number {
    if (next < 0 || next >= this.t.length) {
      return i
    }
    return Math.abs(sampleAt(this.t, next) - sampleAt(this.t, i)) > MAX_GAP_MS ? i : next
  }

  /** The index i with t[i] <= ms < t[i + 1]. `ms` is within the samples and before the last one. */
  private segmentAt(ms: number, last: number): number {
    // the usual case while playing: the same pair as the last frame, or the next one
    for (let i = this.cursor; i <= this.cursor + 1; i++) {
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
}
