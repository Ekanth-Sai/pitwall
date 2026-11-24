import { describe, expect, it, vi } from 'vitest'

import monza from '../../public/races/monza-2024.json?raw'
import { parseRace } from '../race/load'
import { CarTrack, MAX_GAP_MS } from './carTrack'
import type { Interpolator } from './interpolate'

// A car with samples at the given times, moving 10 dm in x per ms and staying at y = 5.
function track(times: number[]): CarTrack {
  return new CarTrack({
    t: Float64Array.from(times),
    x: Float64Array.from(times, (t) => t * 10),
    y: Float64Array.from(times, () => 5),
  })
}

describe('CarTrack.positionAt', () => {
  it('is exact at every sample', () => {
    const car = track([0, 100, 250, 400])
    for (const t of [0, 100, 250, 400]) {
      expect(car.positionAt(t)).toEqual([t * 10, 5])
    }
  })

  it('moves in a straight line between samples', () => {
    const car = track([0, 100, 300])
    expect(car.positionAt(50)).toEqual([500, 5])
    expect(car.positionAt(150)).toEqual([1500, 5])
  })

  it('hides the car before its first sample and after its last', () => {
    const car = track([100, 200])
    expect(car.positionAt(99)).toBeNull()
    expect(car.positionAt(201)).toBeNull()
  })

  it('hides the car across a long gap, but not at its edges', () => {
    const after = 100 + MAX_GAP_MS + 1
    const car = track([0, 100, after, after + 100])
    expect(car.positionAt(200)).toBeNull()
    // straight from inside the gap to the sample that ends it, as the next frame would
    expect(car.positionAt(after)).toEqual([after * 10, 5])
    expect(car.positionAt(100)).toEqual([1000, 5])
    expect(car.positionAt(after + 50)).toEqual([(after + 50) * 10, 5])
  })

  it('keeps the car across a gap of exactly the limit', () => {
    expect(track([0, MAX_GAP_MS]).positionAt(1)).toEqual([10, 5])
  })

  it('stays right when time goes backwards after a seek', () => {
    const car = track([0, 100, 200, 300, 400])
    expect(car.positionAt(350)).toEqual([3500, 5])
    expect(car.positionAt(50)).toEqual([500, 5])
    expect(car.positionAt(250)).toEqual([2500, 5])
  })

  it('has no position for a car with no samples', () => {
    expect(track([]).positionAt(0)).toBeNull()
  })

  it('rejects columns of different lengths', () => {
    const t = Float64Array.from([0, 1])
    expect(() => new CarTrack({ t, x: t, y: Float64Array.from([0]) })).toThrow(RangeError)
  })

  it('hands the interpolator the pair around the time and the samples either side', () => {
    const car = {
      t: Float64Array.from([0, 100, 200, 300]),
      x: new Float64Array(4),
      y: new Float64Array(4),
    }
    const interpolate = vi.fn<Interpolator>(() => [1, 2])
    const positions = new CarTrack(car, interpolate)
    expect(positions.positionAt(150)).toEqual([1, 2])
    expect(interpolate).toHaveBeenLastCalledWith(car, 150, 1, 2, 0, 3)
    // at the first and last pair there's nothing further out, so the pair's own end is repeated
    positions.positionAt(50)
    expect(interpolate).toHaveBeenLastCalledWith(car, 50, 0, 1, 0, 2)
    positions.positionAt(250)
    expect(interpolate).toHaveBeenLastCalledWith(car, 250, 2, 3, 1, 3)
    // on a sample it isn't asked at all
    interpolate.mockClear()
    positions.positionAt(200)
    expect(interpolate).not.toHaveBeenCalled()
  })

  it("doesn't hand the interpolator a sample across a gap", () => {
    const after = 100 + MAX_GAP_MS + 1
    const t = Float64Array.from([0, 100, after, after + 100])
    const car = { t, x: new Float64Array(4), y: new Float64Array(4) }
    const interpolate = vi.fn<Interpolator>(() => [0, 0])
    const positions = new CarTrack(car, interpolate)
    positions.positionAt(50)
    expect(interpolate).toHaveBeenLastCalledWith(car, 50, 0, 1, 0, 1)
    positions.positionAt(after + 50)
    expect(interpolate).toHaveBeenLastCalledWith(car, after + 50, 2, 3, 2, 3)
  })

  it('hands the interpolator a sample exactly the limit away', () => {
    const t = Float64Array.from([0, MAX_GAP_MS, MAX_GAP_MS + 100, 2 * MAX_GAP_MS + 100])
    const car = { t, x: new Float64Array(4), y: new Float64Array(4) }
    const interpolate = vi.fn<Interpolator>(() => [0, 0])
    new CarTrack(car, interpolate).positionAt(MAX_GAP_MS + 50)
    expect(interpolate).toHaveBeenLastCalledWith(car, MAX_GAP_MS + 50, 1, 2, 0, 3)
  })

  it('agrees with a plain scan on the real race, playing forwards and seeking around', () => {
    const car = parseRace(JSON.parse(monza)).cars[0]
    if (car === undefined) {
      throw new Error('the Monza file has no cars')
    }
    const { t, x, y } = car
    const fast = new CarTrack(car)

    // the same answer found the slow way: try every pair of samples, then use just that pair
    function scan(ms: number) {
      for (let i = 0; i + 1 < t.length; i++) {
        if ((t[i] ?? 0) <= ms && ms < (t[i + 1] ?? 0)) {
          const pair = { t: t.subarray(i, i + 2), x: x.subarray(i, i + 2), y: y.subarray(i, i + 2) }
          return new CarTrack(pair).positionAt(ms)
        }
      }
      return null
    }

    // forwards in steps of one frame at 10x speed (167 ms), then jumps back and forth
    const end = t[t.length - 1] ?? 0
    const times = Array.from({ length: 2000 }, (_, k) => 56 + k * 167)
    times.push(end * 0.9, end * 0.1, end * 0.5, end * 0.49, end * 0.75)
    for (const ms of times) {
      expect(fast.positionAt(ms)).toEqual(scan(ms))
    }
  })
})
