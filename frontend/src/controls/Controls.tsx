import { useEffect, useEffectEvent } from 'react'

import { formatRaceTime } from './raceTime'

/** The speeds offered: real time and ten times faster. */
const SPEEDS = [1, 10] as const

interface ControlsProps {
  readonly playing: boolean
  readonly speed: number
  /** Race time now and the race's length, in ms. */
  readonly time: number
  readonly durationMs: number
  readonly onPlayPause: () => void
  readonly onSpeed: (speed: number) => void
}

/** Play/pause, the speed, and how far into the race it is. The space bar plays and pauses too. */
export function Controls({
  playing,
  speed,
  time,
  durationMs,
  onPlayPause,
  onSpeed,
}: ControlsProps) {
  const onKey = useEffectEvent((event: KeyboardEvent) => {
    // space on a focused button already clicks it: toggling here as well would undo the click
    if (event.key !== ' ' || event.repeat || event.target instanceof HTMLButtonElement) {
      return
    }
    // without this, space also scrolls the page down
    event.preventDefault()
    onPlayPause()
  })

  useEffect(() => {
    function listener(event: KeyboardEvent) {
      onKey(event)
    }
    window.addEventListener('keydown', listener)
    return () => {
      window.removeEventListener('keydown', listener)
    }
  }, [])

  return (
    <div className="controls" role="group" aria-label="Playback">
      <button type="button" onClick={onPlayPause}>
        {playing ? 'Pause' : 'Play'}
      </button>
      {SPEEDS.map((s) => (
        <button
          key={s}
          type="button"
          aria-pressed={s === speed}
          onClick={() => {
            onSpeed(s)
          }}
        >
          {`${String(s)}×`}
        </button>
      ))}
      {/* not an <output>: that's a live region, and a screen reader would read it every second */}
      <span className="race-time">{`${formatRaceTime(time)} / ${formatRaceTime(durationMs)}`}</span>
    </div>
  )
}
