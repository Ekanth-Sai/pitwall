import { type MouseEvent, useEffect, useEffectEvent } from 'react'

import { formatRaceTime } from './raceTime'

/**
 * Clicking a speed with the mouse leaves focus where it was. Otherwise the speed button would
 * keep focus, and the space bar would only click it again instead of playing and pausing.
 * Keyboard users still reach it with Tab. Play/Pause doesn't need this: space on it clicks it,
 * which toggles.
 */
function keepFocus(event: MouseEvent<HTMLButtonElement>) {
  event.preventDefault()
}

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
    // Left alone: other keys, a held-down space, space with a modifier (Shift+Space scrolls up),
    // and space on a focused button, which already clicks it: toggling as well would undo that.
    const modified = event.shiftKey || event.ctrlKey || event.altKey || event.metaKey
    if (
      event.key !== ' ' ||
      event.repeat ||
      modified ||
      event.target instanceof HTMLButtonElement
    ) {
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
          onMouseDown={keepFocus}
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
