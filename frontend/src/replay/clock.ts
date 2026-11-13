/** Wall time in milliseconds, such as `performance.now`. Passed in so tests can control it. */
export type Now = () => number

/**
 * The replay's race time, in ms since the race file's `start`. While playing, it runs at `speed`
 * times wall time; it stops at `durationMs` and pauses there.
 *
 * It stores one anchor, "race time `anchorRace` at wall time `anchorWall`", and works out the
 * current time from it. Every change (play, pause, speed, seek) moves the anchor to now first,
 * so race time never jumps.
 */
export class PlaybackClock {
  readonly durationMs: number
  private readonly now: Now
  private anchorRace = 0
  private anchorWall: number
  private rate = 1
  private running = false

  constructor(durationMs: number, now: Now) {
    if (!(Number.isFinite(durationMs) && durationMs > 0)) {
      throw new RangeError(`duration must be a positive number of ms, got ${String(durationMs)}`)
    }
    this.durationMs = durationMs
    this.now = now
    this.anchorWall = now()
  }

  get playing(): boolean {
    return this.running
  }

  get speed(): number {
    return this.rate
  }

  /** Race time now. Reaching the end pauses the clock there. */
  time(): number {
    if (!this.running) {
      return this.anchorRace
    }
    const t = this.anchorRace + (this.now() - this.anchorWall) * this.rate
    if (t >= this.durationMs) {
      this.anchorRace = this.durationMs
      this.running = false
      return this.durationMs
    }
    return t
  }

  /** Starts the clock. At the end, it starts again from the beginning. */
  play(): void {
    if (this.running) {
      return
    }
    if (this.anchorRace >= this.durationMs) {
      this.anchorRace = 0
    }
    this.anchorWall = this.now()
    this.running = true
  }

  pause(): void {
    this.anchorRace = this.time()
    this.running = false
  }

  /** How many race ms pass per wall ms: 1 is real time, 10 is ten times faster. */
  setSpeed(speed: number): void {
    if (!(Number.isFinite(speed) && speed > 0)) {
      throw new RangeError(`speed must be a positive number, got ${String(speed)}`)
    }
    this.moveAnchorToNow()
    this.rate = speed
  }

  /** Jumps to race time `ms`, kept within the race. Playing stays playing. */
  seek(ms: number): void {
    if (!Number.isFinite(ms)) {
      throw new RangeError(`can't seek to ${String(ms)}`)
    }
    this.anchorRace = Math.min(Math.max(ms, 0), this.durationMs)
    this.anchorWall = this.now()
  }

  private moveAnchorToNow(): void {
    this.anchorRace = this.time()
    this.anchorWall = this.now()
  }
}
