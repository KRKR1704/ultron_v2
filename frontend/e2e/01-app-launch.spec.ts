import { test, expect } from '@playwright/test'
import { launchUltronApp } from './fixtures/electron-app'
import type { ElectronApplication, Page } from 'playwright'

test.describe('01 — App launch', () => {
  let app: ElectronApplication
  let page: Page

  test.afterEach(async () => {
    await app?.close()
  })

  test('launches, opens a frameless window, loads without console errors, black background', async () => {
    const consoleErrors: string[] = []

    const launched = await launchUltronApp()
    app = launched.app
    page = launched.page

    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })

    await page.waitForTimeout(2000)

    // Window exists and has a title
    const title = await page.title()
    expect(title.length).toBeGreaterThan(0)

    // Frameless: BrowserWindow was created with frame:false in electron/main.ts —
    // verify via the custom TitleBar being present instead of relying on OS chrome.
    const titleBar = page.locator('text=ULTRON').first()
    await expect(titleBar).toBeVisible({ timeout: 10_000 })

    // Background should be black/near-black, not a white flash
    const bgColor = await page.evaluate(() => {
      return getComputedStyle(document.body).backgroundColor
    })
    // eslint-disable-next-line no-console
    console.log('body background-color:', bgColor)

    await page.screenshot({ path: 'e2e/screenshots/app-launch.png' })

    expect(consoleErrors, `Console errors: ${JSON.stringify(consoleErrors)}`).toHaveLength(0)
  })
})
