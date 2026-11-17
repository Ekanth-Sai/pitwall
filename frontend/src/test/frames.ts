import { vi } from 'vitest'

/** Stands in for the browser's requestAnimationFrame: a frame runs only when a test calls step. */
export class FakeFrames {
  private nextId = 1
  private readonly waiting = new Map<number, FrameRequestCallback>()

  readonly request = (callback: FrameRequestCallback): number => {
    const id = this.nextId++
    this.waiting.set(id, callback)
    return id
  }

  readonly cancel = (id: number): void => {
    this.waiting.delete(id)
  }

  /** How many callbacks wait for the next frame. */
  get pending(): number {
    return this.waiting.size
  }

  /** Runs one frame at time `now`. Callbacks requested during it wait for the next one. */
  step(now: number): void {
    const due = [...this.waiting.values()]
    this.waiting.clear()
    for (const callback of due) {
      callback(now)
    }
  }
}

/** Replaces requestAnimationFrame and cancelAnimationFrame with a new FakeFrames. */
export function installFakeFrames(): FakeFrames {
  const frames = new FakeFrames()
  vi.stubGlobal('requestAnimationFrame', frames.request)
  vi.stubGlobal('cancelAnimationFrame', frames.cancel)
  return frames
}
