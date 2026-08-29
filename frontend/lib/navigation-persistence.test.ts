import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const rootLayout = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
const productLayout = readFileSync(new URL("../app/(product)/layout.tsx", import.meta.url), "utf8");
const projectDetail = readFileSync(new URL("../components/project/ProjectDetailView.tsx", import.meta.url), "utf8");
const accountMenu = readFileSync(new URL("../components/identity/AccountMenu.tsx", import.meta.url), "utf8");
const appShell = readFileSync(new URL("../components/shell/AppShell.tsx", import.meta.url), "utf8");

test("one root provider owns workflow state across product route transitions", () => {
  assert.match(rootLayout, /import \{ AssemblyProvider \} from "\.\.\/lib\/workflow-context";/);
  assert.match(rootLayout, /<AssemblyProvider>\{children\}<\/AssemblyProvider>/);
  assert.doesNotMatch(productLayout, /AssemblyProvider/);
  assert.match(productLayout, /<AppShell>\{children\}<\/AppShell>/);
});

test("guest account navigation exposes authentication and appearance without adding another primary-nav destination", () => {
  assert.match(accountMenu, /href="\/login"/);
  assert.match(accountMenu, /href="\/signup"/);
  assert.match(accountMenu, /href="\/settings"/);
  assert.match(accountMenu, /Settings and appearance/);
  assert.match(appShell, /<AccountMenu \/>/);
  assert.doesNotMatch(appShell, /href: "\/settings"/);
});

test("Project proof uses client routing without browser-storage proof persistence", () => {
  assert.match(projectDetail, /import Link from "next\/link";/);
  assert.match(projectDetail, /<Link className="secondary-link" href="\/projects\/proof">/);
  const layoutsAndProject = `${rootLayout}\n${productLayout}\n${projectDetail}`;
  assert.doesNotMatch(layoutsAndProject, /localStorage|sessionStorage/);
});
