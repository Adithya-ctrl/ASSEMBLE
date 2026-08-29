import { randomBytes } from "node:crypto";

import { BASE, BROWSER_URL, puppeteer } from "./browser_support.mjs";
const username = `pattern-${randomBytes(6).toString("hex")}`;
const password = `P1!${randomBytes(12).toString("base64url")}aA`;

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function activateTab(page, label, expectedField) {
  const handle = await page.evaluateHandle((text) => [...document.querySelectorAll('[role="tab"]')]
    .find((button) => button.textContent?.includes(text)), label);
  const tab = handle.asElement();
  assert(tab, `${label} collaboration tab missing`);
  await tab.focus();
  await page.keyboard.press("Enter");
  assert(await tab.evaluate((button) => button.getAttribute("aria-selected") === "true"), `${label} collaboration tab did not become active`);
  await page.waitForSelector(expectedField, { visible: true });
}

const browser = await puppeteer.connect({ browserURL: BROWSER_URL });
const context = await browser.createBrowserContext();
const page = await context.newPage();
const consoleErrors = [];
const pageErrors = [];

try {
  await page.goto(`${BASE}/signup`, { waitUntil: "networkidle0" });
  await page.type("#auth-username", username);
  await page.type("#auth-email", `${username}@example.test`);
  await page.type("#auth-display-name", "Pattern Regression");
  await page.type("#auth-password", password);
  const signup = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/auth/signup" && response.request().method() === "POST");
  await page.evaluate(() => {
    const submit = [...document.querySelectorAll("button")]
      .find((button) => button.textContent?.trim() === "Create account");
    if (!submit) throw new Error("signup submit missing");
    submit.click();
  });
  assert((await signup).status() === 201, "setup signup failed");
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    const pathReady = new URL(page.url()).pathname === "/communities";
    const contentReady = await page.evaluate(() => document.body.innerText.includes("Collaboration spaces"));
    if (pathReady && contentReady) break;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  assert(new URL(page.url()).pathname === "/communities", `signup did not reach /communities; observed ${page.url()}`);
  assert(await page.evaluate(() => document.body.innerText.includes("Collaboration spaces")), "collaboration route marker missing after signup");

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  const renderedButtons = await page.evaluate(() => [...document.querySelectorAll("button")]
    .map((button) => button.textContent?.trim() ?? ""));
  await activateTab(page, "Create", "#collab-community-slug");
  const slug = await page.$eval("#collab-community-slug", (input) => {
    const check = (value) => {
      input.value = value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      return input.checkValidity();
    };
    return {
      pattern: input.getAttribute("pattern"),
      valid: check("marathon-neighbourhood"),
      invalidUnderscore: check("marathon_neighbourhood"),
      invalidLeadingHyphen: check("-marathon"),
    };
  });

  await activateTab(page, "Accept invite", "#collab-invite-token");
  const token = await page.$eval("#collab-invite-token", (input) => {
    const check = (value) => {
      input.value = value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      return input.checkValidity();
    };
    return {
      pattern: input.getAttribute("pattern"),
      valid: check(`${"A".repeat(40)}_-`),
      invalidDot: check(`${"A".repeat(40)}.`),
      invalidSpace: check(`${"A".repeat(40)} `),
    };
  });

  assert(slug.pattern === String.raw`[a-z0-9](?:[a-z0-9\-]{1,62}[a-z0-9])?`, `unexpected rendered slug pattern ${slug.pattern}`);
  assert(slug.valid === true, "valid hyphenated slug failed mounted validation");
  assert(slug.invalidUnderscore === false, "invalid underscore slug passed mounted validation");
  assert(slug.invalidLeadingHyphen === false, "invalid leading-hyphen slug passed mounted validation");
  assert(token.pattern === String.raw`[A-Za-z0-9_\-]+`, `unexpected rendered token pattern ${token.pattern}`);
  assert(token.valid === true, "valid URL-safe invitation token failed mounted validation");
  assert(token.invalidDot === false, "invalid dotted invitation token passed mounted validation");
  assert(token.invalidSpace === false, "invalid spaced invitation token passed mounted validation");
  assert(consoleErrors.length === 0, `console errors observed: ${consoleErrors.join(" | ")}`);
  assert(pageErrors.length === 0, `page errors observed: ${pageErrors.join(" | ")}`);

  console.log(JSON.stringify({
    status: "PASS",
    browser: await browser.version(),
    sourceHead: "453c84fc9c05495b1d21b91f505d8179019f296c",
    renderedButtons,
    slug,
    token,
    consoleErrorCount: consoleErrors.length,
    pageErrorCount: pageErrors.length,
  }));
} finally {
  await context.close();
  browser.disconnect();
}
