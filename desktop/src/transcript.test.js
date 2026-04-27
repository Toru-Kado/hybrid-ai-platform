import { describe, expect, it } from "vitest";

import { buildTranscriptContent, buildTranscriptFilename } from "./transcript";

describe("transcript helpers", () => {
  const session = {
    session_id: 12,
    title: "Jerusalem Planning",
    created_at: "2026-04-25T12:00:00.000Z",
    updated_at: "2026-04-25T12:05:00.000Z",
  };
  const messages = [
    {
      role: "user",
      content: "Summarize the roadmap.",
      created_at: "2026-04-25T12:01:00.000Z",
    },
    {
      role: "assistant",
      content: "## Roadmap\n\n- Finish the UI\n- Improve the data layer",
      created_at: "2026-04-25T12:02:00.000Z",
    },
  ];

  it("builds a filesystem-safe transcript filename", () => {
    expect(buildTranscriptFilename(session, "markdown")).toBe("jerusalem-planning.md");
    expect(buildTranscriptFilename(session, "json")).toBe("jerusalem-planning.json");
  });

  it("preserves assistant markdown in exported markdown transcripts", () => {
    const exported = buildTranscriptContent(session, messages, "markdown");

    expect(exported).toContain("# Jerusalem Planning");
    expect(exported).toContain("## Assistant");
    expect(exported).toContain("## Roadmap");
    expect(exported).toContain("- Finish the UI");
  });

  it("exports structured json transcripts", () => {
    const exported = buildTranscriptContent(session, messages, "json");
    const parsed = JSON.parse(exported);

    expect(parsed.session.title).toBe("Jerusalem Planning");
    expect(parsed.messages).toHaveLength(2);
    expect(parsed.messages[1].content).toContain("## Roadmap");
  });
});
