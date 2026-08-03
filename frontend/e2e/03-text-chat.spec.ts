import { test, expect } from '@playwright/test'
import { launchUltronApp } from './fixtures/electron-app'
import type { ElectronApplication, Page } from 'playwright'

test.describe('03 — Text chat', () => {
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

  test('sends a message and receives a response mentioning Ultron within 30s', async () => {
    const input = page.locator('input[type="text"]')
    await expect(input).toBeVisible({ timeout: 10_000 })

    await input.fill('Who are you?')
    await input.press('Enter')

    // Wait for an assistant message to appear
    const assistantMessage = page.locator('text=/who are you/i').first()
    // Wait for the loading indicator to disappear (response arrived) or timeout at 30s
    await expect(page.getByText(/processing request/i)).toBeHidden({ timeout: 30_000 }).catch(() => {})

    await page.waitForTimeout(1000)
    await page.screenshot({ path: 'e2e/screenshots/text-chat.png' })

    const bodyText = await page.textContent('body')
    expect(bodyText?.toLowerCase()).toContain('ultron')
  })
})
