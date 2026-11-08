// adds DOM matchers such as toHaveTextContent to Vitest's expect
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// unmount whatever a test rendered, so the next test starts from an empty page
afterEach(() => {
  cleanup()
})
