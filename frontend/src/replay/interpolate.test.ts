import { describe, expect, it } from 'vitest'

import { linear, sampleAt } from './interpolate'

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
