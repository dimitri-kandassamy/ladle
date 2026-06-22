// Render build/cookbook.html -> build/cookbook.pdf with Paged.js + Chrome.
//
// Paged.js paginates the print HTML; the actual rasterising/printing is done by
// a headless browser. We point pagedjs-cli at the already-installed Google Chrome
// (PUPPETEER_EXECUTABLE_PATH) so CI/local don't need to download a second browser.

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const input = join(root, "build", "cookbook.html");
const output = join(root, "build", "cookbook.pdf");

if (!existsSync(input)) {
  console.error("Missing build/cookbook.html — run `python3 tools/build_html.py` first.");
  process.exit(1);
}

// Locate a Chrome/Chromium binary.
function findChrome() {
  if (process.env.PUPPETEER_EXECUTABLE_PATH) return process.env.PUPPETEER_EXECUTABLE_PATH;
  const candidates = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ];
  return candidates.find((p) => existsSync(p));
}

const chrome = findChrome();
const env = { ...process.env };
if (chrome) {
  env.PUPPETEER_EXECUTABLE_PATH = chrome;
  console.log(`Using browser: ${chrome}`);
} else {
  console.log("No system Chrome found; relying on puppeteer's bundled browser.");
}

const bin = join(root, "node_modules", ".bin", "pagedjs-cli");
const args = [
  input,
  "-o", output,
  "--browserArgs", "--no-sandbox,--font-render-hinting=none,--allow-file-access-from-files",
];

const res = spawnSync(bin, args, { stdio: "inherit", env });
if (res.status !== 0) {
  console.error(`pagedjs-cli exited with status ${res.status}`);
  process.exit(res.status ?? 1);
}
console.log(`Wrote ${output}`);
