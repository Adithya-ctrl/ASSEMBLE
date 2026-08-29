import { BACKEND_BASE, BASE, BROWSER_URL, EVIDENCE, puppeteer } from "./browser_support.mjs";

const HEAD = "453c84fc9c05495b1d21b91f505d8179019f296c";

const steps = [];
const consoleEntries = [];
const pageErrors = [];
const failedRequests = [];
const httpErrors = [];
const requestCounts = new Map();

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function record(step, detail) {
  steps.push({ step, detail, at: new Date().toISOString() });
}

async function settle(ms = 250) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function body(page) {
  return page.evaluate(() => document.body?.innerText ?? "");
}

async function waitPath(page, expectedPath) {
  const deadline = Date.now() + 30_000;
  while (new URL(page.url()).pathname !== expectedPath && Date.now() < deadline) await settle(50);
  assert(new URL(page.url()).pathname === expectedPath, `navigation did not reach ${expectedPath}; observed ${page.url()}`);
}

async function waitContent(page, marker) {
  const deadline = Date.now() + 30_000;
  while (!(await body(page)).includes(marker) && Date.now() < deadline) await settle(50);
  assert((await body(page)).includes(marker), `rendered content missing ${marker}`);
}

async function clickLink(page, href) {
  const link = await page.evaluateHandle((target) => [...document.querySelectorAll("a")]
    .find((candidate) => candidate.offsetParent !== null && candidate.getAttribute("href") === target), href);
  const element = link.asElement();
  assert(element, `visible link ${href} missing`);
  await element.focus();
  await page.keyboard.press("Enter");
  await waitPath(page, href);
  await settle();
}

async function clickButton(page, label) {
  const handle = await page.evaluateHandle((text) => [...document.querySelectorAll("button")]
    .find((button) => button.offsetParent !== null && button.textContent?.includes(text)), label);
  const button = handle.asElement();
  assert(button, `visible button containing ${label} missing`);
  assert(!await button.evaluate((node) => node.disabled || node.getAttribute("aria-disabled") === "true"), `${label} was disabled`);
  await button.focus();
  await page.keyboard.press("Enter");
  await settle();
}

async function selectTab(page, label) {
  const handle = await page.evaluateHandle((text) => [...document.querySelectorAll('button[role="tab"]')]
    .find((button) => button.offsetParent !== null && button.textContent?.includes(text)), label);
  const tab = handle.asElement();
  assert(tab, `visible tab ${label} missing`);
  await tab.focus();
  await page.keyboard.press("Enter");
  await settle(180);
  assert(await tab.evaluate((node) => node.getAttribute("aria-selected") === "true"), `${label} tab did not become active`);
}

async function chooseRadio(page, name, labelText) {
  const handle = await page.evaluateHandle(({ group, text }) => [...document.querySelectorAll("label")]
    .find((label) => label.textContent?.includes(text) && label.querySelector(`input[name="${group}"]`)), { group: name, text: labelText });
  const label = handle.asElement();
  assert(label, `appearance option ${labelText} missing`);
  const input = await label.$("input");
  assert(input, `appearance input ${labelText} missing`);
  await input.focus();
  await page.keyboard.press("Space");
  await settle(150);
  assert(await input.evaluate((node) => node.checked), `${labelText} did not become checked`);
}

function monitor(page, label) {
  page.on("console", (message) => consoleEntries.push({ label, type: message.type(), text: message.text(), url: page.url() }));
  page.on("pageerror", (error) => pageErrors.push({ label, message: error.message, url: page.url() }));
  page.on("requestfailed", (request) => failedRequests.push({ label, method: request.method(), url: request.url(), reason: request.failure()?.errorText }));
  page.on("request", (request) => {
    const key = `${request.method()} ${new URL(request.url()).pathname}`;
    requestCounts.set(key, (requestCounts.get(key) ?? 0) + 1);
  });
  page.on("response", (response) => {
    if (response.status() >= 400) httpErrors.push({ label, status: response.status(), method: response.request().method(), url: response.url() });
  });
}

const browser = await puppeteer.connect({ browserURL: BROWSER_URL });

try {
  const pages = (await Promise.all(browser.browserContexts()
    .filter((context) => context !== browser.defaultBrowserContext())
    .map((context) => context.pages())))
    .flat()
    .filter((page) => page.url().startsWith(BASE));
  assert(pages.length === 2, `expected two preserved marathon pages, observed ${pages.length}`);

  let owner;
  let member;
  for (const page of pages) {
    const accountName = await page.$eval("button.identity-account-trigger", (button) => button.textContent ?? "");
    if (accountName.includes("Marathon Owner Updated")) owner = page;
    if (accountName.includes("Marathon Member")) member = page;
  }
  assert(owner && member, "could not identify preserved owner/member contexts");
  monitor(owner, "owner");
  monitor(member, "member");

  const directHealth = await fetch(`${BACKEND_BASE}/api/health`);
  const proxyHealth = await fetch(`${BASE}/api/health`);
  assert(directHealth.status === 200 && proxyHealth.status === 200, "post-restart health failed");
  assert((await directHealth.json()).solver === "ortools-cp-sat", "direct post-restart solver health mismatch");
  assert((await proxyHealth.json()).solver === "ortools-cp-sat", "proxied post-restart solver health mismatch");
  record(30, "Backend restarted on the same private SQLite file; direct and proxied health remained green.");

  if (new URL(owner.url()).pathname !== "/communities") await clickLink(owner, "/communities");
  await owner.reload({ waitUntil: "networkidle0" });
  await waitPath(owner, "/communities");
  await waitContent(owner, "Marathon Neighbourhood");
  let text = await body(owner);
  assert(text.includes("Administrator") && text.includes("Marathon Owner Updated"), "owner session/community/role did not persist");
  await member.reload({ waitUntil: "networkidle0" });
  await waitPath(member, "/communities");
  await waitContent(member, "Marathon Neighbourhood");
  text = await body(member);
  assert(text.includes("Member") && text.includes("Marathon Member"), "member session/community/role did not persist");
  record(31, "Hard reload proved both authenticated sessions, the Collaboration space, and current Administrator/Member roles durable.");

  await clickLink(owner, "/");
  await clickLink(owner, "/projects");
  text = await body(owner);
  assert(text.includes("Your first delivery plan starts with proof"), "Project in-memory empty state missing after hard reload");
  assert(!text.includes("Marathon Clinic Project"), "Project incorrectly persisted across hard reload");
  await owner.goto(`${BASE}/projects/proof`, { waitUntil: "networkidle0" });
  await waitPath(owner, "/projects/proof");
  text = await body(owner);
  assert(text.includes("No Project proof is available") && text.includes("session-only"), "Project proof did not disclose its in-memory boundary");
  record(32, "Project and Project proof truthfully returned to their session-only empty states after hard reload.");

  await clickLink(owner, "/initiatives");
  await clickLink(owner, "/initiatives/BASIC_WORKSHOP/proof");
  await clickButton(owner, "Reset");
  await waitContent(owner, "Awaiting compile");
  record(33, "Planning reset returned Basic proof to Awaiting compile.");

  await clickLink(owner, "/communities");
  const manageHref = await owner.$eval("a", () => [...document.querySelectorAll("a")]
    .find((link) => link.textContent?.includes("Manage"))?.getAttribute("href"));
  assert(manageHref, "persisted community Manage link missing");
  await clickLink(owner, manageHref);
  await selectTab(owner, "Audit events");
  text = await body(owner);
  assert(text.includes("Invitation Accepted") && text.includes("Membership Role Changed"), "persisted audit events missing");
  assert(!documentContainsRawTokenShape(text), "audit UI exposed a raw invitation-token-shaped value");
  await clickLink(member, "/communities");
  await selectTab(member, "Accept invite");
  assert(await member.$eval("#collab-invite-token", (input) => input.value === ""), "invitation token field repopulated after restart/reload");
  assert(!documentContainsRawTokenShape(await body(member)), "member UI exposed a raw invitation-token-shaped value");
  record(34, "Reloaded owner audit and member invitation form exposed no raw invitation token; the token field remained empty.");

  const speculativeRscCancellations = failedRequests.filter((entry) => entry.method === "GET" && entry.reason === "net::ERR_ABORTED" && new URL(entry.url).searchParams.has("_rsc"));
  const unexpectedFailedRequests = failedRequests.filter((entry) => !speculativeRscCancellations.includes(entry));
  const unexpectedConsoleErrors = consoleEntries.filter((entry) => entry.type === "error");
  assert(pageErrors.length === 0, `page errors observed after restart: ${JSON.stringify(pageErrors)}`);
  assert(httpErrors.length === 0, `unexpected HTTP error responses after restart: ${JSON.stringify(httpErrors)}`);
  assert(unexpectedFailedRequests.length === 0, `unexpected failed requests after restart: ${JSON.stringify(unexpectedFailedRequests)}`);
  assert(unexpectedConsoleErrors.length === 0, `unexpected console errors after restart: ${JSON.stringify(unexpectedConsoleErrors)}`);
  record(35, `Post-restart page errors, HTTP errors and unexpected request failures were zero; ${speculativeRscCancellations.length} cancelled speculative RSC request(s) recorded separately.`);

  await clickLink(owner, "/settings");
  await selectTab(owner, "Appearance");
  await chooseRadio(owner, "settings-theme", "Use device setting");
  await chooseRadio(owner, "settings-contrast", "Standard contrast");
  await chooseRadio(owner, "settings-motion", "Follow device preference");
  const cdp = await owner.createCDPSession();
  await cdp.send("Emulation.setPageScaleFactor", { pageScaleFactor: 1 });
  assert(await owner.evaluate(() => document.documentElement.dataset.theme === "system"), "system theme was not restored");
  assert(await owner.evaluate(() => document.documentElement.dataset.motion === "system"), "system motion was not restored");
  assert(!await owner.$eval("main", (node) => node.classList.contains("contrast-high")), "standard contrast was not restored");
  assert((await owner.evaluate(() => window.visualViewport?.scale ?? 1)) === 1, "normal page scale was not restored");
  record(36, "System theme, standard contrast, system motion, and 100% page scale restored.");

  await owner.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
  await member.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 });
  assert(await owner.evaluate(() => window.innerWidth === 1440 && window.innerHeight === 1000), "owner final viewport mismatch");
  assert(await member.evaluate(() => window.innerWidth === 390 && window.innerHeight === 844), "member final viewport mismatch");
  await owner.screenshot({ path: `${EVIDENCE}/step37-owner-settings-1440.png`, fullPage: true });
  await member.screenshot({ path: `${EVIDENCE}/step37-member-communities-390.png`, fullPage: true });
  record(37, "Captured final owner and member screenshots at desktop and mobile viewports.");

  console.log(JSON.stringify({
    status: "PASS_STEPS_30_37",
    head: HEAD,
    steps,
    consoleEntries,
    pageErrors,
    failedRequests,
    httpErrors,
    requestCounts: Object.fromEntries([...requestCounts.entries()].sort()),
  }, null, 2));
} finally {
  browser.disconnect();
}

function documentContainsRawTokenShape(text) {
  return /\b[A-Za-z0-9_-]{40,128}\b/.test(text);
}
