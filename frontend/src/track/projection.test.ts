import { describe, expect, it } from 'vitest'

import monza from '../../public/races/monza-2024.json?raw'
import { parseRace } from '../race/load'
import { Projection } from './projection'

const square = [0, 0, 10, 10] as const

describe('Projection.project', () => {
  it('only flips y when there is no rotation', () => {
    expect(new Projection(0, square).project(3, 4)).toEqual([3, -4])
  })

  it('rotates counter-clockwise before flipping', () => {
    // (1, 0) turned 90 degrees is (0, 1): up in the world, so up (negative y) on screen
    const [x, y] = new Projection(90, square).project(1, 0)
    expect(x).toBeCloseTo(0)
    expect(y).toBeCloseTo(-1)
  })
})

describe('Projection.viewBox', () => {
  it('covers the flipped bounds plus the margin', () => {
    expect(new Projection(0, [-5, 2, 15, 12]).viewBox(1)).toBe('-6.0 -13.0 22.0 12.0')
  })

  it('rejects empty bounds', () => {
    expect(() => new Projection(0, [0, 0, 0, 10])).toThrow(RangeError)
    expect(() => new Projection(0, [0, 5, 10, 5])).toThrow(RangeError)
  })
})

describe('Projection.path', () => {
  it('moves to the first point and draws lines to the rest', () => {
    const path = new Projection(0, square).path(
      [
        [0, 0],
        [10, 0],
        [10, 10],
      ],
      false,
    )
    expect(path).toBe('M0.0 0.0 L10.0 0.0 L10.0 -10.0')
  })

  it('closes a loop with Z', () => {
    const path = new Projection(0, square).path(
      [
        [0, 0],
        [1, 1],
      ],
      true,
    )
    expect(path).toMatch(/ Z$/)
  })
})

describe('Projection on the Monza export', () => {
  // The python export rotated the outline to get `bounds`. If this rotation matches it, every
  // projected point lands inside the viewBox, and the extremes touch its edges.
  const race = parseRace(JSON.parse(monza))
  const { rotation, bounds, circuit, pitLane } = race.track
  const projection = new Projection(rotation, bounds)
  const points = [...circuit, ...(pitLane ?? [])].map(([x, y]) => projection.project(x, y))
  const xs = points.map(([x]) => x)
  const ys = points.map(([, y]) => y)

  it('matches the bounds the Python export computed', () => {
    const [minX, minY, maxX, maxY] = bounds
    expect(Math.min(...xs)).toBeCloseTo(minX, 0)
    expect(Math.max(...xs)).toBeCloseTo(maxX, 0)
    expect(Math.min(...ys)).toBeCloseTo(-maxY, 0)
    expect(Math.max(...ys)).toBeCloseTo(-minY, 0)
  })

  it('lays the track out landscape', () => {
    const [, , width, height] = projection.viewBox(0).split(' ').map(Number)
    expect(width).toBeGreaterThan(2 * (height ?? 0))
  })
})
