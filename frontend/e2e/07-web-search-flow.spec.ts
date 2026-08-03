import { test, expect } from '@playwright/test'
import { launchUltronApp } from './fixtures/electron-app'
import type { ElectronApplication, Page } from 'playwright'

test.describe('07 — Web search flow', () => {
  let app: ElectronApplication
  let page: Page

  test.beforeEach(async () => {
    const launched = await launchUltronApp()
    app = launched.app
    page = launched.page
    await page.waitForTimeout(1500)
  })

  test.afterEach(async () => {
    await app?.close()
  })

  test('search request returns a proper response, not an error state', async () => {
    const input = page.locator('input[type="text"]')
    await input.fill('search for latest AI news')
    await input.press('Enter')

    await page.waitForTimeout(20_000)
    await page.screenshot({ path: 'e2e/screenshots/web-search-flow.png' })

    const bodyText = (await page.textContent('body'))?.toLowerCase() ?? ''
    expect(bodyText).not.toContain('connection error')
    expect(bodyText).not.toContain('422')
    expect(bodyText.length).toBeGreaterThan(0)
  })
})
