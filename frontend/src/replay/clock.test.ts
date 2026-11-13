import { describe, expect, it } from 'vitest'

import { PlaybackClock } from './clock'

// A wall clock the test moves by hand.
class FakeTime {
  wall = 1000

  readonly now = () => this.wall

  advance(ms: number): void {
    this.wall += ms
  }
}

function setup(durationMs = 10_000) {
  const time = new FakeTime()
  return { time, clock: new PlaybackClock(durationMs, time.now) }
}

describe('PlaybackClock', () => {
  it('starts paused at the beginning', () => {
    const { time, clock } = setup()
    time.advance(500)
    expect(clock.playing).toBe(false)
    expect(clock.time()).toBe(0)
  })

  it('follows wall time while playing', () => {
    const { time, clock } = setup()
    clock.play()
    time.advance(250)
    expect(clock.time()).toBe(250)
  })

  it('runs faster at high speed', () => {
    const { time, clock } = setup()
    clock.setSpeed(10)
    clock.play()
    time.advance(100)
    expect(clock.time()).toBe(1000)
    expect(clock.speed).toBe(10)
  })

  it('stands still while paused', () => {
    const { time, clock } = setup()
    clock.play()
    time.advance(300)
    clock.pause()
    time.advance(5000)
    expect(clock.time()).toBe(300)
  })

  it('carries on from where it was paused', () => {
    const { time, clock } = setup()
    clock.play()
    time.advance(300)
    clock.pause()
    time.advance(5000)
    clock.play()
    time.advance(200)
    expect(clock.time()).toBe(500)
  })

  it('does not jump when the speed changes', () => {
    const { time, clock } = setup()
    clock.play()
    time.advance(100)
    clock.setSpeed(10)
    expect(clock.time()).toBe(100)
    time.advance(100)
    expect(clock.time()).toBe(1100)
  })

  it('ignores play while already playing', () => {
    const { time, clock } = setup()
    clock.play()
    time.advance(100)
    clock.play()
    time.advance(100)
    expect(clock.time()).toBe(200)
  })

  it('stops and pauses at the end', () => {
    const { time, clock } = setup(1000)
    clock.play()
    time.advance(5000)
    expect(clock.time()).toBe(1000)
    expect(clock.playing).toBe(false)
  })

  it('starts again from the beginning when playing at the end', () => {
    const { time, clock } = setup(1000)
    clock.play()
    time.advance(5000)
    clock.time()
    clock.play()
    time.advance(100)
    expect(clock.time()).toBe(100)
  })

  it('seeks forwards and backwards, and keeps playing', () => {
    const { time, clock } = setup()
    clock.play()
    clock.seek(8000)
    time.advance(100)
    expect(clock.time()).toBe(8100)
    clock.seek(2000)
    expect(clock.time()).toBe(2000)
    expect(clock.playing).toBe(true)
  })

  it('keeps a seek within the race', () => {
    const { clock } = setup(1000)
    clock.seek(-50)
    expect(clock.time()).toBe(0)
    clock.seek(99_999)
    expect(clock.time()).toBe(1000)
  })

  it.each([0, -1, Number.NaN, Number.POSITIVE_INFINITY])('rejects a duration of %s', (ms) => {
    expect(() => new PlaybackClock(ms, () => 0)).toThrow(RangeError)
  })

  it.each([0, -2, Number.NaN])('rejects a speed of %s', (speed) => {
    const { clock } = setup()
    expect(() => {
      clock.setSpeed(speed)
    }).toThrow(RangeError)
  })

  it('rejects a seek to a time that is not a number', () => {
    const { clock } = setup()
    expect(() => {
      clock.seek(Number.NaN)
    }).toThrow(RangeError)
  })
})
