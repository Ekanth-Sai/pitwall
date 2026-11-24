// Writes docs/figures/interpolation.svg from the Monza race, using the app's own code: Vite loads
// the TypeScript (`runnerImport`), so nothing here repeats the maths.
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { runnerImport } from 'vite'

const frontend = new URL('../', import.meta.url)
// a real path, not a URL's: `pathname` would keep a space as %20
const root = fileURLToPath(frontend)
const { module: load } = await runnerImport('/src/race/load.ts', { root })
const { module: figure } = await runnerImport('/src/figures/interpolation.ts', { root })

const race = load.parseRace(
  JSON.parse(readFileSync(new URL('public/races/monza-2024.json', frontend), 'utf8')),
)
// Leclerc, the winner, on a lap 20 minutes in, clear of the start
const svg = figure.interpolationFigure(race, 16, 20 * 60_000, 21.5 * 60_000)
const out = new URL('../docs/figures/interpolation.svg', frontend)
writeFileSync(out, svg + '\n')
console.log(`wrote ${fileURLToPath(out)}`)
