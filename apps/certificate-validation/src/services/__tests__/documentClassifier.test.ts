import { describe, expect, it } from "vitest";

import { classifyDocumentType } from "../classification/documentClassifier.js";

describe("classifyDocumentType", () => {
  it("detects IELTS", () => {
    expect(classifyDocumentType("IELTS Test Report Form Overall Band Score 6.5")).toBe("ielts");
  });

  it("detects TOEFL", () => {
    expect(classifyDocumentType("ETS TOEFL iBT total score 98")).toBe("toefl");
  });

  it("detects ENT context", () => {
    expect(classifyDocumentType("Единое национальное тестирование итоговый балл 100")).toBe("ent");
  });

  it("detects noisy ENT certificate markers from OCR text", () => {
    expect(classifyDocumentType("Серия ST СЕРТИФИКАТ 2089899 КТ - 98")).toBe("ent");
  });

  it("detects NIS", () => {
    expect(
      classifyDocumentType("Nazarbayev Intellectual Schools certificate Grade 12 итоговый балл 88")
    ).toBe("nis_12");
  });
});
