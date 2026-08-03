import { _electron as electron, ElectronApplication, Page } from 'playwright'
import * as path from 'path'

const FRONTEND_ROOT = path.resolve(__dirname, '..', '..')

/**
 * Launches the real Electron app pointing at the already-running
 * `next dev` server on http://localhost:3000 (electron/main.ts loadURL
 * in dev mode). Requires `npm run dev` AND `npm run electron:compile`
 * to have been run first (dist-electron/main.js must exist).
 */
export async function launchUltronApp(): Promise<{ app: ElectronApplication; page: Page }> {
  const app = await electron.launch({
    args: [path.join(FRONTEND_ROOT, 'dist-electron', 'main.js')],
    cwd: FRONTEND_ROOT,
  })

  const page = await app.firstWindow()
  await page.waitForLoadState('domcontentloaded')

  return { app, page }
}
