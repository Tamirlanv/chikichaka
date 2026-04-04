import { describe, expect, it } from "vitest";

import { validatePlausibleScore } from "../extraction/plausibleScore.js";

describe("validatePlausibleScore", () => {
  it("accepts valid IELTS band", () => {
    expect(validatePlausibleScore("ielts", 6.5).ok).toBe(true);
    expect(validatePlausibleScore("ielts", 6.7).ok).toBe(true);
  });

  it("rejects IELTS outside 4–9", () => {
    expect(validatePlausibleScore("ielts", 3.5).ok).toBe(false);
    expect(validatePlausibleScore("ielts", 10).ok).toBe(false);
  });

  it("accepts integer TOEFL in range", () => {
    expect(validatePlausibleScore("toefl", 82).ok).toBe(true);
  });

  it("rejects non-integer or out of range TOEFL", () => {
    expect(validatePlausibleScore("toefl", 82.5).ok).toBe(false);
    expect(validatePlausibleScore("toefl", 121).ok).toBe(false);
  });

  it("accepts ENT aggregate in range", () => {
    expect(validatePlausibleScore("ent", 98).ok).toBe(true);
  });
});
