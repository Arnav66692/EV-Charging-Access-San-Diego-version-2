const { test, expect } = require('@playwright/test');
const path = require('node:path');

// Use the exact pinned Leaflet release without making CI depend on CDN uptime.
test.beforeEach(async ({ page }) => {
  await page.route('https://unpkg.com/leaflet@1.9.4/dist/**', route => {
    const asset = new URL(route.request().url()).pathname.split('/dist/')[1];
    return route.fulfill({ path: path.join(__dirname, '../../node_modules/leaflet/dist', asset) });
  });
});

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`map and controls at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/');
    await expect(page.getByRole('status')).toContainText('Map ready');
    await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
    const controls = await page.locator('#controls').boundingBox();
    expect(controls.x).toBeGreaterThanOrEqual(0);
    expect(controls.x + controls.width).toBeLessThanOrEqual(viewport.width);
    expect(controls.y).toBeGreaterThanOrEqual(0);
    expect(controls.y + controls.height).toBeLessThan(viewport.height);
    await page.getByRole('button', { name: 'Access percentile', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Access percentile', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await page.getByLabel('Outline DAC areas').check();
    await page.getByLabel('Candidate sites by tier').check();
    await expect(page.getByRole('status')).toHaveText('Candidate sites loaded.');
    expect(await page.locator('.leaflet-overlay-pane path').count()).toBeGreaterThan(10);
    await page.getByLabel('Candidate sites by tier').uncheck();
    expect(errors).toEqual([]);
    expect(await page.locator('.leaflet-tile').count()).toBe(0);
  });
}

test('base data failure is visible and disables controls', async ({ page }) => {
  await page.route('**/data/block_groups.geojson', route => route.fulfill({ status: 503, body: 'unavailable' }));
  await page.goto('/');
  await expect(page.getByRole('status')).toContainText('Map data could not be loaded');
  await expect(page.getByLabel('Outline DAC areas')).toBeDisabled();
});

test('candidate failure can be retried', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('status')).toContainText('Map ready');
  await page.route('**/data/candidates.geojson', route => route.fulfill({ status: 503, body: 'unavailable' }));
  await page.getByLabel('Candidate sites by tier').check();
  await expect(page.getByRole('status')).toContainText('Candidate sites unavailable');
  await expect(page.getByLabel('Candidate sites by tier')).not.toBeChecked();
  await expect(page.getByLabel('Candidate sites by tier')).toBeEnabled();
  await page.unroute('**/data/candidates.geojson');
  await page.getByLabel('Candidate sites by tier').check();
  await expect(page.getByRole('status')).toHaveText('Candidate sites loaded.');
});
