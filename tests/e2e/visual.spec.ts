import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { expect, type Page, type TestInfo, test } from '@playwright/test'

const viewports = [
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
]

async function waitForImages(page: Page) {
  await page.waitForFunction(() =>
    Array.from(document.images).every((image) => image.complete && image.naturalWidth > 0),
  )
}

async function saveScreenshot(page: Page, testInfo: TestInfo, viewportName: string, name: string) {
  await waitForImages(page)
  if (testInfo.project.name !== 'chrome') {
    return
  }
  const dir = path.join('output', 'playwright', viewportName)
  await mkdir(dir, { recursive: true })
  await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage: true })
}

async function enterPractice(page: Page) {
  await page.getByRole('button', { name: /^(\u5f00\u59cb\u7ec3\u4e60|\u7ee7\u7eed\u7ec3\u4e60)$/ }).click()
}

async function switchToSection(page: Page, section: '01' | '02') {
  await page
    .getByRole('tab', { name: new RegExp(`^(Section\\s*)?${section}|\\u7b2c\\s*${Number(section)}\\s*\\u90e8\\u5206`) })
    .click()
}

function questionInput(page: Page, questionNumber: number) {
  return page.getByLabel(new RegExp(`^(\\u7b2c\\s*)?${questionNumber}\\s*(\\u9898|\\.)?$|^Question\\s*${questionNumber}$`, 'i'))
}

async function submitPractice(page: Page) {
  await page.getByLabel(/^(\u7b2c\s*)?1\s*(\u9898|\.)?$|^Question\s*1$/i).fill('Ardleigh')
  await page.getByRole('button', { name: /^\u63d0\u4ea4\u7b54\u6848$/ }).click()
  await expect(page.getByText(/\/\s*40/)).toBeVisible()
}

for (const viewport of viewports) {
  const viewportName = `${viewport.width}x${viewport.height}`

  test.describe(`visual coverage ${viewportName}`, () => {
    test.use({ viewport })

    test(`captures home, section 1, section 2, and submitted states at ${viewportName}`, async ({ page }, testInfo) => {
      await page.goto('/')
      await expect(page.getByRole('main')).toBeVisible()
      await saveScreenshot(page, testInfo, viewportName, 'home')

      await enterPractice(page)
      await questionInput(page, 1).scrollIntoViewIfNeeded()
      await expect(questionInput(page, 1)).toBeVisible()
      await saveScreenshot(page, testInfo, viewportName, 'section-1')

      await switchToSection(page, '02')
      await saveScreenshot(page, testInfo, viewportName, 'section-2')

      await switchToSection(page, '01')
      await submitPractice(page)
      await saveScreenshot(page, testInfo, viewportName, 'submitted')
    })
  })
}
