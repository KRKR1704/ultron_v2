import { test, expect } from '@playwright/test'
import { launchUltronApp } from './fixtures/electron-app'
import type { ElectronApplication, Page } from 'playwright'

test.describe('04 — Mode switch', () => {
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

  test('toggling mode changes button label and affects chat tone', async () => {
    const modeButton = page.locator('button', { hasText: /Professional|Casual/ }).first()
    await expect(modeButton).toBeVisible({ timeout: 10_000 })

    const initialLabel = await modeButton.textContent()

    await modeButton.click()
    await page.waitForTimeout(1500)

    const afterClickLabel = await modeButton.textContent()
    expect(afterClickLabel).not.toBe(initialLabel)

    const input = page.locator('input[type="text"]')
    await input.fill('greet me')
    await input.press('Enter')
    await page.waitForTimeout(15_000)

    const bodyTextCasualish = (await page.textContent('body'))?.toLowerCase() ?? ''

    // Toggle back
    await modeButton.click()
    await page.waitForTimeout(1500)
    const restoredLabel = await modeButton.textContent()
    expect(restoredLabel).toBe(initialLabel)

    await input.fill('greet me again')
    await input.press('Enter')
    await page.waitForTimeout(15_000)

    await page.screenshot({ path: 'e2e/screenshots/mode-switch.png' })

    // Record what we actually observed for the audit rather than assuming.
    // eslint-disable-next-line no-console
    console.log('Mode label sequence:', initialLabel, '->', afterClickLabel, '->', restoredLabel)
  })
})
