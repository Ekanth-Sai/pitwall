import { useMemo, type ReactNode } from 'react'

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
  // the cars inside re-render this every frame, but the track itself never changes.
  const circuit = useMemo(() => projection.path(track.circuit, true), [projection, track.circuit])
  const pitLane = useMemo(
    () => (track.pitLane ? projection.path(track.pitLane, false) : null),
    [projection, track.pitLane],
  )
  return (
    <svg
      className="track-map"
      viewBox={projection.viewBox(MARGIN)}
      role="img"
      aria-label="Track map"
    >
      <path className="circuit" d={circuit} />
      {pitLane !== null && <path className="pit-lane" d={pitLane} />}
      {children}
    </svg>
  )
}
