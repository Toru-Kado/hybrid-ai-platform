const FORMAT_CONFIG = {
  markdown: {
    extension: "md",
    mimeType: "text/markdown;charset=utf-8",
  },
  json: {
    extension: "json",
    mimeType: "application/json;charset=utf-8",
  },
};

export function transcriptFormatConfig(format) {
  return FORMAT_CONFIG[format] || FORMAT_CONFIG.markdown;
}

export function buildTranscriptFilename(session, format) {
  const { extension } = transcriptFormatConfig(format);
  const base = (session?.title || "session-transcript")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);

  return `${base || "session-transcript"}.${extension}`;
}

export function buildTranscriptContent(session, messages, format) {
  if (format === "json") {
    return JSON.stringify(
      {
        exported_at: new Date().toISOString(),
        session,
        messages,
      },
      null,
      2,
    );
  }

  return buildMarkdownTranscript(session, messages);
}

function buildMarkdownTranscript(session, messages) {
  const lines = [
    `# ${session?.title || "Session transcript"}`,
    "",
    `- Session ID: ${session?.session_id ?? "unknown"}`,
    `- Exported: ${new Date().toISOString()}`,
  ];

  if (session?.created_at) {
    lines.push(`- Created: ${session.created_at}`);
  }
  if (session?.updated_at) {
    lines.push(`- Updated: ${session.updated_at}`);
  }

  lines.push("");

  for (const message of messages || []) {
    lines.push(`## ${message.role === "assistant" ? "Assistant" : "You"}`);
    if (message.created_at) {
      lines.push("");
      lines.push(`_${message.created_at}_`);
    }
    lines.push("");
    lines.push(message.content || "");
    lines.push("");
  }

  return `${lines.join("\n").trim()}\n`;
}
