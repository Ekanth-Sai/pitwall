import { useEffect, useEffectEvent } from 'react'

/**
 * Calls `onFrame` once per screen refresh while `active` is true (the default), from when the
 * component mounts until it unmounts.
 *
 * `onFrame` may be a new function on every render. The loop always calls the latest one, and isn't
 * stopped and started again when it changes.
 */
export function useAnimationFrame(onFrame: (now: number) => void, active = true): void {
  // an Effect Event: always the latest onFrame, but not a dependency of the effect below
  const frame = useEffectEvent(onFrame)

  useEffect(() => {
    if (!active) {
      return
    }
    let id = requestAnimationFrame(function tick(now) {
      frame(now)
      id = requestAnimationFrame(tick)
    })
    return () => {
      cancelAnimationFrame(id)
    }
  }, [active])
}
