/** Race time as timing screens show it, rounded down to the second: m:ss, or h:mm:ss from 1 h. */
export function formatRaceTime(ms: number): string {
  if (!(Number.isFinite(ms) && ms >= 0)) {
    throw new RangeError(`race time must be 0 or more ms, got ${String(ms)}`)
  }
  const seconds = Math.floor(ms / 1000)
  const h = Math.floor(seconds / 3600)
  const m = Math.floor(seconds / 60) % 60
  const ss = String(seconds % 60).padStart(2, '0')
  return h > 0 ? `${String(h)}:${String(m).padStart(2, '0')}:${ss}` : `${String(m)}:${ss}`
}
