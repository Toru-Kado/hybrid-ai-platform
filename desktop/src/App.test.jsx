import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { SIDEBAR_MAX_WIDTH, SIDEBAR_MIN_WIDTH } from "./layout";

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
    chat: vi.fn(),
  };
}

function setViewportWidth(width) {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: width,
  });
}

async function renderApp(width) {
  setViewportWidth(width);
  window.assistantApi = createAssistantApi();
  const view = render(<App />);
  await screen.findByText("Connected");
  return view;
}

describe("App layout behavior", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    delete window.assistantApi;
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

  it("lets the desktop sidebar resize within the supported bounds", async () => {
    const { container } = await renderApp(1440);
    const layout = container.querySelector(".chat-layout");
    const resizer = screen.getByRole("separator", { name: "Resize session sidebar" });

    expect(layout).toHaveStyle({ "--sidebar-width": "320px" });

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
});
