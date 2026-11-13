import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Car, Track } from '../race/load'
import { CarDot } from './CarDot'
import { Projection } from './projection'
import { TrackMap } from './TrackMap'

const track: Track = {
  rotation: 0,
  bounds: [0, 0, 100, 50],
  circuit: [
    [0, 0],
    [100, 0],
    [100, 50],
  ],
  pitLane: [
    [0, 10],
    [100, 10],
  ],
}

const car: Car = {
  number: 16,
  acronym: 'LEC',
  name: 'Charles LECLERC',
  team: 'Ferrari',
  colour: '#E80020',
  ink: 'white',
  t: new Float64Array([0]),
  x: new Float64Array([0]),
  y: new Float64Array([0]),
}

describe('TrackMap', () => {
  const projection = new Projection(track.rotation, track.bounds)

  it('draws the circuit as a closed path and the pit lane as an open one', () => {
    const { container } = render(<TrackMap track={track} projection={projection} />)
    const circuit = container.querySelector('path.circuit')
    const pitLane = container.querySelector('path.pit-lane')
    expect(circuit?.getAttribute('d')).toMatch(/^M0\.0 0\.0 .* Z$/)
    expect(pitLane?.getAttribute('d')).not.toMatch(/Z$/)
  })

  it('leaves out the pit lane when the race has none', () => {
    const { container } = render(
      <TrackMap track={{ ...track, pitLane: null }} projection={projection} />,
    )
    expect(container.querySelectorAll('path')).toHaveLength(1)
  })

  it('fits the viewBox to the track', () => {
    render(<TrackMap track={track} projection={projection} />)
    expect(screen.getByRole('img', { name: 'Track map' })).toHaveAttribute(
      'viewBox',
      projection.viewBox(400),
    )
  })

  it('draws its children on top of the track', () => {
    const { container } = render(
      <TrackMap track={track} projection={projection}>
        <CarDot car={car} x={0} y={0} />
      </TrackMap>,
    )
    const svg = container.querySelector('svg')
    expect(svg?.lastElementChild).toHaveClass('car')
  })
})

describe('CarDot', () => {
  function renderDot() {
    return render(
      <svg>
        <CarDot car={car} x={12.34} y={-5} />
      </svg>,
    )
  }

  it('shows the number in the ink colour on the team colour', () => {
    const { container } = renderDot()
    expect(container.querySelector('circle')).toHaveAttribute('fill', '#E80020')
    expect(screen.getByText('16')).toHaveAttribute('fill', 'white')
  })

  it('sits at the position it is given', () => {
    const { container } = renderDot()
    expect(container.querySelector('g.car')).toHaveAttribute('transform', 'translate(12.3 -5.0)')
  })

  it('names the driver on hover', () => {
    const { container } = renderDot()
    expect(container.querySelector('title')).toHaveTextContent('LEC: Charles LECLERC, Ferrari')
  })
})
