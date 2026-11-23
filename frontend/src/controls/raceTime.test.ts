import { describe, expect, it } from 'vitest'

import { formatRaceTime } from './raceTime'

describe('formatRaceTime', () => {
  it.each([
    [0, '0:00'],
    [999, '0:00'],
    [59_999, '0:59'],
    [61_000, '1:01'],
    [3_599_999, '59:59'],
    [3_600_000, '1:00:00'],
    [4_590_500, '1:16:30'],
  ])('shows %i ms as %s', (ms, shown) => {
    expect(formatRaceTime(ms)).toBe(shown)
  })

  it.each([-1, Number.NaN, Number.POSITIVE_INFINITY])('rejects %s', (ms) => {
    expect(() => formatRaceTime(ms)).toThrow(RangeError)
  })
})
