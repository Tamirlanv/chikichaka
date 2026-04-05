import { spawnSync } from "node:child_process";

import { env } from "../../config/env.js";

/**
 * Fail fast if Tesseract is missing or required language packs are not installed.
 * Called once at process startup in production-like environments.
 */
export function runOcrPreflight(): void {
  const bin = env.TESSERACT_BIN;
  const version = spawnSync(bin, ["--version"], { encoding: "utf8" });
  if (version.status !== 0) {
    // eslint-disable-next-line no-console
    console.error(
      "certificate-validation OCR preflight: tesseract --version failed.\n",
      version.stderr || version.error || ""
    );
    process.exit(1);
  }

  const langs = spawnSync(bin, ["--list-langs"], { encoding: "utf8" });
  if (langs.status !== 0) {
    // eslint-disable-next-line no-console
    console.error(
      "certificate-validation OCR preflight: tesseract --list-langs failed.\n",
      langs.stderr || langs.error || ""
    );
    process.exit(1);
  }

  const lines = (langs.stdout || "")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  const available = new Set(lines.filter((l) => /^[a-z]{3}$/i.test(l)));

  const required = ["eng", "rus", "kaz"] as const;
  const missing = required.filter((code) => !available.has(code));
  if (missing.length > 0) {
    // eslint-disable-next-line no-console
    console.error(
      `certificate-validation OCR preflight: missing tessdata language(s): ${missing.join(", ")}. ` +
        `Installed: ${[...available].sort().join(", ") || "(none)"}. ` +
        "Install tesseract-ocr-eng, tesseract-ocr-rus, tesseract-ocr-kaz (see docs/ocr-setup.md)."
    );
    process.exit(1);
  }
}
