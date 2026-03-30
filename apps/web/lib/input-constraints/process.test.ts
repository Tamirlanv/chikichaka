import { describe, expect, it } from "vitest";
import { processInputValue, validateFormattedInput, validateRawInput } from "./process";

describe("input-constraints/process", () => {
  it("processes text with trim and max length", () => {
    const res = processInputValue("text", "  test   text  ");
    expect(res.formattedValue).toBe("test text");
    expect(res.rawValue).toBe("test text");
    expect(res.isPotentiallyValid).toBe(true);
  });

  it("processes phone with normalization and completion flag", () => {
    const res = processInputValue("phone", "+7(777)123-45-67");
    expect(res.rawValue).toBe("77771234567");
    expect(res.formattedValue).toBe("+7 777 123 45 67");
    expect(res.isComplete).toBe(true);
  });

  it("processes iin and truncates", () => {
    const res = processInputValue("iin", "1234abcd56789012");
    expect(res.rawValue).toBe("123456789012");
    expect(res.formattedValue).toBe("123456789012");
    expect(res.isComplete).toBe(true);
  });

  it("processes date and applies strictness on blur", () => {
    const valid = processInputValue("date", "12052006", { phase: "blur" });
    expect(valid.formattedValue).toBe("12.05.2006");
    expect(valid.rawValue).toBe("12052006");
    expect(valid.isComplete).toBe(true);
    expect(valid.isPotentiallyValid).toBe(true);

    const invalid = processInputValue("date", "32132006", { phase: "blur" });
    expect(invalid.formattedValue).toBe("32.13.2006");
    expect(invalid.isPotentiallyValid).toBe(false);
  });

  it("validates raw and formatted values", () => {
    expect(validateRawInput("iin", "123456789012")).toBe(true);
    expect(validateRawInput("iin", "1234567890123")).toBe(false);

    expect(validateFormattedInput("date", "12.05.2006")).toBe(true);
    expect(validateFormattedInput("date", "12.05.2006.1")).toBe(false);
    expect(validateFormattedInput("latin_username", "@valid_name.1")).toBe(true);
    expect(validateFormattedInput("latin_username", "@юзер")).toBe(false);
  });

  it("processes latin username by stripping non-latin chars", () => {
    const res = processInputValue("latin_username", "@тест.user_12");
    expect(res.formattedValue).toBe("@.user_12");
    expect(res.isPotentiallyValid).toBe(true);
  });
});
