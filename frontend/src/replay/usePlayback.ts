import { useEffect, useState } from 'react'

import { type Now, PlaybackClock } from './clock'
import { useAnimationFrame } from './useAnimationFrame'

/** The replay's state for drawing, and what the controls can do to it. */
export interface Playback {
  /** Race time in ms, updated every frame while playing. */
  readonly time: number
  readonly playing: boolean
  readonly speed: number
  // arrow-function types, not methods: callers pass them around on their own, as onClick handlers
  readonly playPause: () => void
  readonly setSpeed: (speed: number) => void
}

/**
 * A PlaybackClock for a component's whole life, playing from when the component appears.
 *
 * The clock holds the truth; `time`, `playing` and `speed` copy it into React state, because a
 * state change is what makes React draw again. The frame loop runs only while playing.
 */
export function usePlayback(durationMs: number, now: Now): Playback {
  // a useState initialiser runs only once, so this is the same clock on every render
  const [clock] = useState(() => new PlaybackClock(durationMs, now))
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeedState] = useState(clock.speed)

  useEffect(() => {
    clock.play()
    return () => {
      clock.pause()
    }
  }, [clock])

  useAnimationFrame(() => {
    setTime(clock.time())
    // the clock pauses itself at the end of the race; this stops the loop then
    setPlaying(clock.playing)
  }, playing)

  return {
    time,
    playing,
    speed,
    playPause: () => {
      if (clock.playing) {
        clock.pause()
      } else {
        clock.play()
      }
      setTime(clock.time())
      setPlaying(clock.playing)
    },
    setSpeed: (next) => {
      // setSpeed reads the time first, so it can be what stops the clock at the end
      clock.setSpeed(next)
      setSpeedState(next)
      setTime(clock.time())
      setPlaying(clock.playing)
    },
  }
}
