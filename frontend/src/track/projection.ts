import type { Bounds, Point } from '../race/load'

/**
 * Turns OpenF1 world coordinates into SVG coordinates. The world is in decimetres with y up;
 * the track's `rotation` lays it out landscape. SVG's y axis points down, so y is flipped last.
 */
export class Projection {
  private readonly cos: number
  private readonly sin: number
  private readonly bounds: Bounds

  /** `bounds` is the rotated bounding box from the race file: [minX, minY, maxX, maxY] */
  constructor(rotationDegrees: number, bounds: Bounds) {
    const [minX, minY, maxX, maxY] = bounds
    if (!(minX < maxX && minY < maxY)) {
      throw new RangeError(`empty bounds: ${bounds.join(', ')}`)
    }
    const radians = (rotationDegrees * Math.PI) / 180
    this.cos = Math.cos(radians)
    this.sin = Math.sin(radians)
    this.bounds = bounds
  }

  /** One world point on screen: rotate counter-clockwise about the origin, then flip y. */
  project(x: number, y: number): Point {
    return [x * this.cos - y * this.sin, -(x * this.sin + y * this.cos)]
  }

  /** The SVG viewBox ("minX minY width height) around the track, with `margin` on each side. */
  viewBox(margin: number): string {
    const [minX, minY, maxX, maxY] = this.bounds
    // after the flip, the top edge is the old maximum y
    return [minX - margin, -maxY - margin, maxX - minX + 2 * margin, maxY - minY + 2 * margin]
      .map((v) => v.toFixed(1))
      .join(' ')
  }

  /** SVG path data through the points; `closed` joins the last point back to the first. */
  path(points: readonly Point[], closed: boolean): string {
    const parts = points.map(([x, y], i) => {
      const [sx, sy] = this.project(x, y)
      return `${i === 0 ? 'M' : 'L'}${sx.toFixed(1)} ${sy.toFixed(1)}`
    })
    return parts.join(' ') + (closed ? ' Z' : '')
  }
}
