import { useMemo } from 'react'

import type { Car, Point, Race } from './race/load'
import { CarDot } from './track/CarDot'
import { Projection } from './track/projection'
import { TrackMap } from './track/TrackMap'

interface RaceViewProps {
  readonly race: Race
}

/** A car's first recorded position, or null if it has none. */
function firstPosition(car: Car): Point | null {
  const x = car.x[0]
  const y = car.y[0]
  return x === undefined || y === undefined ? null : [x, y]
}

/** The race at its first moment: every car at its first sample. P1.4 makes them move. */
export function RaceView({ race }: RaceViewProps) {
  const { rotation, bounds } = race.track
  // built once per track, not on every render: P1.4 re-renders this many times a second
  const projection = useMemo(() => new Projection(rotation, bounds), [rotation, bounds])

  return (
    <section>
      <h2>{`${race.location} ${String(race.year)} · ${race.name}`}</h2>
      <TrackMap track={race.track} projection={projection}>
        {race.cars.map((car) => {
          const start = firstPosition(car)
          if (start === null) {
            return null
          }
          const [x, y] = projection.project(...start)
          return <CarDot key={car.number} car={car} x={x} y={y} />
        })}
      </TrackMap>
    </section>
  )
}
