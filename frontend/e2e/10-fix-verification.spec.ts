import { test } from '@playwright/test'
import { launchUltronApp } from './fixtures/electron-app'
import type { ElectronApplication, Page } from 'playwright'

test.describe('10 — Post-fix manual verification', () => {
  let app: ElectronApplication
  let page: Page

  test.afterEach(async () => {
    await app?.close()
  })

  test('widgets show real backend state after fixes 6/7/8', async () => {
    const launched = await launchUltronApp()
    app = launched.app
    page = launched.page

    try {
      const ctx = page.context()
      await ctx.grantPermissions(['geolocation'])
      await ctx.setGeolocation({ latitude: 40.7128, longitude: -74.006 })
      // The widget's geolocation effect already ran (and likely failed/denied)
      // before permission was granted — reload so it re-mounts with permission
      // already in place, to exercise the real "ready" happy path.
      await page.reload()
      await page.waitForLoadState('domcontentloaded')
    } catch (err) {
      console.log('Could not grant geolocation permission via context API:', err)
    }

    // Give geolocation + calendar/tasks fetches time to resolve.
    await page.waitForTimeout(6000)
    await page.screenshot({ path: 'e2e/screenshots/10-widgets-after-fixes.png', fullPage: true })

    const bodyText = (await page.textContent('body')) ?? ''
    console.log('--- Contains "Calendar not connected yet":', bodyText.includes('Calendar not connected yet'))
    console.log('--- Contains "Tasks not connected yet":', bodyText.includes('Tasks not connected yet'))
    console.log('--- Contains "Enable location for weather":', bodyText.includes('Enable location for weather'))
    console.log('--- Contains a real temperature (°C):', /\d+°C/.test(bodyText))
  })
})
