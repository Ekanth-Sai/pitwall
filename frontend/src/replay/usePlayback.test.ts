import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { installFakeFrames } from '../test/frames'
import { usePlayback } from './usePlayback'

// a 1000 ms race, with wall time and frames moved by hand; `frame(ms)` moves time on, then draws
function setup() {
  const frames = installFakeFrames()
  let wall = 0
  const hook = renderHook(() => usePlayback(1000, () => wall))
  function frame(ms: number) {
    wall += ms
    act(() => {
      frames.step(wall)
    })
  }
  function press(action: (playback: typeof hook.result.current) => void) {
    act(() => {
      action(hook.result.current)
    })
  }
  return { frames, frame, press, hook }
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

  it('pauses the clock when the component goes away', () => {
    const { frames, hook } = setup()
    hook.unmount()
    expect(frames.pending).toBe(0)
  })
})
