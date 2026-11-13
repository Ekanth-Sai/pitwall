import { describe, expect, it, vi } from 'vitest'

import monza from '../../public/races/monza-2024.json?raw'
import { loadRace, parseRace, ReplayError, undelta } from './load'

// One car in the export's format, with the three samples. `changes` replaces some of its fields.
function carJson(changes: Record<string, unknown> = {}) {
  return {
    number: 16,
    acronym: 'LEC',
    name: 'Charles LECLERC',
    team: 'Ferrari',
    colour: 'E80020',
    ink: 'white',
    t: [56, 200, 240],
    x: [-1151, 0, 3],
    y: [1892, 2, -1],
    ...changes,
  }
}

// A small race in the export's format with the cars given.
function raceJson(cars = [carJson()]) {
  return {
    format: 1,
    session: { name: 'Race', location: 'Monza', year: 2024 },
    start: '2024-09-01T13:03:34.412+00:00',
    duration_ms: 1000,
    track: {
      format: 1,
      rotation: -64.63,
      bounds: [0, 0, 10, 10],
      circuit: [
        [0, 0],
        [10, 0],
        [10, 10],
      ],
      pit_lane: null,
    },
    cars,
  }
}

function okResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

describe('undelta', () => {
  it('rebuilds absolute values with a running sum', () => {
    expect(Array.from(undelta([5, 1, 2]))).toEqual([5, 6, 8])
  })

  it('handles an empty column', () => {
    expect(undelta([])).toHaveLength(0)
  })
})

describe('parseRace', () => {
  it('decodes the session, track and cars', () => {
    const race = parseRace(raceJson())
    expect(race.location).toBe('Monza')
    expect(race.start.toISOString()).toBe('2024-09-01T13:03:34.412Z')
    expect(race.durationMs).toBe(1000)
    expect(race.track.pitLane).toBeNull()
    const car = race.cars[0]
    expect(car?.colour).toBe('#E80020')
    expect(Array.from(car?.t ?? [])).toEqual([56, 256, 496])
    expect(Array.from(car?.x ?? [])).toEqual([-1151, -1151, -1148])
    expect(Array.from(car?.y ?? [])).toEqual([1892, 1894, 1893])
  })

  it('accepts the real Monza export', () => {
    const race = parseRace(JSON.parse(monza))
    expect(race.cars).toHaveLength(20)
    expect(race.track.circuit).toHaveLength(500)
  })

  it.each([
    ['not an object', () => 'race'],
    ['another format', (r: ReturnType<typeof raceJson>) => ({ ...r, format: 2 })],
    ['a bad start time', (r: ReturnType<typeof raceJson>) => ({ ...r, start: 'Sunday' })],
    [
      'a start time without exactly 3 fraction digits',
      (r: ReturnType<typeof raceJson>) => ({ ...r, start: '2024-09-01T13:03:34.412123+00:00' }),
    ],
    ['no cars', (r: ReturnType<typeof raceJson>) => ({ ...r, cars: [] })],
  ])('rejects %s', (_label, change) => {
    expect(() => parseRace(change(raceJson()))).toThrow(ReplayError)
  })

  it('names the field that failed', () => {
    const race = raceJson([carJson({ colour: '#e80020' })])
    expect(() => parseRace(race)).toThrow('at cars[0].colour')
  })

  it('rejects columns of different lengths', () => {
    const race = raceJson([carJson({ x: [1, 2] })])
    expect(() => parseRace(race)).toThrow('t, x and y must have the same length')
  })

  it('rejects times that do not increase', () => {
    const race = raceJson([carJson({ t: [56, 0, 240] })])
    expect(() => parseRace(race)).toThrow('times must start at 0 or later and strictly increase')
  })

  it('rejects a time before the start', () => {
    const race = raceJson([carJson({ t: [-5, 200, 240] })])
    expect(() => parseRace(race)).toThrow('times must start at 0 or later and strictly increase')
  })

  it('rejects a time after the end', () => {
    const race = raceJson([carJson({ t: [56, 200, 745] })])
    expect(() => parseRace(race)).toThrow('every sample must be within duration_ms')
  })

  it('rejects two cars with the same number', () => {
    const race = raceJson([carJson(), carJson()])
    expect(() => parseRace(race)).toThrow('car numbers must be unique')
  })

  it('rejects bounds with min above max', () => {
    const race = raceJson()
    race.track.bounds = [10, 0, 0, 10]
    expect(() => parseRace(race)).toThrow('min below max')
  })

  it('keeps the message short when many values are wrong', () => {
    const many = Array.from({ length: 1000 }, () => 1.5)
    const race = raceJson([carJson({ t: many.map(() => 1), x: many, y: many })])
    let message = ''
    try {
      parseRace(race)
    } catch (e) {
      message = (e as Error).message
    }
    expect(message).toContain('(and 1995 more)')
    expect(message.length).toBeLessThan(2000)
  })

  it('rejects positions that are not integers', () => {
    const race = raceJson([carJson({ x: [1.5, 0, 0] })])
    expect(() => parseRace(race)).toThrow(ReplayError)
  })
})

describe('loadRace', () => {
  it('fetches and parses the file', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(okResponse(raceJson()))
    const race = await loadRace('/races/test.json', fetchFn)
    expect(race.cars).toHaveLength(1)
    expect(fetchFn).toHaveBeenCalledWith('/races/test.json', expect.anything())
  })

  it('reports a network failure', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline'))
    await expect(loadRace('/races/test.json', fetchFn)).rejects.toThrow(
      'could not download /races/test.json: TypeError: offline',
    )
  })

  it('says it timed out, not that the JSON is bad, when reading the body takes too long', async () => {
    const slow = {
      ok: true,
      json: () => Promise.reject(new DOMException('signal timed out', 'TimeoutError')),
    } as unknown as Response
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(slow)
    await expect(loadRace('/races/test.json', fetchFn, 10)).rejects.toThrow('timed out after 10 ms')
  })

  it('reports an HTTP error', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(new Response('', { status: 404 }))
    await expect(loadRace('/races/test.json', fetchFn)).rejects.toThrow('HTTP 404')
  })

  it('reports a body that is not JSON', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(new Response('<html>'))
    await expect(loadRace('/races/test.json', fetchFn)).rejects.toThrow('is not valid JSON')
  })

  it('gives up after the timeout', async () => {
    const fetchFn = vi.fn<typeof fetch>((_url, init) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(init.signal?.reason as Error)
        })
      })
    })
    await expect(loadRace('/races/test.json', fetchFn, 10)).rejects.toThrow('timed out after 10 ms')
  })
})
