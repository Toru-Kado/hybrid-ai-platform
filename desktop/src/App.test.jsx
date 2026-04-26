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
      target_kind: "inference_profile",
      target_id: "us.anthropic.claude-opus-4-6-v1",
      target_source: "BEDROCK_INFERENCE_PROFILE_ID",
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
    streamChat: vi.fn().mockImplementation(async (_payload, handlers = {}) => {
      const session = {
        session_id: "session-1",
        title: "Platform overview",
        preview: "Summarize the hybrid AI platform.",
      };
      const userMessage = {
        message_id: "message-user-2",
        role: "user",
        content: "Give me a progress demo",
        created_at: "2026-04-23T08:01:00.000Z",
        metadata: null,
      };
      const message = {
        message_id: "message-2",
        role: "assistant",
        content: "Streaming works in readable chunks.",
        created_at: "2026-04-23T08:02:00.000Z",
        metadata: { request_id: "req-2", output_tokens: 24, latency_ms: 48 },
      };
      const completePayload = { session, message };

      await handlers.onSession?.(session);
      await handlers.onUserMessage?.(userMessage);
      await handlers.onTextDelta?.("Streaming works ");
      await handlers.onTextDelta?.("in readable chunks.");
      await handlers.onComplete?.(completePayload);
      return completePayload;
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

function renderAppWithoutWaiting(width, assistantApi = createAssistantApi()) {
  setViewportWidth(width);
  window.assistantApi = assistantApi;
  return { ...render(<App />), assistantApi };
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
    const { container } = await renderApp(900);
    const user = userEvent.setup();
    const sidebar = screen.getByLabelText("Conversation history");
    const preferencesToggle = screen.getByRole("button", { name: "Show preferences" });
    const preferencesPanel = container.querySelector("#preferences-panel");

    expect(sidebar).toHaveAttribute("aria-hidden", "true");
    expect(preferencesToggle).toHaveAttribute("aria-expanded", "false");
    expect(preferencesPanel).toHaveAttribute("hidden");

    await user.click(screen.getByRole("button", { name: "Show sessions" }));
    expect(sidebar).toHaveAttribute("aria-hidden", "false");

    await user.click(preferencesToggle);
    expect(preferencesToggle).toHaveAttribute("aria-expanded", "true");
    expect(preferencesPanel).not.toHaveAttribute("hidden");
    expect(screen.getByLabelText("System prompt override")).toBeInTheDocument();
  });

  it("keeps the preferences panel collapsed until opened, then hides it again", async () => {
    const { container } = await renderApp(1440);
    const user = userEvent.setup();
    const preferencesPanel = container.querySelector("#preferences-panel");
    const toggle = screen.getByRole("button", { name: "Show preferences" });

    expect(preferencesPanel).toHaveAttribute("hidden");

    await user.click(toggle);

    expect(screen.getByLabelText("System prompt override")).toBeVisible();
    expect(screen.getByText("us.anthropic.claude-opus-4-6-v1")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Hide preferences" }));

    expect(preferencesPanel).toHaveAttribute("hidden");
    expect(screen.getByRole("button", { name: "Show preferences" })).toBeInTheDocument();
  });

  it("surfaces runtime target details clearly inside the preferences panel", async () => {
    await renderApp(1440);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Show preferences" }));
    const panel = screen.getByLabelText("Preferences and runtime");

    expect(within(panel).getByText("Inference Profile")).toBeInTheDocument();
    expect(within(panel).getByText("BEDROCK_INFERENCE_PROFILE_ID")).toBeInTheDocument();
    expect(within(panel).getByText("us.anthropic.claude-opus-4-6-v1")).toBeInTheDocument();
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
    await screen.findByText("Create a session to begin a new conversation.");
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

  it("exports the active session as json", async () => {
    const { assistantApi } = await renderApp(1440);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Export .json" }));

    await waitFor(() => {
      expect(assistantApi.saveTranscript).toHaveBeenCalled();
    });
    expect(assistantApi.saveTranscript).toHaveBeenCalledWith(
      expect.objectContaining({
        format: "json",
        suggestedName: "platform-overview.json",
        content: expect.stringContaining("\"title\": \"Platform overview\""),
      }),
    );
    await screen.findByText("Exported JSON transcript.");
  });

  it("shows a retry affordance when the desktop bootstrap cannot reach the local API", async () => {
    const assistantApi = createAssistantApi();
    assistantApi.health.mockRejectedValueOnce(new Error("Could not reach local API."));
    renderAppWithoutWaiting(1440, assistantApi);
    const user = userEvent.setup();

    await screen.findByText("Connection problem");
    expect(screen.getByText(/The local assistant API may still be starting/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry connection" }));

    await screen.findByText("Connected");
    expect(assistantApi.health).toHaveBeenCalledTimes(2);
  });

  it("offers a session-specific retry when conversation loading fails", async () => {
    const assistantApi = createAssistantApi();
    assistantApi.getSession.mockRejectedValueOnce(new Error("Connection refused while loading session."));
    await renderApp(1440, assistantApi);
    const user = userEvent.setup();

    await screen.findByText("Could not load this session");
    await screen.findByText("Conversation unavailable");

    await user.click(screen.getByRole("button", { name: "Retry loading session" }));

    await screen.findByText("The platform routes Claude through Bedrock.");
    expect(assistantApi.getSession).toHaveBeenCalledTimes(2);
  });

  it("classifies AWS auth failures clearly and retries the failed prompt", async () => {
    const assistantApi = createAssistantApi();
    assistantApi.streamChat.mockRejectedValueOnce(
      new Error("ExpiredToken: The security token included in the request is expired."),
    );
    await renderApp(1440, assistantApi);
    const user = userEvent.setup();

    await user.clear(screen.getByLabelText("Prompt"));
    await user.type(screen.getByLabelText("Prompt"), "Keep this prompt");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    await screen.findByText("AWS authentication needed");
    expect(
      screen.getByText(/Refresh the active AWS session, then retry/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry request" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry request" }));

    await waitFor(() => {
      expect(assistantApi.streamChat).toHaveBeenCalledTimes(2);
    });
    await screen.findByText("Streaming works in readable chunks.");
  });

  it("renders assistant replies from live stream events", async () => {
    const gate = { promise: null, resolve: null };
    gate.promise = new Promise((resolve) => {
      gate.resolve = resolve;
    });
    const assistantApi = createAssistantApi();
    assistantApi.streamChat.mockImplementationOnce(async (_payload, handlers = {}) => {
      const session = {
        session_id: "session-1",
        title: "Platform overview",
        preview: "Summarize the hybrid AI platform.",
      };
      const userMessage = {
        message_id: "message-user-2",
        role: "user",
        content: "Give me a progress demo",
        created_at: "2026-04-23T08:01:00.000Z",
        metadata: null,
      };
      const message = {
        message_id: "message-2",
        role: "assistant",
        content: "Streaming works in readable chunks.",
        created_at: "2026-04-23T08:02:00.000Z",
        metadata: { request_id: "req-2", output_tokens: 24, latency_ms: 48 },
      };
      const completePayload = { session, message };

      await handlers.onSession?.(session);
      await handlers.onUserMessage?.(userMessage);
      await handlers.onTextDelta?.("Streaming works ");
      await gate.promise;
      await handlers.onTextDelta?.("in readable chunks.");
      await handlers.onComplete?.(completePayload);
      return completePayload;
    });

    await renderApp(1440, assistantApi);
    const user = userEvent.setup();

    await user.clear(screen.getByLabelText("Prompt"));
    await user.type(screen.getByLabelText("Prompt"), "Give me a progress demo");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => {
      expect(assistantApi.streamChat).toHaveBeenCalled();
    });

    await screen.findByText("Streaming response...");
    await screen.findByRole("button", { name: "Streaming..." });
    gate.resolve();
    await screen.findByText("Streaming works in readable chunks.");
  });
});
