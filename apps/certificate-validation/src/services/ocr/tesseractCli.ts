import { env } from "../../config/env.js";
import { runProcess } from "../../utils/process.js";

/** Run Tesseract and return stdout text. */
export async function runTesseractStdout(
  imagePath: string,
  lang: string,
  psm?: string,
): Promise<string> {
  const args = [imagePath, "stdout", "-l", lang];
  if (psm?.trim()) {
    args.push("--psm", psm.trim());
  }
  const { stdout } = await runProcess(env.TESSERACT_BIN, args);
  return stdout.trim();
}
