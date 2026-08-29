import { BASE, BROWSER_URL, EVIDENCE, puppeteer } from "./browser_support.mjs";

const HEAD = "453c84fc9c05495b1d21b91f505d8179019f296c";

const consoleEntries = [];
const pageErrors = [];
const failedRequests = [];
const httpErrors = [];
const requestCounts = new Map();
const visualEvidence = [];
const routeMatrix = [];
let zoomEvidence = null;
let stage = "setup";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function settle(ms = 300) {
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
  const handle = await page.evaluateHandle((target) => [...document.querySelectorAll("a")]
    .find((link) => link.offsetParent !== null && link.getAttribute("href") === target), href);
  const link = handle.asElement();
  assert(link, `visible link ${href} missing`);
  await link.focus();
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
    .find((tab) => tab.offsetParent !== null && tab.textContent?.includes(text)), label);
  const tab = handle.asElement();
  assert(tab, `visible tab ${label} missing`);
  await tab.focus();
  await page.keyboard.press("Enter");
  await settle(180);
  assert(await tab.evaluate((node) => node.getAttribute("aria-selected") === "true"), `${label} tab did not become active`);
}

async function action(page, label, path, expectedStatus = 200) {
  const responsePromise = page.waitForResponse((response) => new URL(response.url()).pathname === path && response.request().method() === "POST");
  await clickButton(page, label);
  const response = await responsePromise;
  assert(response.status() === expectedStatus, `${path} returned ${response.status()}, expected ${expectedStatus}`);
  await settle(400);
  return response;
}

async function unlockAction(page) {
  const unlock = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/unlock" && response.request().method() === "POST");
  const plan = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/plan" && response.request().method() === "POST");
  await clickButton(page, "FIND MINIMUM UNLOCK");
  assert((await unlock).status() === 200, "unlock failed");
  assert((await plan).status() === 200, "plan failed");
  await settle(400);
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

async function capture(page, name) {
  const path = `${EVIDENCE}/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  visualEvidence.push({ name, viewport: await page.evaluate(() => ({ width: innerWidth, height: innerHeight })), path });
}

async function routeAudit(page, pathname, viewport) {
  await page.setViewport({ ...viewport, deviceScaleFactor: 1 });
  await page.goto(`${BASE}${pathname}`, { waitUntil: "networkidle0" });
  await settle(150);
  const audit = await page.evaluate(() => {
    const visible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    };
    const controls = [...document.querySelectorAll('a, button, input, select, textarea, summary, [role="button"], [role="tab"]')]
      .filter(visible)
      .map((element) => {
        const associatedLabel = element.labels?.[0] ?? null;
        const rect = associatedLabel && ["checkbox", "radio"].includes(element.type)
          ? associatedLabel.getBoundingClientRect()
          : element.getBoundingClientRect();
        const labelledBy = element.getAttribute("aria-labelledby")?.split(/\s+/).map((id) => document.getElementById(id)?.textContent ?? "").join(" ") ?? "";
        const label = associatedLabel?.textContent ?? "";
        const name = [
          element.getAttribute("aria-label"),
          labelledBy,
          label,
          element.textContent,
          element.getAttribute("alt"),
          element.getAttribute("title"),
        ].map((value) => value?.trim() ?? "").find(Boolean) ?? "";
        return { tag: element.tagName, name: name.trim(), width: rect.width, height: rect.height };
      });
    return {
      path: location.pathname,
      title: document.title,
      mains: document.querySelectorAll("main").length,
      h1: [...document.querySelectorAll("h1")].map((node) => node.textContent?.trim() ?? ""),
      liveRegions: document.querySelectorAll('[aria-live], [role="status"]').length,
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      unnamed: controls.filter((item) => !item.name),
      undersized: controls.filter((item) => item.width < 44 || item.height < 44),
      controlCount: controls.length,
    };
  });
  assert(audit.mains === 1, `${pathname} had ${audit.mains} main landmarks at ${viewport.width}`);
  assert(audit.h1.length === 1 && audit.h1[0], `${pathname} h1 hierarchy root missing at ${viewport.width}`);
  assert(audit.overflow <= 1, `${pathname} horizontally overflowed ${audit.overflow}px at ${viewport.width}`);
  assert(audit.unnamed.length === 0, `${pathname} had unnamed controls at ${viewport.width}: ${JSON.stringify(audit.unnamed)}`);
  if ([320, 390, 1440].includes(viewport.width)) {
    assert(audit.undersized.length === 0, `${pathname} had sub-44px controls at ${viewport.width}: ${JSON.stringify(audit.undersized)}`);
  }
  routeMatrix.push({ viewport, ...audit });
}

const browser = await puppeteer.connect({ browserURL: BROWSER_URL });
const context = await browser.createBrowserContext();
const page = await context.newPage();
monitor(page, "supplemental");

try {
  stage = "basic-s0-proof";
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await page.goto(`${BASE}/initiatives/BASIC_WORKSHOP/proof`, { waitUntil: "networkidle0" });
  await waitContent(page, "Initiative proof");
  await action(page, "COMPILE COMMUNITY", "/api/analyse");
  await action(page, "ASSEMBLE NOW", "/api/analyse");
  assert((await body(page)).includes("Basic Workshop analysis returned OPTIMAL"), "Basic S0 proof missing");
  await clickLink(page, "/resilience");
  await page.select('select[id$="-stress-initiative"]', "BASIC_WORKSHOP");
  await action(page, "Run stress test", "/api/stress-test");
  let text = await body(page);
  assert(text.includes("4 critical") && text.includes("0 unknown") && text.includes("0%"), "Basic S0 stress truth mismatch");
  assert((text.match(/Outcome evidence/g) ?? []).length === 4, "Basic S0 did not render four outcomes");
  await capture(page, "supplemental-basic-s0-stress-1440");

  stage = "s0-frontier";
  await selectTab(page, "Capability frontier");
  await action(page, "Compare actions", "/api/frontier");
  text = await body(page);
  assert(text.includes("Highest leverage") && text.includes("Train two digital helpers"), "S0 highest-leverage training claim missing");
  const frontierCards = await page.evaluate(() => [...document.querySelectorAll("article")].map((card) => card.innerText));
  const trainingCard = frontierCards.find((card) => card.includes("Train two digital helpers"));
  const borrowCard = frontierCards.find((card) => card.includes("Borrow two additional laptops"));
  const recruitCards = frontierCards.filter((card) => card.includes("Recruit external digital helper"));
  assert(trainingCard?.includes("Highest leverage") && trainingCard.includes("Pareto-efficient"), "S0 training card leverage/Pareto truth mismatch");
  assert(borrowCard?.includes("Pareto-efficient"), "S0 borrow card Pareto truth mismatch");
  assert(recruitCards.length === 2 && recruitCards.every((card) => !card.includes("Pareto-efficient")), "S0 recruit cards incorrectly marked Pareto");
  assert((text.match(/Pareto-efficient/g) ?? []).length === 2, "S0 frontier did not render exactly two Pareto badges");
  assert(text.includes("Results are not an action sequence"), "frontier operational-isolation notice missing");

  stage = "judge-disclosure";
  const projectBeforeJudge = await page.evaluate(() => document.body.innerText.includes("Project status"));
  assert(projectBeforeJudge === false, "counterfactual UI exposed an operational Project");
  assert(await page.evaluate((labels) => [...document.querySelectorAll("details")]
    .filter((node) => labels.includes(node.querySelector("summary")?.textContent?.trim() ?? ""))
    .every((node) => !node.open), ["Source evidence", "Action evidence", "Technical evidence"]), "Resilience technical evidence unexpectedly open before Judge mode");
  await clickButton(page, "View proof");
  const judgeOn = await page.evaluateHandle(() => [...document.querySelectorAll('[role="menuitem"]')]
    .find((item) => item.textContent?.includes("Judge proof mode off")));
  assert(judgeOn.asElement(), "Judge mode enable item missing");
  await judgeOn.asElement().focus();
  await page.keyboard.press("Enter");
  await settle(250);
  assert(await page.evaluate((labels) => [...document.querySelectorAll("details")]
    .filter((node) => labels.some((label) => node.querySelector("summary")?.textContent?.includes(label)))
    .some((node) => node.open), ["Source evidence", "Action evidence", "Technical evidence"]), "Judge mode did not disclose Resilience technical evidence");
  assert((await body(page)).includes("Judge mode"), "Judge mode label missing");
  await clickButton(page, "View proof");
  const judgeOff = await page.evaluateHandle(() => [...document.querySelectorAll('[role="menuitem"]')]
    .find((item) => item.textContent?.includes("Judge proof mode on")));
  assert(judgeOff.asElement(), "Judge mode disable item missing");
  await judgeOff.asElement().focus();
  await page.keyboard.press("Enter");
  await settle(250);
  assert(await page.evaluate((labels) => [...document.querySelectorAll("details")]
    .filter((node) => labels.includes(node.querySelector("summary")?.textContent?.trim() ?? ""))
    .every((node) => !node.open), ["Source evidence", "Action evidence", "Technical evidence"]), "Resilience technical evidence remained open after Judge mode disabled");

  stage = "project-purity";
  await clickLink(page, "/projects");
  assert((await body(page)).includes("Your first delivery plan starts with proof"), "resilience changed Project state");

  await clickLink(page, "/initiatives");
  await clickLink(page, "/initiatives/BASIC_WORKSHOP/proof");
  const isolationReset = page.waitForResponse((response) => response.request().method() === "GET" && new URL(response.url()).pathname === "/api/demo");
  await clickButton(page, "Reset proof");
  assert((await isolationReset).status() === 200, "pending-Clinic isolation reset failed");
  await waitContent(page, "Awaiting compile");
  await clickLink(page, "/initiatives");
  const clinicCard = await page.evaluateHandle(() => [...document.querySelectorAll("button.initiative-card")]
    .find((button) => button.textContent?.includes("Multilingual Digital Help Clinic")));
  const clinicButton = clinicCard.asElement();
  assert(clinicButton, "Clinic initiative card missing");
  await clinicButton.focus();
  await page.keyboard.press("Enter");
  await settle(150);
  assert(await clinicButton.evaluate((button) => button.getAttribute("aria-current") === "true"), "Clinic initiative card did not become selected");
  assert(await page.$eval('a.primary-link', (link) => link.getAttribute("href") === "/initiatives/MULTILINGUAL_CLINIC/proof"), "selected proof link did not target Clinic");
  await clickLink(page, "/initiatives/MULTILINGUAL_CLINIC/proof");
  await waitContent(page, "Initiative proof");
  stage = "clinic-pending";
  await action(page, "COMPILE COMMUNITY", "/api/analyse");
  await action(page, "ASSEMBLE NOW", "/api/analyse");
  await action(page, "WHY BLOCKED", "/api/explain");
  await unlockAction(page);
  await action(page, "APPLY CATALYST", "/api/transition");
  assert((await body(page)).includes("Updated community awaiting verification"), "pending successor state missing");
  await clickLink(page, "/resilience");
  text = await body(page);
  assert(text.includes("Verification is required"), "pending transition did not block Resilience");
  assert(!await page.$('button:not([disabled])') || !text.includes("Run stress test"), "pending transition exposed a runnable stress control");
  await capture(page, "supplemental-pending-resilience-block-1440");

  await clickLink(page, "/initiatives/MULTILINGUAL_CLINIC/proof");
  const reset = page.waitForResponse((response) => response.request().method() === "GET" && new URL(response.url()).pathname === "/api/demo");
  await clickButton(page, "Reset proof");
  assert((await reset).status() === 200, "supplemental reset failed");
  await waitContent(page, "Awaiting compile");

  stage = "invalid-route-battery";
  const analyseBefore = requestCounts.get("POST /api/analyse") ?? 0;
  const invalidRoutes = [
    "/initiatives/UNKNOWN/proof",
    "/initiatives/basic_workshop/proof",
    "/initiatives/%252Fetc%252Fpasswd/proof",
    `/initiatives/${"A".repeat(512)}/proof`,
  ];
  for (const route of invalidRoutes) {
    await page.goto(`${BASE}${route}`, { waitUntil: "networkidle0" });
    await waitContent(page, "Initiative not found");
    assert((await body(page)).includes("No analysis was run for a fallback initiative"), `${route} fallback warning missing`);
  }
  assert((requestCounts.get("POST /api/analyse") ?? 0) === analyseBefore, "malformed proof route triggered fallback analysis");

  const viewports = [
    { width: 320, height: 568 },
    { width: 375, height: 667 },
    { width: 390, height: 844 },
    { width: 768, height: 1024 },
    { width: 1024, height: 768 },
    { width: 1280, height: 720 },
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
  ];
  const routes = ["/", "/community", "/initiatives", "/projects", "/projects/proof", "/resilience", "/settings", "/login", "/signup", "/communities"];
  stage = "responsive-route-matrix";
  for (const viewport of viewports) {
    for (const route of routes) await routeAudit(page, route, viewport);
  }

  stage = "appearance-zoom-matrix";
  await page.setViewport({ width: 320, height: 568, deviceScaleFactor: 1 });
  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle0" });
  const choose = async (name, labelText) => {
    const handle = await page.evaluateHandle(({ group, text: target }) => [...document.querySelectorAll("label")]
      .find((label) => label.textContent?.includes(target) && label.querySelector(`input[name="${group}"]`)), { group: name, text: labelText });
    const label = handle.asElement();
    assert(label, `appearance option ${labelText} missing`);
    const input = await label.$("input");
    await input.focus();
    await page.keyboard.press("Space");
    await settle(150);
  };
  await choose("settings-theme", "Dark theme");
  await choose("settings-contrast", "High contrast");
  await choose("settings-motion", "Reduce non-essential motion");
  assert(await page.evaluate(() => document.documentElement.dataset.theme === "dark" && document.documentElement.dataset.motion === "reduced"), "dark/reduced settings missing");
  assert(await page.$eval("main", (node) => node.classList.contains("contrast-high")), "high contrast missing");
  await capture(page, "supplemental-settings-dark-high-reduced-320");
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  const cdp = await page.createCDPSession();
  await cdp.send("Emulation.setPageScaleFactor", { pageScaleFactor: 4 });
  zoomEvidence = await page.evaluate(() => ({
    requestedScale: 4,
    measuredScale: window.visualViewport?.scale ?? 1,
    layoutWidth: window.innerWidth,
    visualViewportWidth: window.visualViewport?.width ?? window.innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
  }));
  assert(zoomEvidence.measuredScale >= 2.9 && zoomEvidence.measuredScale <= 3.1, `Chrome maximum zoom probe did not clamp to measured 3x: ${JSON.stringify(zoomEvidence)}`);
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), "maximum available 300% zoom introduced document overflow");
  await capture(page, "supplemental-settings-300pct-environment-cap-1440");
  await cdp.send("Emulation.setPageScaleFactor", { pageScaleFactor: 1 });
  await choose("settings-theme", "Use device setting");
  await choose("settings-contrast", "Standard contrast");
  await choose("settings-motion", "Follow device preference");

  const expectedHttp = httpErrors.filter((entry) => entry.status === 401 && new URL(entry.url).pathname === "/api/auth/session");
  const unexpectedHttp = httpErrors.filter((entry) => !expectedHttp.includes(entry));
  const expectedConsole = consoleEntries.filter((entry) => entry.type === "error" && entry.text.includes("401"));
  const unexpectedConsole = consoleEntries.filter((entry) => entry.type === "error" && !expectedConsole.includes(entry));
  const speculative = failedRequests.filter((entry) => entry.method === "GET" && entry.reason === "net::ERR_ABORTED" && new URL(entry.url).searchParams.has("_rsc"));
  const unexpectedFailed = failedRequests.filter((entry) => !speculative.includes(entry));
  assert(pageErrors.length === 0, `page errors observed: ${JSON.stringify(pageErrors)}`);
  assert(unexpectedHttp.length === 0, `unexpected HTTP errors: ${JSON.stringify(unexpectedHttp)}`);
  assert(unexpectedConsole.length === 0, `unexpected console errors: ${JSON.stringify(unexpectedConsole)}`);
  assert(unexpectedFailed.length === 0, `unexpected failed requests: ${JSON.stringify(unexpectedFailed)}`);

  console.log(JSON.stringify({
    status: "PASS_SUPPLEMENTAL_RESILIENCE_ACCESSIBILITY",
    head: HEAD,
    routeAuditCount: routeMatrix.length,
    routeMatrix,
    zoomEvidence: { ...zoomEvidence, classification: "400% NOT VERIFIED — Chrome 151 headless/CDP clamps requested 4x to measured 3x" },
    visualEvidence,
    consoleEntries,
    pageErrors,
    failedRequests,
    httpErrors,
    adjudication: {
      expectedGuestSession401: expectedHttp.length,
      expected401ConsoleEntries: expectedConsole.length,
      speculativeRscCancellations: speculative.length,
      unexpectedHttp: unexpectedHttp.length,
      unexpectedConsole: unexpectedConsole.length,
      unexpectedFailedRequests: unexpectedFailed.length,
    },
    requestCounts: Object.fromEntries([...requestCounts.entries()].sort()),
  }, null, 2));
} catch (error) {
  console.error(JSON.stringify({
    status: "HOLD_DIAGNOSTIC",
    stage,
    pageClosed: page.isClosed(),
    url: page.isClosed() ? null : page.url(),
    error: error instanceof Error ? error.message : String(error),
  }));
  throw error;
} finally {
  if (!page.isClosed()) await context.close().catch(() => undefined);
  browser.disconnect();
}
