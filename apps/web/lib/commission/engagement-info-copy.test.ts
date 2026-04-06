import { describe, expect, it } from "vitest";

import { ENGAGEMENT_INFO_MODAL_DESCRIPTION, ENGAGEMENT_INFO_MODAL_TITLE } from "./engagement-info-copy";

describe("engagement info copy", () => {
  it("keeps human-readable title and description", () => {
    expect(ENGAGEMENT_INFO_MODAL_TITLE).toBe("Что показывает вкладка «Вовлеченность»");
    expect(ENGAGEMENT_INFO_MODAL_DESCRIPTION).toContain(
      "насколько последовательно и осознанно кандидат проходил этапы подачи",
    );
  });

  it("does not include technical terms", () => {
    const lower = ENGAGEMENT_INFO_MODAL_DESCRIPTION.toLowerCase();
    expect(lower).not.toContain("pipeline");
    expect(lower).not.toContain("unit");
    expect(lower).not.toContain("telemetry");
    expect(lower).not.toContain("event logs");
  });
});
