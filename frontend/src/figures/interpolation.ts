import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import type { Race } from '../race/load'
import { MAX_GAP_MS } from '../replay/carTrack'
import { type Samples, sampleAt } from '../replay/interpolate'
import { Projection } from '../track/projection'
import { InterpolationFigure } from './InterpolationFigure'

/** 10 m: a car moving at walking pace or more covers this over a few samples */
const MIN_LEG_DM = 100

/**
 * The sample where the car turns most sharply between `fromMs` and `toMs`: the biggest change of
 * direction between the `reach` samples before it and the `reach` after it. Looking a few samples
 * either side, not just one, smooths out the noise in the positions; and both stretches must cover
 * at least `MIN_LEG_DM`, or a car standing still (in its pit box) would jitter into a sharp "turn".
 * Samples with a gap among them are skipped too.
 */
export function sharpestTurn(car: Samples, fromMs: number, toMs: number, reach: number): number {
  const { t, x, y } = car
  let best = -1
  let bestTurn = -1
  for (let i = reach; i + reach < t.length; i++) {
    const ms = sampleAt(t, i)
    if (ms < fromMs || ms > toMs) {
      continue
    }
    if (distance(x, y, i - reach, i) < MIN_LEG_DM || distance(x, y, i, i + reach) < MIN_LEG_DM) {
      continue
    }
    // across a gap the car wasn't seen, so a "turn" there is where it went missing and came back
    if (hasGap(t, i - reach, i + reach)) {
      continue
    }
    const into = heading(x, y, i - reach, i)
    const outOf = heading(x, y, i, i + reach)
    // the change of direction, from 0 (straight on) to π (straight back)
    const turn = Math.abs(Math.atan2(Math.sin(outOf - into), Math.cos(outOf - into)))
    if (turn > bestTurn) {
      best = i
      bestTurn = turn
    }
  }
  if (best < 0) {
    throw new RangeError(`no samples between ${String(fromMs)} and ${String(toMs)} ms`)
  }
  return best
}

/** Whether two neighbouring samples from `from` to `to` are more than MAX_GAP_MS apart. */
function hasGap(t: Float64Array, from: number, to: number): boolean {
  for (let j = from; j < to; j++) {
    if (sampleAt(t, j + 1) - sampleAt(t, j) > MAX_GAP_MS) {
      return true
    }
  }
  return false
}

/** How far from sample `from` to sample `to`, in dm. */
function distance(x: Float64Array, y: Float64Array, from: number, to: number): number {
  return Math.hypot(sampleAt(x, to) - sampleAt(x, from), sampleAt(y, to) - sampleAt(y, from))
}

/** The direction from sample `from` to sample `to`, in radians. */
function heading(x: Float64Array, y: Float64Array, from: number, to: number): number {
  return Math.atan2(sampleAt(y, to) - sampleAt(y, from), sampleAt(x, to) - sampleAt(x, from))
}

/** The figure as SVG text: car `carNumber` through its sharpest turn from `fromMs` to `toMs`. */
export function interpolationFigure(
  race: Race,
  carNumber: number,
  fromMs: number,
  toMs: number,
): string {
  const car = race.cars.find((c) => c.number === carNumber)
  if (car === undefined) {
    throw new RangeError(`no car ${String(carNumber)} in the race`)
  }
  const corner = sharpestTurn(car, fromMs, toMs, 3)
  const projection = new Projection(race.track.rotation, race.track.bounds)
  const figure = createElement(InterpolationFigure, {
    car,
    projection,
    first: corner - 3,
    last: corner + 3,
  })
  return renderToStaticMarkup(figure)
}
