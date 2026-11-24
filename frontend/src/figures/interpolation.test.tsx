import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { Car, Race } from '../race/load'
import { MAX_GAP_MS } from '../replay/carTrack'
import { Projection } from '../track/projection'
import { interpolationFigure, sharpestTurn } from './interpolation'
import { InterpolationFigure } from './InterpolationFigure'

// a car every 200 ms, 20 m apart (360 km/h): along x to sample 5, then a right angle, then up y
const n = 11
const corner: Car = {
  number: 44,
  acronym: 'TST',
  name: 'Test DRIVER',
  team: 'Test Team',
  colour: '#3671C6',
  ink: 'white',
  t: Float64Array.from({ length: n }, (_, i) => i * 200),
  x: Float64Array.from({ length: n }, (_, i) => Math.min(i, 5) * 200),
  y: Float64Array.from({ length: n }, (_, i) => Math.max(i - 5, 0) * 200),
}

const race: Race = {
  name: 'Race',
  location: 'Monza',
  year: 2024,
  start: new Date('2024-09-01T13:03:34Z'),
  durationMs: 1000,
  track: { rotation: 0, bounds: [0, 0, 1000, 1000], circuit: [], pitLane: null },
  cars: [corner],
}

// sample times every 100 ms, and positions from a function of the sample number
function drive(position: (i: number) => readonly [number, number]) {
  return {
    t: Float64Array.from({ length: n }, (_, i) => i * 100),
    x: Float64Array.from({ length: n }, (_, i) => position(i)[0]),
    y: Float64Array.from({ length: n }, (_, i) => position(i)[1]),
  }
}

// parked, with the position jittering by a decimetre or so
const jitter = (i: number) => [i % 2, (i % 3) - 1] as const

describe('sharpestTurn', () => {
  it('finds the corner, turning left or right', () => {
    expect(sharpestTurn(corner, 0, 2000, 2)).toBe(5)
    const right = { ...corner, y: corner.y.map((y) => -y) }
    expect(sharpestTurn(right, 0, 2000, 2)).toBe(5)
  })

  it('only looks between the times it is given', () => {
    // from sample 6 on, the sharpest is 6, still turning out of the corner
    expect(sharpestTurn(corner, 1100, 2000, 2)).toBe(6)
    // up to sample 4, it's 4, already turning into it
    expect(sharpestTurn(corner, 0, 900, 2)).toBe(4)
  })

  it('takes the first of equal turns', () => {
    const straight = drive((i) => [i * 200, 0])
    expect(sharpestTurn(straight, 0, 1000, 2)).toBe(2)
  })

  it("doesn't count a car pulling away or stopping as a turn", () => {
    // parked until sample 4, then straight along x: the first turn it can judge is at 5
    const pullsAway = drive((i) => (i < 5 ? jitter(i) : [(i - 4) * 200, 0]))
    expect(sharpestTurn(pullsAway, 0, 1000, 2)).toBe(5)
    // straight along x until it stops at sample 5, then parked: only 2 to 4 have room both sides
    const stops = drive((i) =>
      i <= 6 ? [Math.min(i, 5) * 200, 0] : [1000 + jitter(i)[0], jitter(i)[1]],
    )
    expect(sharpestTurn(stops, 0, 1000, 2)).toBe(2)
  })

  it("doesn't take a car standing still for a corner", () => {
    // every "turn" of the jitter is sharp, and none is real
    const parked = drive(jitter)
    expect(() => sharpestTurn(parked, 0, 1000, 2)).toThrow('no samples between 0 and 1000 ms')
  })

  it("doesn't take going missing and coming back for a turn", () => {
    // straight along x to sample 5, then gone for over MAX_GAP_MS, back on another straight: the
    // jump looks like a sharp turn, but every sample near it has the gap within reach
    const back = drive((i) => (i <= 5 ? [i * 200, 0] : [1000 - (i - 5) * 200, 1000]))
    back.t = Float64Array.from(back.t, (t, i) => (i > 5 ? t + MAX_GAP_MS : t))
    expect(sharpestTurn(back, 0, 10_000, 1)).toBe(1)
  })

  it('throws when there are no samples between the times', () => {
    expect(() => sharpestTurn(corner, 3000, 4000, 2)).toThrow(RangeError)
  })
})

describe('interpolationFigure', () => {
  const svg = new DOMParser().parseFromString(
    interpolationFigure(race, 44, 0, 2000),
    'image/svg+xml',
  ).documentElement

  it('is a standalone SVG', () => {
    expect(svg.tagName).toBe('svg')
    expect(svg.getAttribute('xmlns')).toBe('http://www.w3.org/2000/svg')
  })

  it('draws the seven samples around the corner, both lines, the legend and a scale', () => {
    // the samples, plus the one in the legend
    expect(svg.querySelectorAll('circle.sample')).toHaveLength(8)
    // each line once in the drawing and once in the legend
    expect(svg.querySelectorAll('path.curve')).toHaveLength(2)
    expect(svg.querySelectorAll('path.line')).toHaveLength(2)
    expect(svg.querySelector('path.scale')).not.toBeNull()
    expect(svg.querySelector('.title')?.textContent).toBe(
      'Car 44 (TST) through a corner, 7 samples',
    )
  })

  it('draws the three samples either side of the sharpest turn', () => {
    const projection = new Projection(race.track.rotation, race.track.bounds)
    // from 1100 ms on, the sharpest turn is at sample 6, so the figure draws 3 to 9
    const figure = <InterpolationFigure car={corner} projection={projection} first={3} last={9} />
    expect(interpolationFigure(race, 44, 1100, 2000)).toBe(renderToStaticMarkup(figure))
  })

  it('draws the two lines differently through the corner', () => {
    const [, curve] = svg.querySelectorAll('path.curve')
    const [, line] = svg.querySelectorAll('path.line')
    expect(curve?.getAttribute('d')).not.toBe(line?.getAttribute('d'))
  })

  it('rejects a car that is not in the race', () => {
    expect(() => interpolationFigure(race, 1, 0, 2000)).toThrow('no car 1 in the race')
  })
})

describe('InterpolationFigure', () => {
  const projection = new Projection(0, [0, 0, 1000, 1000])

  it('rejects samples that run backwards', () => {
    const figure = <InterpolationFigure car={corner} projection={projection} first={5} last={3} />
    expect(() => renderToStaticMarkup(figure)).toThrow('samples 5 to 3 run backwards')
  })

  // the numbers in a path's `d`, as [x, y] pairs
  function points(d: string | null | undefined): number[][] {
    const values = (d ?? '').match(/-?\d+(\.\d+)?/g)?.map(Number) ?? []
    return values.flatMap((v, i) => (i % 2 === 0 ? [[v, values[i + 1] ?? NaN]] : []))
  }

  function draw(car: Car, first: number, last: number) {
    const markup = renderToStaticMarkup(
      <InterpolationFigure car={car} projection={projection} first={first} last={last} />,
    )
    return new DOMParser().parseFromString(markup, 'image/svg+xml').documentElement
  }

  it('takes both lines all the way to the last sample', () => {
    // 206 ms apart: the last sample, 824 ms on, isn't a whole number of 10 ms steps away
    const svg = draw({ ...corner, t: Float64Array.from(corner.t, (t) => t * 1.03) }, 3, 7)
    const dots = [...svg.querySelectorAll('circle.sample')]
    const lastDot = dots[dots.length - 1]
    for (const path of [...svg.querySelectorAll('path.curve, path.line')].slice(2)) {
      const end = points(path.getAttribute('d')).at(-1)
      expect(end?.[0]).toBeCloseTo(Number(lastDot?.getAttribute('cx')), 1)
      expect(end?.[1]).toBeCloseTo(Number(lastDot?.getAttribute('cy')), 1)
    }
  })

  it('keeps the curve inside the drawing area where it bulges past the samples', () => {
    // four samples on a tall, narrow ellipse, either side of its top: the curve rises above all of
    // them, and as the samples' height fills the drawing area, it would cross the top edge
    const angles = [45, 75, 105, 135].map((a) => (a * Math.PI) / 180)
    const arc = {
      ...corner,
      // under 30 m apart, every 500 ms: below the speed limit, so the curve uses all four
      t: Float64Array.from([0, 500, 1000, 1500]),
      x: Float64Array.from(angles, (a) => 100 * Math.cos(a)),
      y: Float64Array.from(angles, (a) => 1000 * Math.sin(a)),
    }
    const [, curve] = draw(arc, 0, 3).querySelectorAll('path.curve')
    for (const [x, y] of points(curve?.getAttribute('d'))) {
      expect(x).toBeGreaterThanOrEqual(24 - 0.05)
      expect(x).toBeLessThanOrEqual(720 - 24 + 0.05)
      expect(y).toBeGreaterThanOrEqual(88 - 0.05)
      expect(y).toBeLessThanOrEqual(480 - 24 + 0.05)
    }
  })

  it("won't draw across a gap, where the car wasn't seen", () => {
    const gap = {
      ...corner,
      t: Float64Array.from(corner.t, (t, i) => (i > 5 ? t + MAX_GAP_MS : t)),
    }
    const figure = <InterpolationFigure car={gap} projection={projection} first={3} last={7} />
    expect(() => renderToStaticMarkup(figure)).toThrow("car 44 wasn't seen at 1010 ms")
  })
})
