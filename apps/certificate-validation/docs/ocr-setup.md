# Tesseract OCR (certificate-validation)

The service runs the **system** `tesseract` binary (see `TESSERACT_BIN` in [`src/config/env.ts`](../src/config/env.ts)). There is no bundled OCR in npm dependencies.

## Install

### macOS (Homebrew)

```bash
brew install tesseract
brew install tesseract-lang   # optional: extra languages (rus, kaz, …)
```

Verify:

```bash
which tesseract
tesseract --list-langs
```

Ensure **`eng`** is present (IELTS). For Cyrillic ЕНТ scans, install **`rus`** and/or **`kaz`** and use e.g. `OCR_LANG=rus+kaz+eng` or per-fixture `ocrLang` in `apps/web/public/legal/expected.json`.

### Debian / Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus tesseract-ocr-kaz
```

### Custom binary path

If `tesseract` is not on `PATH`:

```bash
export TESSERACT_BIN=/opt/homebrew/bin/tesseract
```

## Legal fixtures (`npm run test:legal`)

- By default, tests **fail** if OCR is required and Tesseract is missing (so CI/local cannot get a false green run).
- To skip OCR-dependent cases (e.g. CI without apt packages): `LEGAL_SKIP_OCR_FIXTURES=1`.
- Optional env:
  - **`OCR_PSM`** — Tesseract page segmentation (e.g. `4` for single column; sometimes improves IELTS forms).
  - **`LEGAL_REQUIRE_SCORE`** — if set to `0`, the test still runs OCR and asserts **document type**, but does **not** fail when a numeric score cannot be parsed (common on low-resolution scans where table digits are not recognized). The JSON summary still reports `detectedScore: null` with a note. Use `1` or unset for strict score checks.

## `LEGAL_REQUIRE_SCORE` and real-world scans

Tesseract often **does not** read band scores in IELTS tables or composite scores on ЕНТ scans if the resolution or font is unfriendly. The pipeline still returns **`documentType`** from declaration + OCR merge and **`rawDetectedText`** for debugging. For strict score matching, prefer **higher-resolution** scans or adjust `OCR_PSM` / `ocrLang` in `expected.json`.

## Docker (reproducible run)

From the **repository root**:

```bash
docker build -f apps/certificate-validation/Dockerfile.legal -t cert-legal .
docker run --rm cert-legal
```

This copies `apps/certificate-validation` and `apps/web/public/legal` and sets `LEGAL_FIXTURES_DIR` so fixtures resolve correctly.

## Production image path

Deploy the HTTP service with **[`infra/docker/Dockerfile.certificate-validation`](../../../infra/docker/Dockerfile.certificate-validation)** (build context: repository root). That image installs **tesseract-ocr** + **eng/rus/kaz** tessdata, **ffmpeg**, and runs the compiled server (`node dist/server.js`). It is the same stack used by **`docker compose`** for the `certificate-validation` service.

`preprocessImage` uses **ffmpeg** for contrast/rotation. The legal integration test mocks preprocessing; the real server needs **ffmpeg** on the host for that path.

On startup the service runs an OCR **preflight** (`tesseract --version`, `tesseract --list-langs`) and exits if **eng**, **rus**, or **kaz** are missing.
