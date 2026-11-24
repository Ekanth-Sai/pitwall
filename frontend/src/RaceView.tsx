import { useMemo } from 'react'

import { Controls } from './controls/Controls'
import type { Race } from './race/load'
import { CarTrack } from './replay/carTrack'
import { catmullRom } from './replay/interpolate'
import type { Now } from './replay/clock'
import { usePlayback } from './replay/usePlayback'
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

/** The race playing from the start, with every car where it is now, and the controls above it. */
export function RaceView({ race, now = wallTime }: RaceViewProps) {
  const { rotation, bounds } = race.track
  // built once per track, not on every frame
  const projection = useMemo(() => new Projection(rotation, bounds), [rotation, bounds])
  // one CarTrack per car, kept across frames so each one's cursor is still there next frame
  const cars = useMemo(
    () => race.cars.map((car) => ({ car, track: new CarTrack(car, catmullRom) })),
    [race.cars],
  )
  const playback = usePlayback(race.durationMs, now)

  return (
    <section>
      <h2>{`${race.location} ${String(race.year)} · ${race.name}`}</h2>
      <Controls
        playing={playback.playing}
        speed={playback.speed}
        time={playback.time}
        durationMs={race.durationMs}
        onPlayPause={playback.playPause}
        onSpeed={playback.setSpeed}
      />
      <TrackMap track={race.track} projection={projection}>
        {cars.map(({ car, track }) => {
          const position = track.positionAt(playback.time)
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
