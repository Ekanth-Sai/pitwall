import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { Car, Race } from './race/load'
import { RaceView } from './RaceView'
import { installFakeFrames } from './test/frames'
import { Projection } from './track/projection'

// samples at the given times, moving 1 dm in x per ms, at y = 0
function makeCar(number: number, times: number[]): Car {
  return {
    number,
    acronym: 'TST',
    name: 'Test DRIVER',
    team: 'Test Team',
    colour: '#3671C6',
    ink: 'white',
    t: Float64Array.from(times),
    x: Float64Array.from(times),
    y: Float64Array.from(times, () => 0),
  }
}

const race: Race = {
  name: 'Race',
  location: 'Monza',
  year: 2024,
  start: new Date('2024-09-01T13:03:34Z'),
  durationMs: 1000,
  track: {
    rotation: 0,
    bounds: [0, 0, 1000, 100],
    circuit: [
      [0, 0],
      [1000, 0],
      [1000, 100],
    ],
    pitLane: null,
  },
  cars: [makeCar(1, [0, 1000]), makeCar(16, [500, 800])],
}

const projection = new Projection(race.track.rotation, race.track.bounds)

// renders the view with hand-moved wall time and frames; `frame(ms)` moves time on, then draws
function setup() {
  const frames = installFakeFrames()
  let wall = 0
  const view = render(<RaceView race={race} now={() => wall} />)
  function frame(ms: number) {
    wall += ms
    act(() => {
      frames.step(wall)
    })
  }
  // each drawn car's number and where it's drawn (the transform on its dot)
  function drawn() {
    const out = new Map<string | undefined, string | null>()
    for (const dot of view.container.querySelectorAll('g.car')) {
      out.set(dot.querySelector('text')?.textContent, dot.getAttribute('transform'))
    }
    return out
  }
  return { frames, frame, drawn, view }
}

function at(x: number, y: number): string {
  const [sx, sy] = projection.project(x, y)
  return `translate(${sx.toFixed(1)} ${sy.toFixed(1)})`
}

describe('RaceView', () => {
  it('starts at the beginning of the race', () => {
    const { drawn } = setup()
    expect(drawn()).toEqual(new Map([['1', at(0, 0)]]))
  })

  it('moves the cars as wall time passes', () => {
    const { frame, drawn } = setup()
    frame(250)
    expect(drawn().get('1')).toBe(at(250, 0))
    frame(400)
    expect(drawn()).toEqual(
      new Map([
        ['1', at(650, 0)],
        ['16', at(650, 0)],
      ]),
    )
  })

  it('hides a car after its last sample, and stops at the end of the race', () => {
    const { frame, drawn } = setup()
    frame(900)
    expect(drawn().has('16')).toBe(false)
    frame(5000)
    expect(drawn()).toEqual(new Map([['1', at(1000, 0)]]))
  })

  it('stops asking for frames when it goes away', () => {
    const { frames, view } = setup()
    view.unmount()
    expect(frames.pending).toBe(0)
  })

  it('holds the cars still while paused, and runs ten times faster at 10×', async () => {
    const user = userEvent.setup()
    const { frame, drawn } = setup()
    frame(10)
    await user.click(screen.getByRole('button', { name: 'Pause' }))
    frame(500)
    expect(drawn().get('1')).toBe(at(10, 0))
    await user.click(screen.getByRole('button', { name: '10×' }))
    await user.click(screen.getByRole('button', { name: 'Play' }))
    frame(20)
    expect(drawn().get('1')).toBe(at(210, 0))
    expect(screen.getByText('0:00 / 0:01')).toBeInTheDocument()
  })
})
