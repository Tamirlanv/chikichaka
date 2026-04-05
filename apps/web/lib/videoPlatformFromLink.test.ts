import { describe, expect, it } from "vitest";

import { detectVideoPlatformFromUrl } from "./videoPlatformFromLink";

describe("detectVideoPlatformFromUrl", () => {
  it("detects Google Meet", () => {
    expect(detectVideoPlatformFromUrl("https://meet.google.com/xxx-yyyy-zzz")).toBe("Google Meet");
  });

  it("detects Zoom", () => {
    expect(detectVideoPlatformFromUrl("https://us02web.zoom.us/j/123456789")).toBe("Zoom");
    expect(detectVideoPlatformFromUrl("https://zoom.us/j/123")).toBe("Zoom");
  });

  it("detects Discord", () => {
    expect(detectVideoPlatformFromUrl("https://discord.gg/abc123")).toBe("Discord");
    expect(detectVideoPlatformFromUrl("https://discord.com/channels/1/2/3")).toBe("Discord");
  });

  it("returns null for unknown hosts", () => {
    expect(detectVideoPlatformFromUrl("https://example.com/meet")).toBeNull();
    expect(detectVideoPlatformFromUrl("")).toBeNull();
  });
});
