import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App, RACE_URL } from './App.tsx'
import type { Car, Race } from './race/load'
import { Projection } from './track/projection'

function makeCar(number: number, x: number[], y: number[]): Car {
  return {
    number,
    acronym: 'TST',
    name: 'Test DRIVER',
    team: 'Test Team',
    colour: '#3671C6',
    ink: 'white',
    t: new Float64Array(x.map((_, i) => i * 250)),
    x: new Float64Array(x),
    y: new Float64Array(y),
  }
}

function makeRace(location: string, cars: readonly Car[]): Race {
  return {
    name: 'Race',
    location,
    year: 2024,
    start: new Date('2024-09-01T13:03:34Z'),
    durationMs: 1000,
    track: {
      rotation: 90,
      bounds: [0, 0, 100, 50],
      circuit: [
        [0, 0],
        [100, 0],
        [100, 50],
      ],
      pitLane: null,
    },
    cars,
  }
}

const race = makeRace('Monza', [makeCar(1, [10, 20], [5, 6]), makeCar(16, [30], [40])])

/** A promise and the function that settles it, for tests that decide when a download ends. */
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

const never = () => new Promise<Race>(() => undefined)

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('shows the project name as the page heading', () => {
    render(<App load={never} />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('pitwall')
  })

  it('credits OpenF1 with a link', () => {
    render(<App load={never} />)
    expect(screen.getByRole('link', { name: 'OpenF1' })).toHaveAttribute(
      'href',
      'https://openf1.org',
    )
  })

  it('says it is loading until the race arrives', () => {
    render(<App load={never} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading the race')
    expect(screen.queryByRole('img', { name: 'Track map' })).not.toBeInTheDocument()
  })

  it('draws the track and one dot per car once the race arrives', async () => {
    const { container } = render(<App load={() => Promise.resolve(race)} />)
    expect(await screen.findByRole('img', { name: 'Track map' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Monza 2024 · Race')
    expect(container.querySelectorAll('g.car')).toHaveLength(2)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('puts each car at its first sample', async () => {
    const { container } = render(<App load={() => Promise.resolve(race)} />)
    await screen.findByRole('img', { name: 'Track map' })
    const [x, y] = new Projection(90, [0, 0, 100, 50]).project(10, 5)
    expect(container.querySelector('g.car')).toHaveAttribute(
      'transform',
      `translate(${x.toFixed(1)} ${y.toFixed(1)})`,
    )
  })

  it('leaves out a car with no samples', async () => {
    const empty = makeRace('Monza', [makeCar(1, [10], [5]), makeCar(2, [], [])])
    const { container } = render(<App load={() => Promise.resolve(empty)} />)
    await screen.findByRole('img', { name: 'Track map' })
    expect(container.querySelectorAll('g.car')).toHaveLength(1)
  })

  it('shows why the race could not be loaded', async () => {
    render(<App load={() => Promise.reject(new Error('HTTP 404'))} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the race: HTTP 404')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('shows a failure that is not an Error too', async () => {
    // a swapped-in loader could reject with anything, which is the case tested here
    // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
    render(<App load={() => Promise.reject('timed out')} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the race: timed out')
  })

  it('ignores a download that finishes after a newer one', async () => {
    const old = deferred<Race>()
    const { rerender } = render(<App load={() => old.promise} />)
    rerender(<App load={() => Promise.resolve(makeRace('Spa', []))} />)
    expect(await screen.findByRole('heading', { level: 2 })).toHaveTextContent('Spa')
    // act() waits for React to finish whatever the late download triggers
    await act(async () => {
      old.resolve(race)
      await old.promise
    })
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Spa')
  })

  it('downloads the Monza file by default', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response(null, { status: 404 })))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 404')
    expect(fetchMock).toHaveBeenCalledWith(RACE_URL, expect.anything())
  })
})
