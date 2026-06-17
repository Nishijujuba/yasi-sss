import { expect, type Page, test } from '@playwright/test'

async function startOrContinuePractice(page: Page) {
  const entryButton = page.getByRole('button', { name: /^(\u5f00\u59cb\u7ec3\u4e60|\u7ee7\u7eed\u7ec3\u4e60)$/ })
  await expect(entryButton).toBeVisible()
  await entryButton.click()
}

async function switchToSection(page: Page, section: '01' | '02') {
  await page
    .getByRole('tab', { name: new RegExp(`^(Section\\s*)?${section}|\\u7b2c\\s*${Number(section)}\\s*\\u90e8\\u5206`) })
    .click()
}

function questionInput(page: Page, questionNumber: number) {
  return page.getByLabel(new RegExp(`^(\\u7b2c\\s*)?${questionNumber}\\s*(\\u9898|\\.)?$|^Question\\s*${questionNumber}$`, 'i'))
}

test.describe('practice workflow', () => {
  test('continues practice, persists q1, submits, and resets answers', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('main')).toBeVisible()
    await startOrContinuePractice(page)

    const q1 = questionInput(page, 1)
    await expect(q1).toBeVisible()
    await q1.fill('Ardleigh')

    await switchToSection(page, '02')
    await page.reload()
    await startOrContinuePractice(page)
    await switchToSection(page, '01')
    await expect(questionInput(page, 1)).toHaveValue('Ardleigh')

    await page.getByRole('button', { name: /^\u63d0\u4ea4\u7b54\u6848$/ }).click()
    await expect(page.getByText(/\/\s*40/)).toBeVisible()

    await page.getByRole('button', { name: /^(\u91cd\u7f6e\u7ec3\u4e60|\u91cd\u65b0\u5f00\u59cb)$/ }).click()
    await page.getByRole('button', { name: /^\u786e\u8ba4\u91cd\u7f6e$/ }).click()
    await expect(questionInput(page, 1)).toHaveValue('')
  })

  test('keeps the feedback and action rail scrollable on a short viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1365, height: 768 })
    await page.goto('/')

    await startOrContinuePractice(page)
    await questionInput(page, 1).fill('Ardleigh')
    await page.getByRole('button', { name: /^\u63d0\u4ea4\u7b54\u6848$/ }).click()

    const sidePanel = page.locator('.workspace-side-panel')
    await expect(sidePanel).toHaveCSS('overflow-y', /auto|scroll/)

    const metrics = await sidePanel.evaluate((element) => ({
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    }))
    expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight)

    await sidePanel.evaluate((element) => {
      element.scrollTop = element.scrollHeight
    })

    const sideBox = await sidePanel.boundingBox()
    const followButtonBox = await page.getByRole('button', { name: /^\u539f\u6587\u8ddf\u8bfb$/ }).boundingBox()
    expect(sideBox).not.toBeNull()
    expect(followButtonBox).not.toBeNull()
    expect(followButtonBox!.y + followButtonBox!.height).toBeLessThanOrEqual(sideBox!.y + sideBox!.height + 1)
  })
})
