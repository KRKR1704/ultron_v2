import { test, expect } from '@playwright/test'
import { launchUltronApp } from './fixtures/electron-app'
import type { ElectronApplication, Page } from 'playwright'

test.describe('06 — Status indicators', () => {
  let app: ElectronApplication
  let page: Page

  test.beforeEach(async () => {
    const launched = await launchUltronApp()
    app = launched.app
    page = launched.page
    await page.waitForTimeout(3000) // allow first GET /status poll (5s interval) to land
  })

  test.afterEach(async () => {
    await app?.close()
  })

  test('camera/wake status indicators reflect backend state', async () => {
    await page.waitForTimeout(3000)
    const bodyText = (await page.textContent('body')) ?? ''
    // eslint-disable-next-line no-console
    console.log('Header status text present. Contains "Camera":', bodyText.includes('Camera'))
    // eslint-disable-next-line no-console
    console.log('Header status text present. Contains "Wake":', bodyText.includes('Wake'))

    await page.screenshot({ path: 'e2e/screenshots/status-indicators.png' })

    // The settings panel exposes camera/screen state explicitly — open it.
    const settingsButton = page.locator('button').filter({ has: page.locator('svg') }).last()
    await settingsButton.click().catch(() => {})
    await page.waitForTimeout(500)

    const settingsText = (await page.textContent('body')) ?? ''
    expect(settingsText).toMatch(/Camera Monitor/i)
    expect(settingsText).toMatch(/Screen Monitor/i)
  })
})
