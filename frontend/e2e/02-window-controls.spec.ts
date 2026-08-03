import { test, expect } from '@playwright/test'
import { launchUltronApp } from './fixtures/electron-app'
import type { ElectronApplication, Page } from 'playwright'

test.describe('02 — Window controls', () => {
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

  test('custom titlebar visible, minimize/maximize/restore work, close button present', async () => {
    // Custom titlebar
    const titleBar = page.locator('text=ULTRON').first()
    await expect(titleBar).toBeVisible()

    // Drag region CSS
    const dragRegion = await page.evaluate(() => {
      const bar = Array.from(document.querySelectorAll('div')).find((el) =>
        el.textContent?.includes('ULTRON') && el.className.includes(''),
      )
      return bar ? getComputedStyle(bar).getPropertyValue('-webkit-app-region') : null
    })
    // eslint-disable-next-line no-console
    console.log('titlebar -webkit-app-region:', dragRegion)

    const minimizeBtn = page.locator('button[aria-label="Minimize"]')
    const maximizeBtn = page.locator('button[aria-label="Maximize"], button[aria-label="Restore"]')
    const closeBtn = page.locator('button[aria-label="Close"]')

    await expect(minimizeBtn).toBeVisible()
    await expect(maximizeBtn).toBeVisible()
    await expect(closeBtn).toBeVisible()

    // Maximize / restore toggle
    const isMaximizedBefore = await app.evaluate(({ BrowserWindow }) =>
      BrowserWindow.getAllWindows()[0]?.isMaximized(),
    )
    await maximizeBtn.click()
    await page.waitForTimeout(500)
    const isMaximizedAfter = await app.evaluate(({ BrowserWindow }) =>
      BrowserWindow.getAllWindows()[0]?.isMaximized(),
    )
    expect(isMaximizedAfter).not.toBe(isMaximizedBefore)

    // Toggle back
    await maximizeBtn.click()
    await page.waitForTimeout(500)
    const isMaximizedRestored = await app.evaluate(({ BrowserWindow }) =>
      BrowserWindow.getAllWindows()[0]?.isMaximized(),
    )
    expect(isMaximizedRestored).toBe(isMaximizedBefore)

    // Minimize
    await minimizeBtn.click()
    await page.waitForTimeout(500)
    const isMinimized = await app.evaluate(({ BrowserWindow }) =>
      BrowserWindow.getAllWindows()[0]?.isMinimized(),
    )
    expect(isMinimized).toBe(true)

    // Restore from minimize so the window is usable for later assertions
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0]?.restore())

    // Do NOT click the close button — would end the Electron process mid-suite.
    await expect(closeBtn).toBeEnabled()
  })
})
