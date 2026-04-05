import { OcrResult } from "../types.js";

export type OcrExtractOptions = {
  /** Tesseract `-l` value, e.g. `eng` or `rus+kaz+eng`. */
  ocrLang?: string;
};

export interface OcrProvider {
  extractText(imagePath: string, options?: OcrExtractOptions): Promise<OcrResult>;
}
