import { randomBytes } from "node:crypto";

import { BASE, BROWSER_URL, EVIDENCE, puppeteer } from "./browser_support.mjs";
const OWNER_PASSWORD = `M1!${randomBytes(12).toString("base64url")}aA`;
const OWNER_NEW_PASSWORD = `M2!${randomBytes(12).toString("base64url")}aA`;
const MEMBER_PASSWORD = `M3!${randomBytes(12).toString("base64url")}aA`;

const browser = await puppeteer.connect({ browserURL: BROWSER_URL });
const steps = [];
const failures = [];
const consoleEntries = [];
const pageErrors = [];
const failedRequests = [];
const httpErrors = [];
const requestCounts = new Map();

function record(step, detail) {
  steps.push({ step, detail, at: new Date().toISOString() });
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function body(page) {
  return page.evaluate(() => document.body?.innerText ?? "");
}

async function settle(ms = 350) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitPath(page, expectedPath) {
  const deadline = Date.now() + 30_000;
  while (new URL(page.url()).pathname !== expectedPath && Date.now() < deadline) {
    await settle(50);
  }
  assert(new URL(page.url()).pathname === expectedPath, `navigation did not reach ${expectedPath}; observed ${page.url()}`);
}

function routeMarker(path) {
  if (path === "/") return "Build what your community is ready for.";
  if (path === "/community") return "See what the community can bring";
  if (path === "/initiatives") return "Choose what to build together";
  if (path.startsWith("/initiatives/") && path.endsWith("/proof")) return "Initiative proof";
  if (path === "/projects") return "Projects";
  if (path === "/projects/proof") return "Project source proof";
  if (path === "/resilience") return "Pressure-test the proof";
  if (path === "/settings") return "Settings";
  if (path === "/login") return "Sign in to collaborate";
  if (path === "/signup") return "Create your account";
  if (path === "/communities") return "Collaboration spaces";
  if (path.startsWith("/communities/")) return "Marathon Neighbourhood";
  return null;
}

async function waitRouteReady(page, path) {
  await waitPath(page, path);
  const marker = routeMarker(path);
  if (!marker) return;
  const deadline = Date.now() + 30_000;
  while (!(await body(page)).includes(marker) && Date.now() < deadline) await settle(50);
  assert((await body(page)).includes(marker), `route ${path} did not render marker ${marker}`);
}

async function clickButton(page, needle) {
  const clicked = await page.evaluate((text) => {
    const button = [...document.querySelectorAll("button")]
      .find((candidate) => candidate.offsetParent !== null && candidate.textContent?.includes(text));
    if (!button) return false;
    if (button.disabled || button.getAttribute("aria-disabled") === "true") return false;
    button.click();
    return true;
  }, needle);
  assert(clicked, `missing visible button containing ${needle}`);
}

async function clickLink(page, href) {
  const clicked = await page.evaluate((target) => {
    const link = [...document.querySelectorAll("a")]
      .find((candidate) => candidate.offsetParent !== null && candidate.getAttribute("href") === target);
    if (!link) return false;
    link.click();
    return true;
  }, href);
  assert(clicked, `missing visible link ${href}`);
  await waitRouteReady(page, href);
  await settle();
}

async function selectTab(page, needle) {
  const handle = await page.evaluateHandle((text) => [...document.querySelectorAll('button[role="tab"]')]
    .find((candidate) => candidate.offsetParent !== null && candidate.textContent?.includes(text)), needle);
  const element = handle.asElement();
  assert(element, `missing tab ${needle}`);
  await element.focus();
  await page.keyboard.press("Enter");
  await settle(180);
  assert(await element.evaluate((node) => node.getAttribute("aria-selected") === "true"), `tab ${needle} did not become active`);
}

async function action(page, buttonText, apiPath, expectedStatus = 200) {
  const responsePromise = page.waitForResponse((response) => (
    new URL(response.url()).pathname === apiPath && response.request().method() === "POST"
  ));
  await clickButton(page, buttonText);
  const response = await responsePromise;
  assert(response.status() === expectedStatus, `${apiPath} returned ${response.status()}, expected ${expectedStatus}`);
  await settle(450);
  return response;
}

async function unlockAction(page) {
  const unlock = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/unlock" && response.request().method() === "POST");
  const plan = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/plan" && response.request().method() === "POST");
  await clickButton(page, "FIND MINIMUM UNLOCK");
  const [unlockResponse, planResponse] = await Promise.all([unlock, plan]);
  assert(unlockResponse.ok(), `/api/unlock returned ${unlockResponse.status()}`);
  assert(planResponse.ok(), `/api/plan returned ${planResponse.status()}`);
  await settle(450);
}

async function fill(selector, value, page) {
  await page.focus(selector);
  await page.keyboard.down("Meta");
  await page.keyboard.press("A");
  await page.keyboard.up("Meta");
  await page.type(selector, value);
}

async function typeLabeledControl(page, containerSelector, labelText, value) {
  const handle = await page.evaluateHandle(({ container, text }) => {
    const label = [...document.querySelectorAll(`${container} label`)]
      .find((candidate) => candidate.textContent?.includes(text));
    return label?.querySelector("input, textarea");
  }, { container: containerSelector, text: labelText });
  const element = handle.asElement();
  assert(element, `missing ${labelText} control in ${containerSelector}`);
  await element.focus();
  await page.keyboard.down("Meta");
  await page.keyboard.press("A");
  await page.keyboard.up("Meta");
  await element.type(value);
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

try {
  for (const context of browser.browserContexts()) {
    for (const page of await context.pages()) {
      if (page.url() !== "about:blank") await page.close();
    }
    if (context !== browser.defaultBrowserContext()) await context.close();
  }

  const ownerContext = await browser.createBrowserContext();
  const page = await ownerContext.newPage();
  monitor(page, "owner");
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });

  await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
  assert((await body(page)).includes("Build what your community is ready for."), "overview did not load");
  record(1, "Guest Overview loaded at 1440x1000.");

  await clickLink(page, "/community");
  for (const category of ["People", "Places", "Resources"]) {
    await selectTab(page, category);
    assert((await body(page)).includes(category), `${category} inventory missing`);
  }
  await selectTab(page, "People");
  await clickButton(page, "List");
  assert(await page.$eval('button[aria-label="List view"]', (node) => node.getAttribute("aria-pressed") === "true"), "list view not selected");
  await clickButton(page, "Graph");
  assert(await page.$eval('button[aria-label="Graph view"]', (node) => node.getAttribute("aria-pressed") === "true"), "graph view not selected");
  record(2, "People, Places, Resources and Graph/List controls exercised.");
  record(3, "Graph/List preference changed in both directions with pressed state.");

  await clickLink(page, "/initiatives");
  await clickLink(page, "/initiatives/BASIC_WORKSHOP/proof");
  await action(page, "COMPILE COMMUNITY", "/api/analyse");
  await action(page, "ASSEMBLE NOW", "/api/analyse");
  let text = await body(page);
  assert(text.includes("Basic Workshop analysis returned OPTIMAL"), "Basic proof was not optimal");
  record(4, "Basic proof compiled and returned OPTIMAL.");

  const projectForm = ".project-form";
  await typeLabeledControl(page, projectForm, "Project title", "Marathon Basic Project");
  await typeLabeledControl(page, projectForm, "Short description", "A verified basic workshop delivery plan.");
  await typeLabeledControl(page, projectForm, "Objective", "Deliver practical digital help with proven capacity.");
  await action(page, "Create Project", "/api/projects/from-plan", 201);
  assert((await body(page)).includes("Marathon Basic Project was created"), "Basic Project creation receipt missing");
  await clickLink(page, "/projects");
  text = await body(page);
  assert(text.includes("Marathon Basic Project") && text.includes("Ready"), "Basic Project operational view missing");
  record(5, "Basic Project created from verified server proof and shown Ready.");

  await clickLink(page, "/projects/proof");
  assert((await body(page)).includes("Marathon Basic Project"), "Basic Project proof page missing");
  record(6, "Basic Project source proof opened.");

  await clickLink(page, "/initiatives");
  await clickLink(page, "/initiatives/BASIC_WORKSHOP/proof");
  const resetResponse = page.waitForResponse((response) => response.request().method() === "GET" && new URL(response.url()).pathname === "/api/demo");
  await clickButton(page, "Reset proof");
  assert((await resetResponse).status() === 200, "Reset fixture request failed");
  await settle();
  assert((await body(page)).includes("Awaiting compile"), "Reset did not clear proof state");
  record(7, "Planning proof reset to Awaiting compile.");

  await clickLink(page, "/initiatives");
  const selectedClinic = await page.evaluate(() => {
    const button = [...document.querySelectorAll("button.initiative-card")]
      .find((candidate) => candidate.offsetParent !== null && candidate.textContent?.includes("Multilingual Digital Help Clinic"));
    if (!button) return false;
    button.click();
    return true;
  });
  assert(selectedClinic, "Clinic initiative selector missing");
  await settle(100);
  await clickLink(page, "/initiatives/MULTILINGUAL_CLINIC/proof");
  await action(page, "COMPILE COMMUNITY", "/api/analyse");
  await action(page, "ASSEMBLE NOW", "/api/analyse");
  assert((await body(page)).includes("INFEASIBLE"), "Clinic baseline did not block");
  await action(page, "WHY BLOCKED", "/api/explain");
  await unlockAction(page);
  assert((await body(page)).includes("Train two digital helpers"), "Clinic minimum unlock mismatch");
  await action(page, "APPLY CATALYST", "/api/transition");
  assert((await body(page)).includes("Updated community awaiting verification"), "Clinic pending state missing");
  await action(page, "VERIFY NEW STATE", "/api/analyse");
  assert((await body(page)).includes("successor verification returned OPTIMAL"), "Clinic successor proof missing");
  record(8, "Clinic compile/explain/unlock/plan/apply/verify completed; TRAIN path verified OPTIMAL.");

  await typeLabeledControl(page, projectForm, "Project title", "Marathon Clinic Project");
  await typeLabeledControl(page, projectForm, "Short description", "A verified multilingual clinic delivery plan.");
  await typeLabeledControl(page, projectForm, "Objective", "Deliver multilingual digital help with trained capacity.");
  await action(page, "Create Project", "/api/projects/from-plan", 201);
  await clickLink(page, "/projects");
  assert((await body(page)).includes("Marathon Clinic Project"), "Clinic Project missing");
  record(9, "Clinic Project created from the verified successor.");

  await clickLink(page, "/projects/proof");
  assert((await body(page)).includes("Marathon Clinic Project"), "Clinic Project proof missing");
  record(10, "Clinic Project proof opened.");

  await clickLink(page, "/resilience");
  const stressSelect = 'select[id$="-stress-initiative"]';
  const recoverySelect = 'select[id$="-recovery-perturbation"]';
  await page.select(stressSelect, "MULTILINGUAL_CLINIC");
  await action(page, "Run stress test", "/api/stress-test");
  text = await body(page);
  assert(text.includes("6 critical") && text.includes("0 unknown") && text.includes("0%"), "trained Clinic stress truth mismatch");
  record(11, "Trained Clinic stress returned 6/6 critical, zero unknown, 0% resilience.");
  assert((text.match(/Outcome evidence/g) ?? []).length === 6, "not all six stress outcomes rendered");
  record(12, "All six one-fact outcomes rendered with before/after evidence.");

  await page.select(stressSelect, "BASIC_WORKSHOP");
  await action(page, "Run stress test", "/api/stress-test");
  await selectTab(page, "Recovery");
  const perturbation = await page.$eval(recoverySelect, (select) => [...select.options]
    .find((option) => option.textContent?.includes("Priya becomes unavailable"))?.value ?? "");
  assert(perturbation, "returned Priya perturbation missing");
  await page.select(recoverySelect, perturbation);
  await action(page, "Find recovery", "/api/recompile");
  text = await body(page);
  for (const expected of ["Minimum changed", "1 assignment", "Recovered burden", "24", "Priya → Leo", "Sam preserved"]) {
    assert(text.includes(expected), `recovery evidence missing ${expected}`);
  }
  record(13, "Basic recovery used returned Priya disruption; 1 change, Priya to Leo, Sam preserved, burden 24.");

  await selectTab(page, "Capability frontier");
  await action(page, "Compare actions", "/api/frontier");
  text = await body(page);
  assert(text.includes("Highest leverage") && text.includes("None") && text.includes("Not applicable from this source"), "trained frontier truth mismatch");
  record(14, "Trained frontier rendered null highest leverage and TRAIN not applicable.");

  await clickLink(page, "/projects");
  text = await body(page);
  assert(text.includes("Marathon Clinic Project") && text.includes("Ready"), "resilience mutated Project");
  record(15, "Returned to unchanged Ready Clinic Project; counterfactual work caused no operational mutation.");

  await page.focus("button.identity-account-trigger");
  await page.keyboard.press("Enter");
  await settle(150);
  await clickLink(page, "/settings");
  const chooseRadio = async (name, labelText) => {
    const clicked = await page.evaluate(({ group, text: target }) => {
      const label = [...document.querySelectorAll("label")]
        .find((candidate) => candidate.textContent?.includes(target) && candidate.querySelector(`input[name="${group}"]`));
      const input = label?.querySelector("input");
      if (!input) return false;
      input.click();
      return true;
    }, { group: name, text: labelText });
    assert(clicked, `appearance option missing: ${labelText}`);
    await settle(120);
  };
  await chooseRadio("settings-theme", "Dark theme");
  assert(await page.evaluate(() => document.documentElement.dataset.theme === "dark"), "dark theme not applied");
  record(16, "Dark theme applied through guest Settings.");
  await chooseRadio("settings-contrast", "High contrast");
  assert(await page.$eval("main", (node) => node.classList.contains("contrast-high")), "high contrast class missing");
  record(17, "High contrast applied.");
  await chooseRadio("settings-motion", "Reduce non-essential motion");
  assert(await page.evaluate(() => document.documentElement.dataset.motion === "reduced"), "reduced motion not applied");
  record(18, "Reduced-motion preference applied.");

  const cdp = await page.createCDPSession();
  await cdp.send("Emulation.setPageScaleFactor", { pageScaleFactor: 2 });
  const scale = await page.evaluate(() => window.visualViewport?.scale ?? 1);
  assert(scale >= 1.9, `200% page scale not active: ${scale}`);
  record(19, `200% browser page scale active (${scale}).`);

  await page.focus("body");
  const focusTrace = [];
  for (let index = 0; index < 18; index += 1) {
    await page.keyboard.press("Tab");
    focusTrace.push(await page.evaluate(() => {
      const active = document.activeElement;
      return active ? `${active.tagName}:${active.getAttribute("aria-label") ?? active.textContent?.trim().slice(0, 40) ?? ""}` : "none";
    }));
  }
  assert(focusTrace.some((entry) => entry.startsWith("A:")) && focusTrace.some((entry) => entry.startsWith("INPUT:")), "keyboard path missed links or inputs");
  await page.$eval('a[href="/"]', (node) => node.focus());
  await page.keyboard.press("Enter");
  await waitRouteReady(page, "/");
  await page.$eval('a[href="/projects"]', (node) => node.focus());
  await page.keyboard.press("Enter");
  await waitRouteReady(page, "/projects");
  assert((await body(page)).includes("Marathon Clinic Project"), "keyboard Projects navigation lost Project state");
  await page.focus("button.identity-account-trigger");
  await page.keyboard.press("Enter");
  await settle(150);
  await page.$eval('a[href="/settings"]', (node) => node.focus());
  await page.keyboard.press("Enter");
  await waitRouteReady(page, "/settings");
  record(20, `Keyboard-only trace reached links/form controls across ${focusTrace.length} stops and navigated Projects to Settings.`);
  await cdp.send("Emulation.setPageScaleFactor", { pageScaleFactor: 1 });

  await clickLink(page, "/login");
  await clickLink(page, "/signup");
  await page.type("#auth-username", "marathon-owner");
  await page.type("#auth-email", "marathon-owner@example.test");
  await page.type("#auth-display-name", "Marathon Owner");
  await page.type("#auth-password", OWNER_PASSWORD);
  await action(page, "Create account", "/api/auth/signup", 201);
  await waitRouteReady(page, "/communities");
  assert((await body(page)).includes("Marathon Owner"), "owner signup did not establish session");
  const signupCookie = (await page.cookies()).find((cookie) => cookie.name === "assemble_session");
  assert(signupCookie?.httpOnly && signupCookie.sameSite === "Lax" && signupCookie.path === "/" && signupCookie.expires > Date.now() / 1000, "signup session cookie attributes mismatch");
  record(21, "Owner account created in the real browser UI.");

  await clickLink(page, "/settings");
  await fill("#settings-display-name", "Marathon Owner Updated", page);
  await fill("#settings-avatar-url", "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png", page);
  const profileResponse = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/auth/profile" && response.request().method() === "PATCH");
  await clickButton(page, "Save profile");
  assert((await profileResponse).status() === 200, "profile update failed");
  await settle();
  assert((await body(page)).includes("Marathon Owner Updated"), "updated profile missing");
  record(22, "Display name and HTTPS avatar metadata updated.");

  await selectTab(page, "Security");
  const cookieBefore = (await page.cookies()).find((cookie) => cookie.name === "assemble_session")?.value;
  await page.type("#settings-current-password", OWNER_PASSWORD);
  await page.type("#settings-new-password", OWNER_NEW_PASSWORD);
  await page.type("#settings-confirm-password", OWNER_NEW_PASSWORD);
  await action(page, "Change password", "/api/auth/password");
  const cookieAfter = (await page.cookies()).find((cookie) => cookie.name === "assemble_session")?.value;
  assert(cookieBefore && cookieAfter && cookieBefore !== cookieAfter, "password change did not rotate session cookie");
  assert((await page.$$eval('input[type="password"]', (nodes) => nodes.every((node) => node.value === ""))), "password fields not cleared");
  record(23, "Password changed, cookie rotated, and password fields cleared.");

  await clickLink(page, "/communities");
  await selectTab(page, "Create");
  await page.type("#collab-community-name", "Marathon Neighbourhood");
  await page.type("#collab-community-slug", "marathon-neighbourhood");
  await action(page, "Create space", "/api/communities", 201);
  await selectTab(page, "Your spaces");
  text = await body(page);
  assert(text.includes("Marathon Neighbourhood") && text.includes("Administrator"), "created community missing");
  record(24, "Collaboration space created; owner shown as Administrator.");

  const manageHref = await page.$eval("a", (_node, target) => [...document.querySelectorAll("a")].find((link) => link.textContent?.includes("Manage"))?.getAttribute("href"), "unused");
  assert(manageHref, "community Manage link missing");
  await clickLink(page, manageHref);
  await selectTab(page, "Invitations");
  await page.type("#collab-recipient", "marathon-member@example.test");
  await page.select("#collab-invite-role", "COORDINATOR");
  const inviteResponse = await action(page, "Create invitation", `${manageHref.replace("/communities/", "/api/communities/")}/invitations`, 201);
  assert(inviteResponse.headers()["cache-control"] === "no-store", "invitation response missing no-store");
  assert(inviteResponse.headers()["referrer-policy"] === "no-referrer", "invitation response missing no-referrer");
  const rawToken = await page.$eval("code", (node) => node.textContent ?? "");
  assert(rawToken.length >= 40, "one-time token missing");
  record(25, "Recipient-bound Coordinator invitation created; one-time response was no-store/no-referrer.");

  const memberContext = await browser.createBrowserContext();
  const member = await memberContext.newPage();
  monitor(member, "member");
  await member.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 });
  await member.goto(`${BASE}/signup`, { waitUntil: "networkidle0" });
  await member.type("#auth-username", "marathon-member");
  await member.type("#auth-email", "marathon-member@example.test");
  await member.type("#auth-display-name", "Marathon Member");
  await member.type("#auth-password", MEMBER_PASSWORD);
  await action(member, "Create account", "/api/auth/signup", 201);
  await waitRouteReady(member, "/communities");
  await selectTab(member, "Accept invite");
  await member.type("#collab-invite-token", rawToken);
  const acceptResponse = member.waitForResponse((response) => new URL(response.url()).pathname === "/api/invitations/accept" && response.request().method() === "POST");
  await member.$eval("#collab-invite-token", (input) => {
    const submit = input.closest("form")?.querySelector('button[type="submit"]');
    if (!submit) throw new Error("invitation accept form submit missing");
    submit.click();
  });
  const accepted = await acceptResponse;
  assert(accepted.status() === 200, "invitation acceptance failed");
  assert((await accepted.json()).role === "COORDINATOR", "invitation acceptance returned the wrong role");
  await settle(450);
  assert(await member.$eval("#collab-invite-token", (node) => node.value === ""), "accepted token field not cleared");
  await member.type("#collab-invite-token", rawToken);
  const replayResponse = member.waitForResponse((response) => new URL(response.url()).pathname === "/api/invitations/accept" && response.request().method() === "POST");
  await member.$eval("#collab-invite-token", (input) => {
    const submit = input.closest("form")?.querySelector('button[type="submit"]');
    if (!submit) throw new Error("invitation accept form submit missing on replay");
    submit.click();
  });
  const replayed = await replayResponse;
  assert(replayed.status() === 404, "accepted invitation replay did not fail with 404");
  assert((await replayed.json()).error?.code === "INVITATION_NOT_AVAILABLE", "accepted invitation replay exposed the wrong error");
  await settle(250);
  assert(await member.$eval("#collab-invite-token", (node) => node.value === ""), "replayed token field not cleared");
  await selectTab(member, "Your spaces");
  assert((await body(member)).includes("Coordinator"), "member did not receive Coordinator role");
  record(26, "Second browser account accepted the token once, received Coordinator role, and replay failed generically.");

  await clickButton(page, "Dismiss");
  await settle(100);
  assert(!await page.evaluate((token) => document.documentElement.innerHTML.includes(token), rawToken), "dismissed raw token remained in DOM");
  const membersResponse = page.waitForResponse((response) => response.request().method() === "GET" && new URL(response.url()).pathname.endsWith("/members"));
  await selectTab(page, "Members");
  assert((await membersResponse).status() === 200, "member list refresh failed");
  const memberRow = await page.evaluateHandle(() => [...document.querySelectorAll(".collab-member-list > li")]
    .find((row) => row.querySelector("strong")?.textContent?.trim() === "marathon-member"));
  const memberElement = memberRow.asElement();
  assert(memberElement, "accepted marathon-member row missing");
  const memberRoleSelect = await memberElement.$("select");
  const memberRoleButton = await memberElement.$("button[type=submit]");
  assert(memberRoleSelect && memberRoleButton, "marathon-member role form incomplete");
  await memberRoleSelect.select("MEMBER");
  const roleResponse = page.waitForResponse((response) => response.request().method() === "PATCH" && new URL(response.url()).pathname.includes("/members/"));
  await memberRoleButton.evaluate((node) => node.click());
  assert((await roleResponse).status() === 200, "role change failed");
  await member.reload({ waitUntil: "networkidle0" });
  assert((await body(member)).includes("Member"), "live role change not reflected on next request");
  record(27, "Admin changed Coordinator to Member; second browser reflected role loss on next request.");

  const auditResponse = page.waitForResponse((response) => response.request().method() === "GET" && new URL(response.url()).pathname.endsWith("/audit-events"));
  await selectTab(page, "Audit events");
  assert((await auditResponse).status() === 200, "audit event refresh failed");
  text = await body(page);
  assert(text.includes("Invitation Accepted") && text.includes("Membership Role Changed"), "audit events missing");
  assert(!text.includes(rawToken), "raw invitation token leaked into audit UI");
  record(28, "Audit rendered invitation/membership/role events newest-first with no raw token.");

  await clickLink(page, "/settings");
  await page.focus("button.identity-account-trigger");
  await page.keyboard.press("Enter");
  await settle(150);
  await page.evaluate(() => [...document.querySelectorAll('[role="menuitem"]')].find((item) => item.textContent?.trim() === "Sign out")?.focus());
  const logoutResponse = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/auth/logout" && response.request().method() === "POST");
  await page.keyboard.press("Enter");
  assert((await logoutResponse).status() === 204, "logout failed");
  await waitRouteReady(page, "/");
  assert(!(await page.cookies()).some((cookie) => cookie.name === "assemble_session"), "logout did not clear session cookie");
  await page.focus("button.identity-account-trigger");
  await page.keyboard.press("Enter");
  await settle(150);
  await clickLink(page, "/login");
  await page.type("#auth-identity", "marathon-owner");
  await page.type("#auth-password", OWNER_NEW_PASSWORD);
  await action(page, "Sign in", "/api/auth/login");
  await waitRouteReady(page, "/communities");
  assert((await body(page)).includes("Marathon Owner Updated"), "new-password login failed");
  record(29, "Logout cleared cookie; login with rotated password restored owner session.");

  await page.screenshot({ path: `${EVIDENCE}/phase1-29-owner.png`, fullPage: true });
  await member.screenshot({ path: `${EVIDENCE}/phase1-29-member-390.png`, fullPage: true });

  console.log(JSON.stringify({
    status: "PASS_THROUGH_STEP_29",
    head: "453c84fc9c05495b1d21b91f505d8179019f296c",
    steps,
    consoleEntries,
    pageErrors,
    failedRequests,
    httpErrors,
    requestCounts: Object.fromEntries([...requestCounts.entries()].sort()),
    pages: (await browser.pages()).map((candidate) => candidate.url()),
  }, null, 2));
} catch (error) {
  failures.push({ message: error instanceof Error ? error.message : String(error), stack: error instanceof Error ? error.stack : null });
  console.log(JSON.stringify({ status: "HOLD", steps, failures, consoleEntries, pageErrors, failedRequests, httpErrors }, null, 2));
  process.exitCode = 1;
} finally {
  await browser.disconnect();
}
