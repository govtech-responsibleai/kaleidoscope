import { test as base, type Page } from "@playwright/test";
import { setupApiMocks } from "./api-mocks";

// Playwright fixture that pre-injects auth into localStorage so AuthCheck
// doesn't redirect to /login. All API calls are mocked by default.
export const test = base.extend<{ authedPage: Page }>({
  authedPage: async ({ page }, use) => {
    await page.addInitScript(() => {
      localStorage.setItem("token", "fake-token-12345");
      localStorage.setItem("username", "testuser");
      localStorage.setItem("is_admin", "false");
    });
    await setupApiMocks(page);
    await use(page);
  },
});

export { expect } from "@playwright/test";
