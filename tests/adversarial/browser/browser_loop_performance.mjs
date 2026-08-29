import { BASE, BROWSER_URL, puppeteer } from "./browser_support.mjs";
const HEAD = "453c84fc9c05495b1d21b91f505d8179019f296c";
const ITERATIONS = 25;

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function settle(ms = 120) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function text(page) {
  return page.evaluate(() => document.body?.innerText ?? "");
}

async function clickButton(page, label) {
  const handle = await page.evaluateHandle((needle) => [...document.querySelectorAll("button")]
    .find((button) => button.offsetParent !== null && button.textContent?.includes(needle)), label);
  const button = handle.asElement();
  assert(button, `button ${label} missing`);
  try {
    assert(!await button.evaluate((node) => node.disabled), `button ${label} disabled`);
    await button.click();
  } finally {
    await handle.dispose();
  }
}

async function postAction(page, label, path) {
  const response = page.waitForResponse((item) => item.request().method() === "POST" && new URL(item.url()).pathname === path);
  await clickButton(page, label);
  const result = await response;
  assert(result.status() === 200, `${path} returned ${result.status()}`);
  await settle();
}

async function reset(page) {
  const response = page.waitForResponse((item) => item.request().method() === "GET" && new URL(item.url()).pathname === "/api/demo");
  await clickButton(page, "Reset proof");
  assert((await response).status() === 200, "reset fixture failed");
  await settle();
  assert((await text(page)).includes("Awaiting compile"), "reset did not restore clean proof state");
}

async function metrics(page) {
  const cdp = await page.createCDPSession();
  await cdp.send("HeapProfiler.collectGarbage");
  await cdp.send("Performance.enable");
  const result = await cdp.send("Performance.getMetrics");
  const values = Object.fromEntries(result.metrics.map((item) => [item.name, item.value]));
  return {
    jsHeapUsedBytes: values.JSHeapUsedSize,
    domNodes: values.Nodes,
    documents: values.Documents,
    jsEventListeners: values.JSEventListeners,
    liveDomElements: await page.evaluate(() => document.getElementsByTagName("*").length),
  };
}

const browser = await puppeteer.connect({ browserURL: BROWSER_URL });
const context = await browser.createBrowserContext();
const page = await context.newPage();
const requestCounts = new Map();
const consoleErrors = [];
const pageErrors = [];
const failedRequests = [];

page.on("request", (request) => {
  const key = `${request.method()} ${new URL(request.url()).pathname}`;
  requestCounts.set(key, (requestCounts.get(key) ?? 0) + 1);
});
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => pageErrors.push(error.message));
page.on("requestfailed", (request) => failedRequests.push({ method: request.method(), url: request.url(), reason: request.failure()?.errorText }));

try {
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await page.goto(`${BASE}/initiatives/BASIC_WORKSHOP/proof`, { waitUntil: "networkidle0" });
  const before = await metrics(page);
  const durationsMs = [];

  for (let iteration = 1; iteration <= ITERATIONS; iteration += 1) {
    const started = performance.now();
    await postAction(page, "COMPILE COMMUNITY", "/api/analyse");
    await postAction(page, "ASSEMBLE NOW", "/api/analyse");
    const pageText = await text(page);
    assert(pageText.includes("Basic Workshop analysis returned OPTIMAL"), `iteration ${iteration} proof mismatch`);
    assert(await page.$$eval(".project-region", (nodes) => nodes.length === 1), `iteration ${iteration} did not expose exactly one Project form`);
    await reset(page);
    durationsMs.push(performance.now() - started);
  }

  await settle(1000);
  const after = await metrics(page);
  const sorted = [...durationsMs].sort((left, right) => left - right);
  const expectedAnalyse = ITERATIONS * 2;
  const observedAnalyse = requestCounts.get("POST /api/analyse") ?? 0;
  const observedDemo = requestCounts.get("GET /api/demo") ?? 0;
  const speculativeRsc = failedRequests.filter((entry) => entry.method === "GET" && entry.reason === "net::ERR_ABORTED" && new URL(entry.url).searchParams.has("_rsc"));
  const unexpectedFailed = failedRequests.filter((entry) => !speculativeRsc.includes(entry));
  const expected401Console = consoleErrors.filter((entry) => entry.includes("401"));
  const unexpectedConsole = consoleErrors.filter((entry) => !expected401Console.includes(entry));

  assert(observedAnalyse === expectedAnalyse, `expected ${expectedAnalyse} analyse calls, observed ${observedAnalyse}`);
  assert(observedDemo === ITERATIONS + 1, `expected ${ITERATIONS + 1} demo calls including initial load, observed ${observedDemo}`);
  assert(after.domNodes <= before.domNodes + 25, `DOM nodes grew unexpectedly: ${JSON.stringify({ before, after })}`);
  assert(after.liveDomElements <= before.liveDomElements + 5, `live DOM elements grew unexpectedly: ${before.liveDomElements} -> ${after.liveDomElements}`);
  assert(after.documents <= before.documents + 2, `documents grew unexpectedly: ${before.documents} -> ${after.documents}`);
  assert(after.jsEventListeners <= before.jsEventListeners + 25, `event listeners grew unexpectedly: ${before.jsEventListeners} -> ${after.jsEventListeners}`);
  assert(pageErrors.length === 0, `page errors: ${JSON.stringify(pageErrors)}`);
  assert(unexpectedFailed.length === 0, `failed requests: ${JSON.stringify(unexpectedFailed)}`);
  assert(unexpectedConsole.length === 0, `console errors: ${JSON.stringify(unexpectedConsole)}`);

  console.log(JSON.stringify({
    status: "PASS_BROWSER_WORKFLOW_LOOP",
    head: HEAD,
    iterations: ITERATIONS,
    timingsMs: {
      p50: sorted[Math.floor(sorted.length * 0.5)],
      p95: sorted[Math.floor(sorted.length * 0.95)],
      worst: sorted.at(-1),
    },
    before,
    after,
    deltas: {
      jsHeapUsedBytes: after.jsHeapUsedBytes - before.jsHeapUsedBytes,
      domNodes: after.domNodes - before.domNodes,
      documents: after.documents - before.documents,
      jsEventListeners: after.jsEventListeners - before.jsEventListeners,
    },
    requestCounts: Object.fromEntries([...requestCounts.entries()].sort()),
    networkAdjudication: {
      expectedGuestSession401Console: expected401Console.length,
      speculativeRscCancellations: speculativeRsc.length,
      unexpectedConsole: unexpectedConsole.length,
      unexpectedFailed: unexpectedFailed.length,
      pageErrors: pageErrors.length,
    },
  }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ status: "HOLD_DIAGNOSTIC", error: error instanceof Error ? error.message : String(error) }));
  throw error;
} finally {
  await context.close().catch(() => undefined);
  browser.disconnect();
}
