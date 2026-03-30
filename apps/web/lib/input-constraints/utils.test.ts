import { describe, expect, it } from "vitest";
import {
  formatDate,
  formatIIN,
  formatPhone,
  isDateRangePotentiallyValid,
  keepOnlyDigits,
  normalizeKzPhoneRaw,
  sanitizeText,
  sanitizeLatinUsername,
} from "./utils";

describe("input-constraints/utils", () => {
  it("keeps only digits", () => {
    expect(keepOnlyDigits("+7(777)123-45-67")).toBe("77771234567");
  });

  it("formats phone from digits", () => {
    expect(formatPhone("77771234567")).toBe("+7 777 123 45 67");
  });

  it("normalizes phone with leading 8 to 7", () => {
    expect(normalizeKzPhoneRaw("87011234567")).toBe("77011234567");
    expect(formatPhone("+7(777)123-45-67")).toBe("+7 777 123 45 67");
  });

  it("removes letters from phone input", () => {
    expect(formatPhone("abc777123")).toBe("+7 771 23");
  });

  it("formats iin and limits to 12 digits", () => {
    expect(formatIIN("123456789012")).toBe("123456789012");
    expect(formatIIN("1234abcd56789012")).toBe("123456789012");
  });

  it("formats date with dots", () => {
    expect(formatDate("12052006")).toBe("12.05.2006");
    expect(formatDate("12a05b2006")).toBe("12.05.2006");
    expect(formatDate("120520061234")).toBe("12.05.2006");
    expect(formatDate("12")).toBe("12");
    expect(formatDate("1205")).toBe("12.05");
    expect(formatDate("1")).toBe("1");
    expect(formatDate("")).toBe("");
  });

  it("sanitizes text and trims to max length", () => {
    expect(sanitizeText("  hello   world\u200B ")).toBe("hello world");
    expect(sanitizeText("x".repeat(40))).toHaveLength(30);
  });

  it("sanitizes latin usernames", () => {
    expect(sanitizeLatinUsername("@user_name.12")).toBe("@user_name.12");
    expect(sanitizeLatinUsername("@юзер_name")).toBe("@_name");
    expect(sanitizeLatinUsername("тест123")).toBe("123");
  });

  it("checks date ranges softly", () => {
    expect(isDateRangePotentiallyValid("01012000")).toBe(true);
    expect(isDateRangePotentiallyValid("32132000")).toBe(false);
    expect(isDateRangePotentiallyValid("12")).toBe(true);
  });
});
