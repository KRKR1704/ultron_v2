import { test, expect } from '@playwright/test'
import { launchUltronApp } from './fixtures/electron-app'
import type { ElectronApplication, Page } from 'playwright'

test.describe('05 — Audio playback', () => {
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

  test('sends a message and checks for audio-related console errors', async () => {
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })
    page.on('pageerror', (err) => consoleErrors.push(err.message))

    const input = page.locator('input[type="text"]')
    await input.fill('Say hello')
    await input.press('Enter')

    await page.waitForTimeout(15_000)

    const audioErrors = consoleErrors.filter((e) => /audio|decode|playback/i.test(e))
    // eslint-disable-next-line no-console
    console.log('All console errors observed:', consoleErrors)
    // eslint-disable-next-line no-console
    console.log('Audio-related console errors:', audioErrors)

    expect(audioErrors, `Audio errors: ${JSON.stringify(audioErrors)}`).toHaveLength(0)
  })
})
