import { describe, expect, it } from "vitest";

import { parseEntScore, parseIeltsOverall, parseNisScore, parseToeflScore } from "../extraction/scoreParsers.js";

describe("score parsers", () => {
  it("parses ielts overall band score", () => {
    expect(parseIeltsOverall("Overall Band Score: 6.5")).toBe(6.5);
    expect(parseIeltsOverall("OVERALL BAND SCORE 7.0")).toBe(7.0);
  });

  it("prefers overall over stray digits", () => {
    const text = `Listening 8.0 Reading 7.5
    Overall Band Score 6.5`;
    expect(parseIeltsOverall(text)).toBe(6.5);
  });

  it("parses toefl total score lines only", () => {
    expect(parseToeflScore("Total Score 101")).toBe(101);
    expect(parseToeflScore("My Total Score: 82")).toBe(82);
  });

  it("does not pick random digits after word TOEFL when total line missing", () => {
    expect(parseToeflScore("TOEFL iBT Reading 25 Listening 24")).toBeNull();
  });

  it("parses ent aggregate", () => {
    expect(parseEntScore("ЕНТ итоговый балл: 114")).toBe(114);
    expect(parseEntScore("итоговый балл 98")).toBe(98);
  });

  it("parses nis-style aggregate", () => {
    const t = "Nazarbayev Intellectual Schools итоговый балл 95";
    expect(parseNisScore(t)).toBe(95);
  });
});
