import { BASE, BROWSER_URL, EVIDENCE, puppeteer } from "./browser_support.mjs";
const HEAD = "453c84fc9c05495b1d21b91f505d8179019f296c";
const routes = ["/", "/community", "/initiatives", "/initiatives/BASIC_WORKSHOP/proof", "/projects", "/resilience", "/settings", "/communities"];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const browser = await puppeteer.connect({ browserURL: BROWSER_URL });
const context = await browser.createBrowserContext();
const page = await context.newPage();
const pageErrors = [];
const consoleErrors = [];
const failedRequests = [];
const rows = [];
page.on("pageerror", (error) => pageErrors.push(error.message));
page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
page.on("requestfailed", (request) => failedRequests.push({ method: request.method(), url: request.url(), reason: request.failure()?.errorText }));

try {
  await page.setViewport({ width: 2560, height: 1440, deviceScaleFactor: 1 });
  for (const route of routes) {
    await page.goto(`${BASE}${route}`, { waitUntil: "networkidle0" });
    const row = await page.evaluate(() => {
      const main = document.querySelector("main");
      const h1 = document.querySelector("h1");
      const content = main?.querySelector("section") ?? main;
      const rect = content?.getBoundingClientRect();
      return {
        path: location.pathname,
        width: innerWidth,
        height: innerHeight,
        mainCount: document.querySelectorAll("main").length,
        h1: h1?.textContent?.trim() ?? "",
        overflow: document.documentElement.scrollWidth - innerWidth,
        contentWidth: rect?.width ?? 0,
        contentLeft: rect?.left ?? 0,
        contentRight: rect ? innerWidth - rect.right : 0,
      };
    });
    assert(row.width === 2560 && row.height === 1440, `viewport mismatch: ${JSON.stringify(row)}`);
    assert(row.mainCount === 1 && row.h1 && row.overflow <= 1, `route structure failed: ${JSON.stringify(row)}`);
    assert(row.contentWidth >= 600 && row.contentWidth <= 2300, `content measure became implausible: ${JSON.stringify(row)}`);
    rows.push(row);
  }
  await page.goto(`${BASE}/resilience`, { waitUntil: "networkidle0" });
  assert((await page.evaluate(() => document.querySelector("h1")?.textContent ?? "")).includes("Pressure-test"), "ultrawide screenshot route was not Resilience");
  await page.screenshot({ path: `${EVIDENCE}/ultrawide-resilience-2560.png`, fullPage: true });
  const expected401 = consoleErrors.filter((entry) => entry.includes("401"));
  const unexpectedConsole = consoleErrors.filter((entry) => !expected401.includes(entry));
  const speculativeRsc = failedRequests.filter((entry) => entry.method === "GET" && entry.reason === "net::ERR_ABORTED" && new URL(entry.url).searchParams.has("_rsc"));
  const unexpectedFailed = failedRequests.filter((entry) => !speculativeRsc.includes(entry));
  assert(pageErrors.length === 0, `page errors: ${JSON.stringify(pageErrors)}`);
  assert(unexpectedConsole.length === 0, `unexpected console errors: ${JSON.stringify(unexpectedConsole)}`);
  assert(unexpectedFailed.length === 0, `unexpected failed requests: ${JSON.stringify(unexpectedFailed)}`);
  console.log(JSON.stringify({ status: "PASS_ULTRAWIDE_2560", head: HEAD, rows, network: { expected401: expected401.length, speculativeRsc: speculativeRsc.length, unexpectedConsole: 0, unexpectedFailed: 0, pageErrors: 0 } }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ status: "HOLD_DIAGNOSTIC", error: error instanceof Error ? error.message : String(error) }));
  throw error;
} finally {
  await context.close().catch(() => undefined);
  browser.disconnect();
}
