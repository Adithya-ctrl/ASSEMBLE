import { BASE, BROWSER_URL, EVIDENCE, puppeteer } from "./browser_support.mjs";

const HEAD = "453c84fc9c05495b1d21b91f505d8179019f296c";

const observations = [];
const consoleEntries = [];
const pageErrors = [];
const failedRequests = [];
const httpErrors = [];
let stage = "connect";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function settle(ms = 250) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function text(page) {
  return page.evaluate(() => document.body?.innerText ?? "");
}

async function waitText(page, marker, timeout = 30_000) {
  const deadline = Date.now() + timeout;
  while (!(await text(page)).includes(marker) && Date.now() < deadline) await settle(50);
  assert((await text(page)).includes(marker), `missing visible text ${marker}`);
}

async function waitPath(page, expected, timeout = 30_000) {
  const deadline = Date.now() + timeout;
  while (new URL(page.url()).pathname !== expected && Date.now() < deadline) await settle(50);
  assert(new URL(page.url()).pathname === expected, `expected ${expected}, observed ${page.url()}`);
}

async function clickButton(page, label) {
  const handle = await page.evaluateHandle((needle) => [...document.querySelectorAll("button")]
    .find((node) => node.offsetParent !== null && node.textContent?.includes(needle)), label);
  const button = handle.asElement();
  assert(button, `visible button ${label} missing`);
  assert(!await button.evaluate((node) => node.disabled || node.getAttribute("aria-disabled") === "true"), `${label} disabled`);
  await button.focus();
  await page.keyboard.press("Enter");
}

async function clickLink(page, href) {
  const handle = await page.evaluateHandle((target) => [...document.querySelectorAll("a")]
    .find((node) => node.offsetParent !== null && node.getAttribute("href") === target), href);
  const link = handle.asElement();
  assert(link, `visible link ${href} missing`);
  await link.focus();
  await page.keyboard.press("Enter");
  await waitPath(page, href);
  await settle();
}

async function action(page, label, path, expectedStatus = 200) {
  const pending = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === path);
  await clickButton(page, label);
  const response = await pending;
  assert(response.status() === expectedStatus, `${path} returned ${response.status()}`);
  await settle(350);
  return response;
}

function monitor(page, label) {
  page.on("console", (message) => consoleEntries.push({ label, type: message.type(), text: message.text(), url: page.url() }));
  page.on("pageerror", (error) => pageErrors.push({ label, message: error.message, url: page.url() }));
  page.on("requestfailed", (request) => failedRequests.push({ label, method: request.method(), url: request.url(), reason: request.failure()?.errorText }));
  page.on("response", (response) => {
    if (response.status() >= 400) httpErrors.push({ label, status: response.status(), method: response.request().method(), url: response.url() });
  });
}

async function routeTruth(page, expectedPath, marker) {
  await waitPath(page, expectedPath);
  await waitText(page, marker);
  const result = await page.evaluate(() => ({
    path: location.pathname,
    mainCount: document.querySelectorAll("main").length,
    h1: document.querySelector("h1")?.textContent?.trim() ?? "",
    overflow: document.documentElement.scrollWidth - innerWidth,
  }));
  assert(result.mainCount === 1 && result.h1 && result.overflow <= 1, `route truth failed: ${JSON.stringify(result)}`);
  return result;
}

const browser = await puppeteer.connect({ browserURL: BROWSER_URL });
const contexts = [];

try {
  stage = "history-and-preferences";
  const historyContext = await browser.createBrowserContext();
  contexts.push(historyContext);
  const history = await historyContext.newPage();
  monitor(history, "history");
  await history.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  const chain = [
    ["/", "Build what your community is ready for."],
    ["/community", "See what the community can bring"],
    ["/initiatives", "Choose what to build together"],
    ["/initiatives/BASIC_WORKSHOP/proof", "Initiative proof"],
    ["/projects", "Turn a verified initiative into a practical delivery plan"],
    ["/resilience", "Pressure-test the proof"],
    ["/settings", "Settings"],
    ["/communities", "Collaboration spaces"],
  ];
  for (const [path, marker] of chain) {
    await history.goto(`${BASE}${path}`, { waitUntil: "networkidle0" });
    observations.push({ kind: "route", ...(await routeTruth(history, path, marker)) });
  }
  for (let index = chain.length - 2; index >= 0; index -= 1) {
    await history.goBack({ waitUntil: "networkidle0" });
    observations.push({ kind: "back", ...(await routeTruth(history, chain[index][0], chain[index][1])) });
  }
  for (let index = 1; index < chain.length; index += 1) {
    await history.goForward({ waitUntil: "networkidle0" });
    observations.push({ kind: "forward", ...(await routeTruth(history, chain[index][0], chain[index][1])) });
  }
  await history.goto(`${BASE}/preferences`, { waitUntil: "networkidle0" });
  await waitPath(history, "/settings");
  await waitText(history, "Only these four appearance preferences");
  observations.push({ kind: "preferences-redirect", path: new URL(history.url()).pathname });

  stage = "two-tab-planning-isolation";
  const tabContext = await browser.createBrowserContext();
  contexts.push(tabContext);
  const tabA = await tabContext.newPage();
  const tabB = await tabContext.newPage();
  monitor(tabA, "tab-a");
  monitor(tabB, "tab-b");
  await Promise.all([
    tabA.goto(`${BASE}/initiatives/BASIC_WORKSHOP/proof`, { waitUntil: "networkidle0" }),
    tabB.goto(`${BASE}/initiatives/BASIC_WORKSHOP/proof`, { waitUntil: "networkidle0" }),
  ]);
  await action(tabA, "COMPILE COMMUNITY", "/api/analyse");
  await action(tabA, "ASSEMBLE NOW", "/api/analyse");
  assert((await text(tabA)).includes("Basic Workshop analysis returned OPTIMAL"), "tab A proof missing");
  assert((await text(tabB)).includes("Awaiting compile"), "tab B was contaminated by tab A planning state");
  observations.push({ kind: "two-tab-planning", tabA: "OPTIMAL", tabB: "Awaiting compile" });

  stage = "stale-analyse-discard";
  const staleContext = await browser.createBrowserContext();
  contexts.push(staleContext);
  const stale = await staleContext.newPage();
  monitor(stale, "stale");
  await stale.setRequestInterception(true);
  let pausedAnalyse = null;
  let releaseAnalyse;
  const analysePaused = new Promise((resolve) => { releaseAnalyse = resolve; });
  stale.on("request", (request) => {
    if (!pausedAnalyse && request.method() === "POST" && new URL(request.url()).pathname === "/api/analyse") {
      pausedAnalyse = request;
      releaseAnalyse();
      return;
    }
    void request.continue().catch(() => undefined);
  });
  await stale.goto(`${BASE}/initiatives/BASIC_WORKSHOP/proof`, { waitUntil: "networkidle0" });
  await clickButton(stale, "COMPILE COMMUNITY");
  await analysePaused;
  await stale.goto(`${BASE}/initiatives/MULTILINGUAL_CLINIC/proof`, { waitUntil: "domcontentloaded" });
  await waitText(stale, "Initiative proof");
  await pausedAnalyse.continue().catch(() => undefined);
  await settle(800);
  const staleText = await text(stale);
  assert(staleText.includes("Multilingual Digital Help Clinic"), "source switch did not bind Clinic");
  assert(!staleText.includes("Basic Workshop analysis returned OPTIMAL"), "late Basic result repainted Clinic");
  observations.push({ kind: "stale-analyse", outcome: "late source response discarded" });

  stage = "mounted-malformed-response";
  const malformedContext = await browser.createBrowserContext();
  contexts.push(malformedContext);
  const malformed = await malformedContext.newPage();
  monitor(malformed, "malformed");
  await malformed.setRequestInterception(true);
  malformed.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === "/api/analyse") {
      void request.respond({ status: 200, contentType: "application/json", body: "{}" });
      return;
    }
    void request.continue().catch(() => undefined);
  });
  await malformed.goto(`${BASE}/initiatives/BASIC_WORKSHOP/proof`, { waitUntil: "networkidle0" });
  await clickButton(malformed, "COMPILE COMMUNITY");
  await waitText(malformed, "REQUEST_FAILED");
  const malformedText = await text(malformed);
  assert(malformedText.includes("unexpected response"), "malformed response lacked stable fail-closed message");
  assert(!malformedText.includes("OPTIMAL") && !await malformed.$(".project-region"), "malformed response rendered plausible evidence");
  observations.push({ kind: "malformed-response", outcome: "REQUEST_FAILED, evidence withheld" });

  stage = "image-failure-and-semantics";
  const imageContext = await browser.createBrowserContext();
  contexts.push(imageContext);
  const imagePage = await imageContext.newPage();
  monitor(imagePage, "images");
  await imagePage.setViewport({ width: 320, height: 568, deviceScaleFactor: 2 });
  await imagePage.setRequestInterception(true);
  const intentionallyBlockedImages = [];
  imagePage.on("request", (request) => {
    if (request.resourceType() === "image") {
      intentionallyBlockedImages.push(request.url());
      void request.abort("failed");
      return;
    }
    void request.continue().catch(() => undefined);
  });
  for (const [path, marker] of [["/", "Build what your community is ready for."], ["/signup", "Create your account"], ["/resilience", "Pressure-test the proof"]]) {
    await imagePage.goto(`${BASE}${path}`, { waitUntil: "networkidle0" });
    await waitText(imagePage, marker);
    const imageAudit = await imagePage.evaluate(() => ({
      path: location.pathname,
      images: [...document.images].map((node) => ({ alt: node.alt, complete: node.complete, naturalWidth: node.naturalWidth })),
      buttons: [...document.querySelectorAll("button")].filter((node) => node.offsetParent !== null).length,
      links: [...document.querySelectorAll("a")].filter((node) => node.offsetParent !== null).length,
      overflow: document.documentElement.scrollWidth - innerWidth,
      main: document.querySelectorAll("main").length,
    }));
    assert(imageAudit.main === 1 && imageAudit.overflow <= 1, `image failure broke layout: ${JSON.stringify(imageAudit)}`);
    assert(imageAudit.buttons + imageAudit.links > 0, `image failure removed navigation/actions on ${path}`);
    assert(imageAudit.images.every((item) => item.alt.trim().length > 0), `informative image missing alt on ${path}`);
    observations.push({ kind: "image-failure", ...imageAudit });
  }
  assert(intentionallyBlockedImages.length >= 3, "image failure harness did not block expected assets");
  await imagePage.screenshot({ path: `${EVIDENCE}/remaining-images-blocked-resilience-320@2x.png`, fullPage: true });

  stage = "offline-online-recovery";
  const offlineContext = await browser.createBrowserContext();
  contexts.push(offlineContext);
  const offline = await offlineContext.newPage();
  monitor(offline, "offline");
  await offline.goto(`${BASE}/initiatives/BASIC_WORKSHOP/proof`, { waitUntil: "networkidle0" });
  await offline.setOfflineMode(true);
  await clickButton(offline, "COMPILE COMMUNITY");
  await waitText(offline, "SERVICE_UNAVAILABLE");
  let offlineText = await text(offline);
  assert(offlineText.includes("The ASSEMBLE service could not be reached") && offlineText.includes("Compile again"), "offline state lacked stable error/retry");
  assert(!offlineText.includes("OPTIMAL"), "offline request rendered optimistic proof");
  await offline.setOfflineMode(false);
  await action(offline, "Compile again", "/api/analyse");
  await action(offline, "ASSEMBLE NOW", "/api/analyse");
  offlineText = await text(offline);
  assert(offlineText.includes("Basic Workshop analysis returned OPTIMAL"), "online retry did not recover");
  observations.push({ kind: "offline-online", outcome: "stable failure then successful retry" });

  stage = "hostile-text-rendering";
  const hostileContext = await browser.createBrowserContext();
  contexts.push(hostileContext);
  const hostile = await hostileContext.newPage();
  monitor(hostile, "hostile");
  await hostile.goto(`${BASE}/signup`, { waitUntil: "networkidle0" });
  const nonce = Date.now().toString(36);
  const username = `gauntlet-${nonce}`.slice(0, 48);
  const password = `G!${crypto.randomUUID()}a7`;
  await hostile.type("#auth-username", username);
  await hostile.type("#auth-email", `${username}@example.test`);
  await hostile.type("#auth-display-name", "Security render account");
  await hostile.type("#auth-password", password);
  const signup = hostile.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === "/api/auth/signup");
  await clickButton(hostile, "Create account");
  assert((await signup).status() === 201, "hostile-text setup signup failed");
  await waitPath(hostile, "/communities");
  const createTab = await hostile.evaluateHandle(() => [...document.querySelectorAll('button[role="tab"]')]
    .find((node) => node.textContent?.includes("Create")));
  assert(createTab.asElement(), "Create collaboration tab missing");
  await createTab.asElement().focus();
  await hostile.keyboard.press("Enter");
  await settle();
  const hostileName = `<img src=x onerror=window.__gauntlet_xss=1> ' OR 1=1 --`;
  await hostile.type("#collab-community-name", hostileName);
  await hostile.type("#collab-community-slug", `security-${nonce}`.slice(0, 60));
  const createResponse = hostile.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === "/api/communities");
  await clickButton(hostile, "Create space");
  assert((await createResponse).status() === 201, "hostile text community creation failed");
  await waitText(hostile, hostileName);
  const hostileAudit = await hostile.evaluate((literal) => ({
    scriptExecuted: window.__gauntlet_xss === 1,
    literalVisible: document.body.innerText.includes(literal),
    injectedImageCount: [...document.images].filter((node) => node.getAttribute("src") === "x").length,
    overflow: document.documentElement.scrollWidth - innerWidth,
  }), hostileName);
  assert(!hostileAudit.scriptExecuted && hostileAudit.literalVisible && hostileAudit.injectedImageCount === 0 && hostileAudit.overflow <= 1, `hostile text was not safely rendered: ${JSON.stringify(hostileAudit)}`);
  observations.push({ kind: "hostile-text", ...hostileAudit });

  stage = "accessibility-tree";
  const ax = await hostile.createCDPSession();
  const tree = await ax.send("Accessibility.getFullAXTree");
  const roles = tree.nodes.map((node) => node.role?.value).filter(Boolean);
  const names = tree.nodes.map((node) => node.name?.value).filter(Boolean);
  assert(roles.includes("main") && roles.includes("heading") && names.includes("Collaboration spaces"), "accessibility tree missing primary semantics");
  observations.push({ kind: "accessibility-tree", nodeCount: tree.nodes.length, main: roles.filter((role) => role === "main").length, headings: roles.filter((role) => role === "heading").length });

  const expectedHttp = httpErrors.filter((entry) => entry.status === 401 && new URL(entry.url).pathname === "/api/auth/session");
  const expectedConsole = consoleEntries.filter((entry) => entry.type === "error" && (
    entry.text.includes("401")
    || entry.text.includes("ERR_INTERNET_DISCONNECTED")
    || (entry.label === "images" && entry.text.includes("net::ERR_FAILED"))
  ));
  const intentionalImageFailures = failedRequests.filter((entry) => entry.label === "images" && entry.reason === "net::ERR_FAILED");
  const offlineFailures = failedRequests.filter((entry) => entry.label === "offline" && entry.reason === "net::ERR_INTERNET_DISCONNECTED");
  const speculativeRsc = failedRequests.filter((entry) => entry.method === "GET" && entry.reason === "net::ERR_ABORTED" && new URL(entry.url).searchParams.has("_rsc"));
  const staleAbort = failedRequests.filter((entry) => entry.label === "stale" && entry.reason === "net::ERR_ABORTED");
  const expectedFailed = new Set([...intentionalImageFailures, ...offlineFailures, ...speculativeRsc, ...staleAbort]);
  const unexpectedFailed = failedRequests.filter((entry) => !expectedFailed.has(entry));
  const unexpectedHttp = httpErrors.filter((entry) => !expectedHttp.includes(entry));
  const unexpectedConsole = consoleEntries.filter((entry) => entry.type === "error" && !expectedConsole.includes(entry));
  assert(pageErrors.length === 0, `page errors: ${JSON.stringify(pageErrors)}`);
  assert(unexpectedHttp.length === 0, `unexpected HTTP errors: ${JSON.stringify(unexpectedHttp)}`);
  assert(unexpectedConsole.length === 0, `unexpected console errors: ${JSON.stringify(unexpectedConsole)}`);
  assert(unexpectedFailed.length === 0, `unexpected request failures: ${JSON.stringify(unexpectedFailed)}`);

  console.log(JSON.stringify({
    status: "PASS_REMAINING_BROWSER_SECURITY_VISUAL",
    head: HEAD,
    observations,
    networkAdjudication: {
      expectedGuestSession401: expectedHttp.length,
      expected401OrOfflineConsole: expectedConsole.length,
      intentionallyBlockedImages: intentionalImageFailures.length,
      expectedOfflineFailures: offlineFailures.length,
      speculativeRscCancellations: speculativeRsc.length,
      staleNavigationAborts: staleAbort.length,
      unexpectedHttp: unexpectedHttp.length,
      unexpectedConsole: unexpectedConsole.length,
      unexpectedFailed: unexpectedFailed.length,
      pageErrors: pageErrors.length,
    },
  }, null, 2));
} catch (error) {
  console.error(JSON.stringify({
    status: "HOLD_DIAGNOSTIC",
    stage,
    error: error instanceof Error ? error.message : String(error),
  }));
  throw error;
} finally {
  for (const context of contexts.reverse()) await context.close().catch(() => undefined);
  browser.disconnect();
}
