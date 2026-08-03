import { test, expect } from '@playwright/test'
import { launchUltronApp } from './fixtures/electron-app'
import type { ElectronApplication, Page } from 'playwright'

test.describe('09 — Full conversation flow', () => {
  let app: ElectronApplication
  let page: Page

  test.afterEach(async () => {
    await app?.close()
  })

  test('realistic user journey: launch, chat, mode switch, casual chat, mode switch back, search', async () => {
    const launched = await launchUltronApp()
    app = launched.app
    page = launched.page
    await page.waitForTimeout(1500)
    await page.screenshot({ path: 'e2e/screenshots/09-01-launch.png' })

    const input = page.locator('input[type="text"]')

    // Step 1 — greet
    await input.fill('Hello, who are you?')
    await input.press('Enter')
    await page.waitForTimeout(15_000)
    await page.screenshot({ path: 'e2e/screenshots/09-02-greeting-response.png' })

    // Step 2 — switch to casual
    const modeButton = page.locator('button', { hasText: /Professional|Casual/ }).first()
    const beforeLabel = await modeButton.textContent()
    await modeButton.click()
    await page.waitForTimeout(1500)
    await page.screenshot({ path: 'e2e/screenshots/09-03-casual-mode.png' })

    // Step 3 — casual message
    await input.fill("What's up?")
    await input.press('Enter')
    await page.waitForTimeout(15_000)
    await page.screenshot({ path: 'e2e/screenshots/09-04-casual-response.png' })

    // Step 4 — switch back
    await modeButton.click()
    await page.waitForTimeout(1500)
    const afterLabel = await modeButton.textContent()
    await page.screenshot({ path: 'e2e/screenshots/09-05-professional-mode.png' })

    // Step 5 — search
    await input.fill('Search for Python tutorials')
    await input.press('Enter')
    await page.waitForTimeout(20_000)
    await page.screenshot({ path: 'e2e/screenshots/09-06-search-response.png' })

    // eslint-disable-next-line no-console
    console.log('Mode label before toggle cycle:', beforeLabel, '- after full cycle:', afterLabel)
    expect(afterLabel).toBe(beforeLabel)
  })
})
