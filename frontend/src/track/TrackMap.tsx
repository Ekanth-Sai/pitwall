import type { ReactNode } from 'react'

import type { Track } from '../race/load'
import type { Projection } from './projection'

/** Space around the track, in world units (decimetres): room for the dots at the edges. */
export const MARGIN = 400

interface TrackMapProps {
  readonly track: Track
  readonly projection: Projection
  /** Drawn on top of the track: the cars. */
  readonly children?: ReactNode
}

/** The circuit, the pit lane (dashed) and whatever is passed inside, scaled to fit. */
export function TrackMap({ track, projection, children }: TrackMapProps) {
  return (
    <svg
      className="track-map"
      viewBox={projection.viewBox(MARGIN)}
      role="img"
      aria-label="Track map"
    >
      <path className="circuit" d={projection.path(track.circuit, true)} />
      {track.pitLane && <path className="pit-lane" d={projection.path(track.pitLane, false)} />}
      {children}
    </svg>
  )
}
