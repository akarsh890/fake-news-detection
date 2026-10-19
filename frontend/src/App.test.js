import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const APP_JSX_PATH = path.join(__dirname, "App.jsx");
const APP_CSS_PATH = path.join(__dirname, "App.css");
const INDEX_CSS_PATH = path.join(__dirname, "index.css");

test("App.jsx contains required accessibility, validation, and API integration contracts", () => {
  const source = fs.readFileSync(APP_JSX_PATH, "utf8");

  // Core API endpoints
  assert.match(source, /\/health/, "Must check backend /api/health endpoint");
  assert.match(source, /\/predict\?meta=1/, "Must call /api/predict?meta=1");

  // Input validation and limits
  assert.match(source, /MAX_CHARS = 20000/, "Must enforce 20,000 character limit");
  assert.match(
    source,
    /Please enter a news article or headline before analyzing\./,
    "Must validate empty/whitespace input"
  );

  // Separate handling of HTTP 400 errors vs network failures
  assert.match(
    source,
    /if \(!response\.ok\)/,
    "Must inspect response.ok for backend error payloads"
  );
  assert.match(
    source,
    /Could not connect to the backend\./,
    "Must provide clear network error message when backend is unreachable"
  );

  // Accessible controls & result presentation
  assert.match(source, /aria-live="polite"/, "Must include aria-live region for results");
  assert.match(source, /role="alert"/, "Must include role='alert' for validation/network errors");
  assert.match(source, /role="progressbar"/, "Must include accessible confidence progressbar");
  assert.match(source, /disabled=\{loading\}/, "Must disable submission while loading");
});

test("Stylesheets define light/dark theme variables, responsive breakpoints, and reduced-motion rules", () => {
  const indexCss = fs.readFileSync(INDEX_CSS_PATH, "utf8");
  const appCss = fs.readFileSync(APP_CSS_PATH, "utf8");

  assert.match(indexCss, /\[data-theme="dark"\]/, "Must support dark theme token overrides");
  assert.match(
    indexCss,
    /@media \(prefers-reduced-motion: reduce\)/,
    "Must respect prefers-reduced-motion"
  );
  assert.match(appCss, /@media \(max-width: 920px\)/, "Must include tablet responsive breakpoint");
  assert.match(appCss, /@media \(max-width: 640px\)/, "Must include mobile responsive breakpoint");
});

