import { useEffect, useState } from 'react'

import { loadRace, type Race } from './race/load'
import { RaceView } from './RaceView'

/** The race file. BASE_URL keeps the path right when the app is served from a subfolder. */
export const RACE_URL = `${import.meta.env.BASE_URL}races/monza-2024.json`

/** Where the download is: exactly one of these at a time. */
type LoadState =
  | { readonly status: 'loading' }
  | { readonly status: 'ready'; readonly race: Race }
  | { readonly status: 'error'; readonly message: string }

interface AppProps {
  /** Fetches the race. Swappable so tests need no network. */
  readonly load?: () => Promise<Race>
}

function loadMonza(): Promise<Race> {
  return loadRace(RACE_URL)
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export function App({ load = loadMonza }: AppProps) {
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    // set to false by the cleanup below, when `load` changes or the page goes away:
    // a download that finishes after that must not overwrite newer state
    let current = true
    async function run() {
      let next: LoadState
      try {
        next = { status: 'ready', race: await load() }
      } catch (error) {
        next = { status: 'error', message: errorMessage(error) }
      }
      if (current) {
        setState(next)
      }
    }
    void run()
    return () => {
      current = false
    }
  }, [load])

  return (
    <main>
      <h1>pitwall</h1>
      {state.status === 'loading' && <p role="status">Loading the race...</p>}
      {state.status === 'error' && <p role="alert">Could not load the race: {state.message}</p>}
      {state.status === 'ready' && <RaceView race={state.race} />}
      <footer>
        Data from <a href="https://openf1.org">OpenF1</a>. Unofficial and non-commercial.
      </footer>
    </main>
  )
}
