import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { installFakeFrames } from '../test/frames'
import { useAnimationFrame } from './useAnimationFrame'

describe('useAnimationFrame', () => {
  it('calls back once per frame with the frame time', () => {
    const frames = installFakeFrames()
    const onFrame = vi.fn()
    renderHook(() => {
      useAnimationFrame(onFrame)
    })
    act(() => {
      frames.step(16)
      frames.step(33)
    })
    expect(onFrame.mock.calls).toEqual([[16], [33]])
  })

  it('calls the latest callback without restarting the loop', () => {
    const frames = installFakeFrames()
    const first = vi.fn()
    const second = vi.fn()
    const { rerender } = renderHook(
      ({ onFrame }) => {
        useAnimationFrame(onFrame)
      },
      { initialProps: { onFrame: first } },
    )
    rerender({ onFrame: second })
    act(() => {
      frames.step(16)
    })
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledWith(16)
    expect(frames.pending).toBe(1)
  })

  it('stops when the component goes away, even after some frames', () => {
    const frames = installFakeFrames()
    const onFrame = vi.fn()
    const { unmount } = renderHook(() => {
      useAnimationFrame(onFrame)
    })
    // each frame asks for the next one under a new id: the one to cancel is the latest
    act(() => {
      frames.step(16)
    })
    unmount()
    expect(frames.pending).toBe(0)
    frames.step(33)
    expect(onFrame).toHaveBeenCalledTimes(1)
  })
})
