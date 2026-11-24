import { describe, expect, it } from 'vitest'

import { catmullRom, linear, type Samples, sampleAt } from './interpolate'

describe('sampleAt', () => {
  it('reads a sample', () => {
    expect(sampleAt(Float64Array.from([4, 7]), 1)).toBe(7)
  })

  it('rejects an index outside the samples', () => {
    expect(() => sampleAt(Float64Array.from([4, 7]), 2)).toThrow('no sample 2 in 2')
  })
})

describe('linear', () => {
  // three samples: along x, then a turn up in y
  const samples = {
    t: Float64Array.from([0, 100, 300]),
    x: Float64Array.from([0, 1000, 1000]),
    y: Float64Array.from([0, 0, 400]),
  }

  it('moves in a straight line at a constant speed', () => {
    expect(linear(samples, 25, 0, 1, 0, 2)).toEqual([250, 0])
    expect(linear(samples, 250, 1, 2, 0, 2)).toEqual([1000, 300])
  })

  it('goes to the sample it is given, not just the next one', () => {
    expect(linear(samples, 150, 0, 2, 0, 2)).toEqual([500, 200])
  })

  it('pays no attention to the samples either side', () => {
    expect(linear(samples, 150, 1, 2, 1, 2)).toEqual(linear(samples, 150, 1, 2, 0, 2))
  })
})

describe('catmullRom', () => {
  // samples at uneven times, as OpenF1's are
  const times = [0, 90, 250, 330, 500, 620, 700]

  function along(path: (ms: number) => readonly [number, number]): Samples {
    return {
      t: Float64Array.from(times),
      x: Float64Array.from(times, (ms) => path(ms)[0]),
      y: Float64Array.from(times, (ms) => path(ms)[1]),
    }
  }

  // a car going round a circle of radius 1000 dm, half a lap every 600 ms
  const circle = (ms: number) =>
    [1000 * Math.cos((Math.PI * ms) / 600), 1000 * Math.sin((Math.PI * ms) / 600)] as const

  it('passes through every sample', () => {
    const samples = along(circle)
    for (let i = 1; i + 2 < times.length; i++) {
      const [t1, t2] = [samples.t[i] ?? 0, samples.t[i + 1] ?? 0]
      const start = catmullRom(samples, t1, i, i + 1, i - 1, i + 2)
      const end = catmullRom(samples, t2, i, i + 1, i - 1, i + 2)
      expect(start[0]).toBeCloseTo(samples.x[i] ?? 0, 9)
      expect(start[1]).toBeCloseTo(samples.y[i] ?? 0, 9)
      expect(end[0]).toBeCloseTo(samples.x[i + 1] ?? 0, 9)
      expect(end[1]).toBeCloseTo(samples.y[i + 1] ?? 0, 9)
    }
  })

  it('keeps a straight line at a constant speed exact, with or without samples beside', () => {
    const samples = along((ms) => [3 * ms - 40, 500 - 2 * ms])
    for (const [before, after] of [
      [1, 4],
      [2, 4],
      [1, 3],
      [2, 3],
    ] as const) {
      const [x, y] = catmullRom(samples, 300, 2, 3, before, after)
      expect(x).toBeCloseTo(3 * 300 - 40, 9)
      expect(y).toBeCloseTo(500 - 2 * 300, 9)
    }
  })

  it('stays much closer to a curve than a straight line does', () => {
    const samples = along(circle)
    let worstCurve = 0
    let worstLine = 0
    for (let i = 1; i + 2 < times.length; i++) {
      const [t1, t2] = [samples.t[i] ?? 0, samples.t[i + 1] ?? 0]
      for (let k = 1; k < 10; k++) {
        const ms = t1 + ((t2 - t1) * k) / 10
        const [x, y] = circle(ms)
        const curve = catmullRom(samples, ms, i, i + 1, i - 1, i + 2)
        const line = linear(samples, ms, i, i + 1, i - 1, i + 2)
        worstCurve = Math.max(worstCurve, Math.hypot(curve[0] - x, curve[1] - y))
        worstLine = Math.max(worstLine, Math.hypot(line[0] - x, line[1] - y))
      }
    }
    // measured: about 10 dm against 97 dm
    expect(worstCurve).toBeLessThan(worstLine / 5)
  })

  it('is the textbook uniform Catmull-Rom when the samples are evenly spaced', () => {
    const [p0, p1, p2, p3] = [0, 10, 30, 70]
    const samples = {
      t: Float64Array.from([0, 100, 200, 300]),
      x: Float64Array.from([p0, p1, p2, p3]),
      y: Float64Array.from([-p0, -p1, -p2, -p3]),
    }
    // the usual matrix form, a quarter of the way from p1 to p2
    const u = 0.25
    const textbook =
      0.5 *
      (2 * p1 +
        (p2 - p0) * u +
        (2 * p0 - 5 * p1 + 4 * p2 - p3) * u ** 2 +
        (3 * p1 - p0 - 3 * p2 + p3) * u ** 3)
    const [x, y] = catmullRom(samples, 125, 1, 2, 0, 3)
    expect(x).toBeCloseTo(textbook, 9)
    expect(y).toBeCloseTo(-textbook, 9)
  })
})
