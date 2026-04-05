import dotenv from "dotenv";
import { z } from "zod";

dotenv.config({ path: ".env" });

const EnvSchema = z.object({
  CERT_VALIDATION_PORT: z.coerce.number().default(4400),
  DATABASE_URL: z.string().default("postgresql://postgres:postgres@localhost:5432/invision"),
  OPENAI_API_KEY: z.string().optional(),
  /** Default `-l` for Tesseract when request does not override `ocrLang`. */
  OCR_LANG: z.string().default("eng"),
  /** Executable name or absolute path (e.g. `/opt/homebrew/bin/tesseract`). */
  TESSERACT_BIN: z.string().default("tesseract"),
  /** If set, passed to Tesseract as `--psm` (e.g. `4` for single column, `6` uniform block). */
  OCR_PSM: z.string().optional(),
  MAX_FILE_SIZE_BYTES: z.coerce.number().default(8 * 1024 * 1024),
  TOEFL_THRESHOLD: z.coerce.number().default(60)
});

export const env = EnvSchema.parse(process.env);
