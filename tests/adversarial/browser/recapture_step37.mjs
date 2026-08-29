import { readFile } from "node:fs/promises";

import { BASE, BROWSER_URL, EVIDENCE, puppeteer } from "./browser_support.mjs";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function pngDimensions(buffer) {
  assert(buffer.subarray(1, 4).toString() === "PNG", "evidence file is not PNG");
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
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

  await owner.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
  await member.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 });
  const ownerViewport = await owner.evaluate(() => ({ width: window.innerWidth, height: window.innerHeight }));
  const memberViewport = await member.evaluate(() => ({ width: window.innerWidth, height: window.innerHeight }));
  assert(ownerViewport.width === 1440 && ownerViewport.height === 1000, `owner browser viewport mismatch: ${JSON.stringify(ownerViewport)}`);
  assert(memberViewport.width === 390 && memberViewport.height === 844, `member browser viewport mismatch: ${JSON.stringify(memberViewport)}`);

  const ownerPath = `${EVIDENCE}/step37-owner-settings-1440.png`;
  const memberPath = `${EVIDENCE}/step37-member-communities-390.png`;
  await owner.screenshot({ path: ownerPath, fullPage: true });
  await member.screenshot({ path: memberPath, fullPage: true });
  const ownerPng = pngDimensions(await readFile(ownerPath));
  const memberPng = pngDimensions(await readFile(memberPath));
  assert(ownerPng.width === 1440, `owner PNG width mismatch: ${ownerPng.width}`);
  assert(memberPng.width === 390, `member PNG width mismatch: ${memberPng.width}`);

  console.log(JSON.stringify({
    status: "PASS_STEP_37_RECAPTURE",
    sourceHead: "453c84fc9c05495b1d21b91f505d8179019f296c",
    ownerViewport,
    memberViewport,
    ownerPng,
    memberPng,
  }));
} finally {
  browser.disconnect();
}
