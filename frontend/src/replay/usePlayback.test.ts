import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { installFakeFrames } from '../test/frames'
import { PlaybackClock } from './clock'
import { usePlayback } from './usePlayback'

// a 1000 ms race, with wall time and frames moved by hand: `wait(ms)` moves time on with no frame
// (as in a background tab), `frame(ms)` moves it on and then draws
function setup() {
  const frames = installFakeFrames()
  let wall = 0
  const hook = renderHook(() => usePlayback(1000, () => wall))
  function wait(ms: number) {
    wall += ms
  }
  function frame(ms: number) {
    wait(ms)
    act(() => {
      frames.step(wall)
    })
  }
  function press(action: (playback: typeof hook.result.current) => void) {
    act(() => {
      action(hook.result.current)
    })
  }
  return { frames, wait, frame, press, hook }
}

describe('usePlayback', () => {
  it('plays from the start', () => {
    const { frame, hook } = setup()
    expect(hook.result.current).toMatchObject({ time: 0, playing: true, speed: 1 })
    frame(100)
    expect(hook.result.current.time).toBe(100)
  })

  it('stands still while paused, with no frames asked for', () => {
    const { frames, frame, press, hook } = setup()
    frame(100)
    press((p) => {
      p.playPause()
    })
    expect(hook.result.current).toMatchObject({ time: 100, playing: false })
    expect(frames.pending).toBe(0)
    frame(500)
    expect(hook.result.current.time).toBe(100)
  })

  it('carries on from where it was paused', () => {
    const { frame, press, hook } = setup()
    frame(100)
    press((p) => {
      p.playPause()
    })
    frame(500)
    press((p) => {
      p.playPause()
    })
    frame(50)
    expect(hook.result.current).toMatchObject({ time: 150, playing: true })
  })

  it('changes speed', () => {
    const { frame, press, hook } = setup()
    press((p) => {
      p.setSpeed(10)
    })
    frame(50)
    expect(hook.result.current).toMatchObject({ time: 500, speed: 10 })
  })

  it('stops at the end, then plays again from the start', () => {
    const { frames, frame, press, hook } = setup()
    frame(5000)
    expect(hook.result.current).toMatchObject({ time: 1000, playing: false })
    expect(frames.pending).toBe(0)
    press((p) => {
      p.playPause()
    })
    expect(hook.result.current).toMatchObject({ time: 0, playing: true })
    frame(10)
    expect(hook.result.current.time).toBe(10)
  })

  it('shows at once when a speed change finds the race over', () => {
    const { frames, wait, press, hook } = setup()
    wait(5000)
    press((p) => {
      p.setSpeed(10)
    })
    expect(hook.result.current).toMatchObject({ time: 1000, playing: false, speed: 10 })
    expect(frames.pending).toBe(0)
  })

  it('pauses the clock when the component goes away', () => {
    const pause = vi.spyOn(PlaybackClock.prototype, 'pause')
    const { frames, hook } = setup()
    hook.unmount()
    expect(pause).toHaveBeenCalledTimes(1)
    expect(frames.pending).toBe(0)
  })
})
