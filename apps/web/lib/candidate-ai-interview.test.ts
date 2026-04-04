import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { postCandidateAiInterviewAnswers } from "./candidate-ai-interview";

describe("postCandidateAiInterviewAnswers", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ saved: 1 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends JSON with Content-Type application/json (FastAPI body model)", async () => {
    const payload = {
      answers: [{ questionId: "q1", text: "Ответ" }],
    };
    await postCandidateAiInterviewAnswers(payload);

    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain("/api/v1/candidates/me/application/ai-interview/answers");
    expect(init?.method).toBe("POST");
    const headers = new Headers(init?.headers as HeadersInit);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init?.body).toBe(JSON.stringify(payload));
  });
});
