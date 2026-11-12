import type { Car } from '../race/load'

/** Dot size in world units (decimetres): about 44 m across, so the number is readable. */
export const DOT_RADIUS = 220

interface CarDotProps {
  readonly car: Car
  /** Where to draw it, in screen (SVG) coordinates: already projected. */
  readonly x: number
  readonly y: number
}

/** One car: a circle in the team colour with the driver number on it. */
export function CarDot({ car, x, y }: CarDotProps) {
  return (
    <g className="car" transform={`translate(${x.toFixed(1)} ${y.toFixed(1)})`}>
      <title>{`${car.acronym}: ${car.name}, ${car.team}`}</title>
      <circle r={DOT_RADIUS} fill={car.colour} />
      <text fill={car.ink} fontSize={DOT_RADIUS} textAnchor="middle" dominantBaseline="central">
        {car.number}
      </text>
    </g>
  )
}
