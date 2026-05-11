/**
 * @file Transcript export utilities.
 *
 * Builds downloadable transcript content (Markdown or JSON) from a session
 * and its messages. Used by the export feature to let users save conversation
 * history to a local file.
 */

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

/**
 * Returns the file extension and MIME type for a given transcript format.
 * Defaults to markdown if the format is unrecognized.
 * @param {string} format - "markdown" or "json".
 * @returns {{ extension: string, mimeType: string }}
 */
export function transcriptFormatConfig(format) {
  return FORMAT_CONFIG[format] || FORMAT_CONFIG.markdown;
}

/**
 * Generates a filesystem-safe filename for the transcript export, derived
 * from the session title with special characters replaced by hyphens.
 * @param {object} session - Session object (uses session.title).
 * @param {string} format - "markdown" or "json".
 * @returns {string} Suggested filename including extension.
 */
export function buildTranscriptFilename(session, format) {
  const { extension } = transcriptFormatConfig(format);
  const base = (session?.title || "session-transcript")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);

  return `${base || "session-transcript"}.${extension}`;
}

/**
 * Builds the full transcript content string in the specified format.
 * @param {object} session - Session metadata (id, title, timestamps).
 * @param {Array} messages - Array of message objects to include.
 * @param {string} format - "json" for structured JSON, anything else for Markdown.
 * @returns {string} The serialized transcript content.
 */
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

/**
 * Formats session messages into a human-readable Markdown document with
 * metadata header and role-labelled message sections.
 * @param {object} session - Session metadata.
 * @param {Array} messages - Conversation messages.
 * @returns {string} Markdown-formatted transcript.
 */
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
