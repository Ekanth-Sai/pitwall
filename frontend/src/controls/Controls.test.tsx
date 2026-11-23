import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Controls } from './Controls'

function setup(playing = true, speed = 1) {
  const onPlayPause = vi.fn()
  const onSpeed = vi.fn()
  const view = render(
    <Controls
      playing={playing}
      speed={speed}
      time={61_000}
      durationMs={4_590_500}
      onPlayPause={onPlayPause}
      onSpeed={onSpeed}
    />,
  )
  return { onPlayPause, onSpeed, view, user: userEvent.setup() }
}

describe('Controls', () => {
  it('offers Pause while playing and Play while paused', () => {
    const { view } = setup(true)
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Play' })).not.toBeInTheDocument()
    view.unmount()
    setup(false)
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Pause' })).not.toBeInTheDocument()
  })

  it('plays and pauses on a click', async () => {
    const { onPlayPause, user } = setup()
    await user.click(screen.getByRole('button', { name: 'Pause' }))
    expect(onPlayPause).toHaveBeenCalledTimes(1)
  })

  it('shows which speed is on, and changes it on a click', async () => {
    const { onSpeed, user } = setup(true, 1)
    expect(screen.getByRole('button', { name: '1×' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '10×' })).toHaveAttribute('aria-pressed', 'false')
    await user.click(screen.getByRole('button', { name: '10×' }))
    expect(onSpeed).toHaveBeenCalledWith(10)
  })

  it('shows the race time and the length of the race', () => {
    setup()
    expect(screen.getByText('1:01 / 1:16:30')).toBeInTheDocument()
  })

  it('plays and pauses with the space bar', async () => {
    const { onPlayPause, user } = setup()
    await user.keyboard(' ')
    expect(onPlayPause).toHaveBeenCalledTimes(1)
  })

  it('stops space from scrolling the page', () => {
    const { onPlayPause } = setup()
    // fireEvent returns false when a listener called preventDefault
    expect(fireEvent.keyDown(document.body, { key: ' ' })).toBe(false)
    expect(onPlayPause).toHaveBeenCalledTimes(1)
  })

  it('leaves space on a focused button to the button', async () => {
    const { onPlayPause, user } = setup()
    const button = screen.getByRole('button', { name: '10×' })
    // the key going down: the shortcut stays out of it, the button clicks itself when it comes up
    expect(fireEvent.keyDown(button, { key: ' ' })).toBe(true)
    expect(onPlayPause).not.toHaveBeenCalled()
    // the whole press, with the button focused: one click, no extra toggle
    button.focus()
    await user.keyboard(' ')
    expect(onPlayPause).not.toHaveBeenCalled()
  })

  it('keeps the space bar working after a speed is clicked', async () => {
    const { onPlayPause, onSpeed, user } = setup()
    await user.click(screen.getByRole('button', { name: '10×' }))
    expect(onSpeed).toHaveBeenCalledWith(10)
    // the click didn't leave focus on 10×, so space plays and pauses instead of clicking 10× again
    expect(document.activeElement).toBe(document.body)
    await user.keyboard(' ')
    expect(onPlayPause).toHaveBeenCalledTimes(1)
    expect(onSpeed).toHaveBeenCalledTimes(1)
  })

  it('ignores other keys, a held-down space, and space with a modifier', async () => {
    const { onPlayPause, user } = setup()
    await user.keyboard('k{Enter}')
    await user.keyboard('{Shift>} {/Shift}{Control>} {/Control}{Alt>} {/Alt}{Meta>} {/Meta}')
    // pressed, then two automatic repeats while held, then released
    await user.keyboard('[Space>3/]')
    expect(onPlayPause).toHaveBeenCalledTimes(1)
  })

  it('stops listening for the space bar when it goes away', async () => {
    const { onPlayPause, user, view } = setup()
    view.unmount()
    await user.keyboard(' ')
    expect(onPlayPause).not.toHaveBeenCalled()
  })
})
