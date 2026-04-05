import { env } from "../../config/env.js";
import { runProcess } from "../../utils/process.js";
import { OcrResult } from "../types.js";
import type { OcrExtractOptions } from "./ocrProvider.js";
import { OcrProvider } from "./ocrProvider.js";

export class TesseractOcrProvider implements OcrProvider {
  async extractText(imagePath: string, options?: OcrExtractOptions): Promise<OcrResult> {
    const bin = env.TESSERACT_BIN;
    const lang = options?.ocrLang ?? env.OCR_LANG;
    const args = [imagePath, "stdout", "-l", lang];
    if (env.OCR_PSM?.trim()) {
      args.push("--psm", env.OCR_PSM.trim());
    }
    const { stdout } = await runProcess(bin, args);
    const text = stdout.trim();
    return {
      text,
      confidence: text ? 0.7 : null
    };
  }
}
