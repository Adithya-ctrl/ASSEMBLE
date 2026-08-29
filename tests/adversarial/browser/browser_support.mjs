import { fileURLToPath } from "node:url";

const modulePath = process.env.ASSEMBLE_PUPPETEER_MODULE;

if (!modulePath) {
  throw new Error("Set ASSEMBLE_PUPPETEER_MODULE to the local chrome-devtools-mcp third_party/index.js module.");
}

export const { puppeteer } = await import(modulePath);
export const BASE = process.env.ASSEMBLE_FRONTEND_URL ?? "http://127.0.0.1:3134";
export const BACKEND_BASE = process.env.ASSEMBLE_BACKEND_URL ?? "http://127.0.0.1:8018";
export const BROWSER_URL = process.env.ASSEMBLE_BROWSER_URL ?? "http://127.0.0.1:9337";
export const EVIDENCE = process.env.ASSEMBLE_BROWSER_EVIDENCE_DIR
  ?? fileURLToPath(new URL("../evidence/browser/final-453c84f", import.meta.url));
