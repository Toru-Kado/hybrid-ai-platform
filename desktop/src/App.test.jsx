import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { DEFAULT_SIDEBAR_WIDTH, SIDEBAR_MAX_WIDTH, SIDEBAR_MIN_WIDTH } from "./layout";

function createAssistantApi() {
  return {
    health: vi.fn().mockResolvedValue({
      provider: "bedrock",
      aws_region: "us-east-1",
      target_kind: "inference profile",
    }),
    listSessions: vi.fn().mockResolvedValue({
      sessions: [
        {
          session_id: "session-1",
          title: "Platform overview",
          preview: "Summarize the hybrid AI platform.",
        },
        {
          session_id: "session-2",
          title: "Jerusalem notes",
          preview: "Export and search the saved conversations.",
        },
      ],
    }),
    getSession: vi.fn().mockResolvedValue({
      session: {
        session_id: "session-1",
        title: "Platform overview",
        preview: "Summarize the hybrid AI platform.",
      },
      messages: [
        {
          message_id: "message-1",
          role: "assistant",
          content: "The platform routes Claude through Bedrock.",
          created_at: "2026-04-23T08:00:00.000Z",
          metadata: { request_id: "req-1", output_tokens: 12, latency_ms: 34 },
        },
      ],
    }),
    createSession: vi.fn().mockResolvedValue({
      session: {
        session_id: "session-2",
        title: "New session",
        preview: "",
      },
    }),
    renameSession: vi.fn().mockImplementation(async (sessionId, payload) => ({
      session: {
        session_id: sessionId,
        title: payload.title,
        preview: "Summarize the hybrid AI platform.",
      },
    })),
    deleteSession: vi.fn().mockResolvedValue(undefined),
    saveTranscript: vi.fn().mockResolvedValue({ canceled: false, path: "/tmp/session.md" }),
    chat: vi.fn().mockResolvedValue({
      session: {
        session_id: "session-1",
        title: "Platform overview",
        preview: "Summarize the hybrid AI platform.",
      },
      message: {
        message_id: "message-2",
        role: "assistant",
        content: "Streaming works in readable chunks.",
        created_at: "2026-04-23T08:02:00.000Z",
        metadata: { request_id: "req-2", output_tokens: 24, latency_ms: 48 },
      },
    }),
  };
}

function setViewportWidth(width) {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: width,
  });
}

async function renderApp(width, assistantApi = createAssistantApi()) {
  setViewportWidth(width);
  window.assistantApi = assistantApi;
  const view = render(<App />);
  await screen.findByText("Connected");
  return { ...view, assistantApi };
}

describe("App layout behavior", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    delete window.assistantApi;
    vi.useRealTimers();
  });

  it("collapses the session history behind a toggle on narrow viewports", async () => {
    await renderApp(900);
    const user = userEvent.setup();
    const sidebar = screen.getByLabelText("Conversation history");
    const controlsToggle = screen.getByRole("button", { name: "Show controls" });

    expect(sidebar).toHaveAttribute("aria-hidden", "true");
    expect(controlsToggle).toHaveAttribute("aria-expanded", "false");

    await user.click(screen.getByRole("button", { name: "Show sessions" }));
    expect(sidebar).toHaveAttribute("aria-hidden", "false");

    await user.click(controlsToggle);
    expect(controlsToggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByLabelText("System prompt override")).toBeInTheDocument();
  });

  it("shows the app icon in the header chrome", async () => {
    await renderApp(1440);

    expect(screen.getByAltText("Hybrid AI Platform icon")).toBeInTheDocument();
  });

  it("filters saved sessions by title and preview text", async () => {
    await renderApp(1440);
    const user = userEvent.setup();
    const sidebar = screen.getByLabelText("Conversation history");

    expect(within(sidebar).getByText("Platform overview")).toBeInTheDocument();
    expect(within(sidebar).getByText("Jerusalem notes")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Search sessions"), "jerusalem");

    expect(within(sidebar).queryByText("Platform overview")).not.toBeInTheDocument();
    expect(within(sidebar).getByText("Jerusalem notes")).toBeInTheDocument();
  });

  it("lets the desktop sidebar resize within the supported bounds", async () => {
    const { container } = await renderApp(1440);
    const layout = container.querySelector(".chat-layout");
    const resizer = screen.getByRole("separator", { name: "Resize session sidebar" });

    expect(layout).toHaveStyle({ "--sidebar-width": `${DEFAULT_SIDEBAR_WIDTH}px` });

    fireEvent.pointerDown(resizer, { clientX: 320 });
    fireEvent.pointerMove(window, { clientX: 640 });
    fireEvent.pointerUp(window);

    await waitFor(() => {
      expect(layout).toHaveStyle({ "--sidebar-width": `${SIDEBAR_MAX_WIDTH}px` });
    });

    fireEvent.pointerDown(resizer, { clientX: 640 });
    fireEvent.pointerMove(window, { clientX: 80 });
    fireEvent.pointerUp(window);

    await waitFor(() => {
      expect(layout).toHaveStyle({ "--sidebar-width": `${SIDEBAR_MIN_WIDTH}px` });
    });
  });

  it("reopens the desktop sidebar automatically after widening back out", async () => {
    await renderApp(900);
    const sidebar = screen.getByLabelText("Conversation history");

    expect(sidebar).toHaveAttribute("aria-hidden", "true");

    setViewportWidth(1320);
    fireEvent(window, new Event("resize"));

    await waitFor(() => {
      expect(sidebar).toHaveAttribute("aria-hidden", "false");
    });
  });

  it("renames the active session inline", async () => {
    const { assistantApi } = await renderApp(1440);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Rename session" }));
    const titleInput = screen.getByLabelText("Session title");
    await user.clear(titleInput);
    await user.type(titleInput, "Jerusalem planning");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(assistantApi.renameSession).toHaveBeenCalledWith("session-1", {
      title: "Jerusalem planning",
    });
    await screen.findByRole("heading", { name: "Jerusalem planning" });
  });

  it("deletes the active session and clears the thread when none remain", async () => {
    const assistantApi = createAssistantApi();
    assistantApi.listSessions.mockResolvedValueOnce({
      sessions: [
        {
          session_id: "session-1",
          title: "Platform overview",
          preview: "Summarize the hybrid AI platform.",
        },
      ],
    });
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const { assistantApi: mountedApi } = await renderApp(1440, assistantApi);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Delete session" }));

    expect(confirmSpy).toHaveBeenCalled();
    expect(mountedApi.deleteSession).toHaveBeenCalledWith("session-1");
    await screen.findByText("Start a session and the full conversation will scroll here.");
  });

  it("exports the active session as markdown", async () => {
    const { assistantApi } = await renderApp(1440);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Export .md" }));

    await waitFor(() => {
      expect(assistantApi.saveTranscript).toHaveBeenCalled();
    });
    expect(assistantApi.saveTranscript).toHaveBeenCalledWith(
      expect.objectContaining({
        format: "markdown",
        suggestedName: "platform-overview.md",
        content: expect.stringContaining("The platform routes Claude through Bedrock."),
      }),
    );
    await screen.findByText("Exported Markdown transcript.");
  });

  it("reveals assistant replies progressively after the response arrives", async () => {
    const { assistantApi } = await renderApp(1440);
    const user = userEvent.setup();

    await user.clear(screen.getByLabelText("Prompt"));
    await user.type(screen.getByLabelText("Prompt"), "Give me a progress demo");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => {
      expect(assistantApi.chat).toHaveBeenCalled();
    });

    await screen.findByText("Streaming response...");
    await screen.findByRole("button", { name: "Streaming..." });
    await screen.findByText("Streaming works in readable chunks.");
  });
});
