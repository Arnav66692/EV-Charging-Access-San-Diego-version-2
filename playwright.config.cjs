const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests/web',
  use: { baseURL: 'http://127.0.0.1:8767' },
  webServer: { command: 'python3 -m http.server 8767 --directory web', url: 'http://127.0.0.1:8767', reuseExistingServer: !process.env.CI },
  reporter: 'list',
});
