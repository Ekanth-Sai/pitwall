// adds DOM matchers such as toHaveTextContent to Vitest's expect
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

import { installFakeFrames } from './frames'

// no real screen refreshes in tests: frames run only when a test steps them
beforeEach(() => {
  installFakeFrames()
})

// unmount whatever a test rendered, so the next test starts from an empty page
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
