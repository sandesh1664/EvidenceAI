import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const secret = "A sufficiently long test password!";
async function register(page: Page, label = "Researcher") {
  const email = `research-${crypto.randomUUID()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Full name").fill(label);
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(secret);
  const registered = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/auth/register") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  const response = await registered;
  const sentId = response.request().headers()["x-request-id"];
  expect(sentId).toMatch(/^[0-9a-f-]{36}$/);
  expect(response.headers()["x-request-id"]).toBe(sentId);
  await expect(
    page.getByRole("heading", { name: "Your workspaces" }),
  ).toBeVisible();
  return email;
}
async function workspace(page: Page, name: string) {
  await page.bringToFront();
  await expect(
    page.getByRole("heading", { name: "Your workspaces", level: 1 }),
  ).toBeVisible();
  await page.getByLabel("Workspace name", { exact: true }).fill(name);
  await page
    .getByRole("button", { name: "+ Create workspace", exact: true })
    .click();
  await page
    .getByRole("link", { name: new RegExp(name) })
    .last()
    .click();
  await expect(
    page.getByRole("heading", { name, exact: true, level: 1 }),
  ).toBeVisible();
  return new URL(page.url()).pathname;
}
async function nav(page: Page, name: string) {
  await page.bringToFront();
  await page
    .getByRole("navigation")
    .getByRole("link", { name, exact: true })
    .click();
}

test("real authenticated research, workers, citations, persistence and retention", async ({
  page,
  context,
}) => {
  await register(page);
  const root = await workspace(page, "Solar evidence");
  const cookies = await context.cookies("http://localhost:18000");
  const session = cookies.find(
    (cookie) => cookie.name === "evidenceai_session",
  );
  expect(session?.httpOnly).toBe(true);
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
  await nav(page, "Documents");
  await page.getByLabel("Upload documents").setInputFiles({
    name: "solar.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "Solar panels convert sunlight into renewable electricity.\nSolar panels have a 10 year warranty.",
    ),
  });
  await expect(
    page.getByText("1 file uploaded.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("Extraction complete", { exact: true }),
  ).toBeVisible({ timeout: 25000 });
  await expect(page.getByText("Indexed", { exact: true })).toBeVisible({
    timeout: 25000,
  });
  await nav(page, "Search");
  await page.getByLabel("Search query").fill("Solar panels");
  await page.getByRole("button", { name: "Search passages" }).click();
  await expect(
    page.getByText(/passages returned, ordered by relevance/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Inspect source" }).first().click();
  await expect(
    page.getByRole("region", { name: "Source details" }),
  ).toContainText("Solar panels");
  await nav(page, "Research");
  await page
    .getByLabel("Your research question")
    .fill("What do solar panels convert?");
  await page.getByRole("button", { name: "Ask question ↗" }).click();
  await expect(page.getByText("Offline mock · source selection")).toBeVisible();
  await page.getByRole("button", { name: "Open source C1" }).click();
  await expect(
    page.getByRole("region", { name: "Source details" }),
  ).toContainText("solar.txt");
  await nav(page, "Conversations");
  await page.getByLabel("Conversation title").fill("Solar follow-ups");
  await page.getByRole("button", { name: "+ New conversation" }).click();
  await expect(
    page.getByRole("heading", { name: "Solar follow-ups" }),
  ).toBeVisible();
  const conversationUrl = page.url();
  await page
    .getByLabel("Ask a follow-up question")
    .fill("What do solar panels convert?");
  await page.getByRole("button", { name: "Send question ↗" }).click();
  await expect(page.getByText("Offline mock · source selection")).toBeVisible();
  await page
    .getByLabel("Ask a follow-up question")
    .fill("What is their warranty?");
  await page.getByRole("button", { name: "Send question ↗" }).click();
  await expect(
    page
      .getByText("Solar panels have a 10 year warranty.", { exact: false })
      .last(),
  ).toBeVisible();
  await page.reload();
  await expect(
    page
      .getByText("Solar panels have a 10 year warranty.", { exact: false })
      .last(),
  ).toBeVisible();
  await nav(page, "Documents");
  await page
    .getByRole("button", { name: "Delete document", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm delete document" }).click();
  await expect(
    page.getByRole("heading", { name: "No sources yet" }),
  ).toBeVisible();
  await page.goto(conversationUrl);
  await page.getByRole("button", { name: "Open source C1" }).first().click();
  await expect(page.getByText("Original document deleted")).toBeVisible();
  await page.getByText("Conversation settings", { exact: true }).click();
  await page
    .getByRole("button", { name: "Archive conversation", exact: true })
    .click();
  await expect(
    page.getByText("Archived conversations accept no new questions.", {
      exact: false,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Restore conversation" }).click();
  await expect(page.getByLabel("Ask a follow-up question")).toBeEnabled();
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  await page.goto(root);
  await expect(
    page.getByRole("heading", { name: "Solar evidence", level: 1 }),
  ).toBeVisible();
  await page.screenshot({
    path: "/tmp/evidenceai-dashboard.png",
    fullPage: true,
  });
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  expect(browserErrors).toEqual([]);
  await page.getByRole("button", { name: "Sign out", exact: false }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back" }),
  ).toBeVisible();
  await page.goto(conversationUrl);
  await expect(
    page.getByRole("heading", { name: "Welcome back" }),
  ).toBeVisible();
});

test("real CSRF, untrusted origin, safe private HTML and expired session", async ({
  page,
  context,
  request,
}) => {
  await register(page);
  const root = await workspace(page, "CSRF checks");
  const missing = await page.evaluate(async () => {
    const response = await fetch("http://localhost:18000/api/v1/workspaces/", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Blocked" }),
    });
    return response.status;
  });
  expect(missing).toBe(403);
  const untrusted = await request.post(
    "http://localhost:18000/api/v1/workspaces/",
    {
      headers: {
        Origin: "https://untrusted.invalid",
        "X-CSRF-Protection": "1",
      },
      data: { name: "Blocked" },
    },
  );
  expect(untrusted.status()).toBe(403);
  const html = await request.get("http://localhost:3100" + root);
  expect(await html.text()).not.toContain("CSRF checks");
  expect(html.headers()["cache-control"]).toContain("no-store");
  expect(html.headers()["content-security-policy"]).toContain("'nonce-");
  expect(html.headers()["content-security-policy"]).not.toContain(
    "script-src 'self' 'unsafe-inline'",
  );
  await context.clearCookies();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Welcome back" }),
  ).toBeVisible();
});

test("mobile layout, keyboard navigation, themes and ownership boundaries", async ({
  page,
  browser,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await register(page, "Mobile researcher");
  const root = await workspace(page, "Mobile evidence");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(
    page.getByRole("complementary", { name: "Main navigation" }),
  ).toBeVisible();
  await nav(page, "Settings");
  await page.getByLabel("Theme").selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "/tmp/evidenceai-mobile.png", fullPage: true });
  const issues = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(issues.violations).toEqual([]);
  const other = await browser.newContext();
  const outsider = await other.newPage();
  await register(outsider, "Other researcher");
  await outsider.goto(root);
  await expect(outsider.getByRole("main").getByRole("alert")).toContainText(
    /not found|unavailable/i,
  );
  await expect(
    outsider.getByRole("heading", { name: "Mobile evidence" }),
  ).not.toBeVisible();
  await other.close();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
});

test("real membership roles, ownership transfer and eligible workspace deletion", async ({
  page,
  browser,
}) => {
  await register(page, "Project owner");
  const root = await workspace(page, "Team research");
  const colleagueContext = await browser.newContext();
  const colleague = await colleagueContext.newPage();
  await register(colleague, "Project colleague");
  const account = await colleague.evaluate(async () => {
    const response = await fetch("http://localhost:18000/api/v1/auth/me", {
      credentials: "include",
    });
    return response.json();
  });
  await nav(page, "Members");
  await page.getByLabel("Account ID", { exact: true }).fill(account.id);
  await page
    .getByRole("combobox", { name: "Role", exact: true })
    .selectOption("member");
  await page.getByRole("button", { name: "Add member", exact: true }).click();
  await expect(page.getByText("Member added.", { exact: true })).toBeVisible();
  await colleague.goto(root + "/documents");
  await expect(
    colleague.getByRole("heading", { name: "Document library", exact: true }),
  ).toBeVisible();
  await expect(colleague.getByLabel("Upload documents")).not.toBeVisible();
  await page.bringToFront();
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().endsWith("/members/" + account.id) &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    ),
    page
      .getByLabel("Role for " + account.id, { exact: true })
      .selectOption("admin"),
  ]);
  await colleague.reload();
  await expect(colleague.getByLabel("Upload documents")).toBeVisible();
  await page
    .getByRole("button", { name: "Transfer ownership", exact: true })
    .click();
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().endsWith("/transfer-ownership") &&
        response.status() === 200,
    ),
    page.getByRole("button", { name: "Confirm transfer ownership" }).click(),
  ]);
  await page.goto(root);
  await expect(
    page.getByRole("heading", { name: "Team research", level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Delete workspace", exact: true }),
  ).not.toBeVisible();
  await nav(page, "Workspaces");
  const empty = await workspace(page, "Disposable project");
  expect(empty).not.toBe(root);
  await page
    .getByRole("button", { name: "Delete workspace", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm delete workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Your workspaces", level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Disposable project", exact: true }),
  ).not.toBeVisible();
  await colleagueContext.close();
});

test("network and provider failures remain recoverable and source text is inert", async ({ page }) => {
  await register(page);
  await workspace(page, "<script>window.compromised=true</script>");
  expect(await page.evaluate(() => (window as Window & { compromised?: boolean }).compromised)).toBeUndefined();
  await nav(page, "Search");
  await page.route("**/api/v1/workspaces/*/search", (route) => route.abort("failed"));
  await page.getByLabel("Search query").fill("Solar evidence");
  await page.getByRole("button", { name: "Search passages" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toBeVisible();
  await expect(page.getByRole("button", { name: "Search passages" })).toBeEnabled();
  await page.unroute("**/api/v1/workspaces/*/search");
  await page.route("**/api/v1/workspaces/*/search", (route) => route.fulfill({
    status: 503,
    contentType: "application/json",
    headers: { "Access-Control-Allow-Origin": "http://localhost:3100", "Access-Control-Allow-Credentials": "true" },
    body: JSON.stringify({ detail: "Search provider temporarily unavailable" }),
  }));
  await page.getByRole("button", { name: "Search passages" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toBeVisible();
  await expect(page.getByRole("button", { name: "Search passages" })).toBeEnabled();
  await page.unroute("**/api/v1/workspaces/*/search");
  await page.getByRole("button", { name: "Search passages" }).click();
  await expect(page.getByText("No matching indexed passages")).toBeVisible();
});

test("registration and login work through native keyboard form navigation", async ({ page }) => {
  const email = `keyboard-${crypto.randomUUID()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Full name").focus();
  await page.keyboard.type("Keyboard researcher");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Email address")).toBeFocused();
  await page.keyboard.type(email);
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password", { exact: true })).toBeFocused();
  await page.keyboard.type(secret);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Your workspaces" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: false }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await page.getByLabel("Email address").focus();
  await page.keyboard.type(email);
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password", { exact: true })).toBeFocused();
  await page.keyboard.type(secret);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Your workspaces" })).toBeVisible();
});
