import { useEffect, useMemo, useState } from 'react'

import type { Race } from './race/load'
import { CarTrack } from './replay/carTrack'
import { type Now, PlaybackClock } from './replay/clock'
import { useAnimationFrame } from './replay/useAnimationFrame'
import { CarDot } from './track/CarDot'
import { Projection } from './track/projection'
import { TrackMap } from './track/TrackMap'

interface RaceViewProps {
  readonly race: Race
  /** Wall time in ms. Swappable so tests can move time by hand. */
  readonly now?: Now
}

function wallTime(): number {
  return performance.now()
}

/** The race playing at 1× from the start, with every car where it is now. P1.5 adds controls. */
export function RaceView({ race, now = wallTime }: RaceViewProps) {
  const { rotation, bounds } = race.track
  // built once per track, not on every frame
  const projection = useMemo(() => new Projection(rotation, bounds), [rotation, bounds])
  // one CarTrack per car, kept across frames so each one's cursor is still there next frame
  const cars = useMemo(
    () => race.cars.map((car) => ({ car, track: new CarTrack(car) })),
    [race.cars],
  )
  // the same clock for as long as this view is on screen: a useState initialiser runs only once
  const [clock] = useState(() => new PlaybackClock(race.durationMs, now))
  // the race time drawn: set every frame, and each change re-renders the view
  const [time, setTime] = useState(0)

  useEffect(() => {
    clock.play()
  }, [clock])

  useAnimationFrame(() => {
    setTime(clock.time())
  })

  return (
    <section>
      <h2>{`${race.location} ${String(race.year)} · ${race.name}`}</h2>
      <TrackMap track={race.track} projection={projection}>
        {cars.map(({ car, track }) => {
          const position = track.positionAt(time)
          if (position === null) {
            return null
          }
          const [x, y] = projection.project(...position)
          return <CarDot key={car.number} car={car} x={x} y={y} />
        })}
      </TrackMap>
    </section>
  )
}
