import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import ChatInput from "./ChatInput";

function renderChatInput(overrides = {}) {
  const props = {
    prompt: "How do I",
    isLoading: false,
    streamingMessageId: null,
    isBusy: false,
    onSetPrompt: vi.fn(),
    onSubmit: vi.fn((e) => e?.preventDefault?.()),
    suggestion: "",
    onAcceptFull: vi.fn().mockReturnValue(null),
    onAcceptWord: vi.fn().mockReturnValue(null),
    onDismiss: vi.fn(),
    ...overrides,
  };
  const view = render(<ChatInput {...props} />);
  return { ...view, props };
}

describe("ChatInput", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders textarea with prompt value", () => {
    renderChatInput();
    expect(screen.getByLabelText("Prompt")).toHaveValue("How do I");
  });

  it("does not render ghost text when suggestion is empty", () => {
    const { container } = renderChatInput({ suggestion: "" });
    expect(container.querySelector(".ghost-text")).toBeNull();
  });

  it("renders ghost text with aria-hidden when suggestion is provided", () => {
    const { container } = renderChatInput({ suggestion: "configure AWS?" });
    const ghost = container.querySelector(".ghost-text");
    expect(ghost).not.toBeNull();
    expect(ghost).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelector(".ghost-text-prefix").textContent).toBe("How do I");
    expect(container.querySelector(".ghost-text-suggestion").textContent).toBe("configure AWS?");
  });

  it("accepts full suggestion on Tab key", () => {
    const onAcceptFull = vi.fn().mockReturnValue("configure AWS?");
    const onSetPrompt = vi.fn();
    renderChatInput({
      suggestion: "configure AWS?",
      onAcceptFull,
      onSetPrompt,
    });

    fireEvent.keyDown(screen.getByRole("textbox", { name: "Prompt" }), { key: "Tab" });

    expect(onAcceptFull).toHaveBeenCalled();
    expect(onSetPrompt).toHaveBeenCalledWith("How do Iconfigure AWS?");
  });

  it("does not intercept Tab when no suggestion is present", () => {
    const { props } = renderChatInput({ suggestion: "" });

    fireEvent.keyDown(screen.getByRole("textbox", { name: "Prompt" }), { key: "Tab" });

    expect(props.onAcceptFull).not.toHaveBeenCalled();
  });

  it("accepts next word on Ctrl+ArrowRight", () => {
    const onAcceptWord = vi.fn().mockReturnValue("configure");
    const onSetPrompt = vi.fn();
    renderChatInput({
      suggestion: "configure AWS?",
      onAcceptWord,
      onSetPrompt,
    });

    fireEvent.keyDown(screen.getByRole("textbox", { name: "Prompt" }), {
      key: "ArrowRight",
      ctrlKey: true,
    });

    expect(onAcceptWord).toHaveBeenCalled();
    expect(onSetPrompt).toHaveBeenCalledWith("How do Iconfigure");
  });

  it("accepts next word on Alt+ArrowRight", () => {
    const onAcceptWord = vi.fn().mockReturnValue("configure");
    const onSetPrompt = vi.fn();
    renderChatInput({
      suggestion: "configure AWS?",
      onAcceptWord,
      onSetPrompt,
    });

    fireEvent.keyDown(screen.getByRole("textbox", { name: "Prompt" }), {
      key: "ArrowRight",
      altKey: true,
    });

    expect(onAcceptWord).toHaveBeenCalled();
    expect(onSetPrompt).toHaveBeenCalledWith("How do Iconfigure");
  });

  it("dismisses suggestion on Escape", () => {
    const onDismiss = vi.fn();
    renderChatInput({ suggestion: "configure AWS?", onDismiss });

    fireEvent.keyDown(screen.getByRole("textbox", { name: "Prompt" }), { key: "Escape" });

    expect(onDismiss).toHaveBeenCalled();
  });

  it("does not dismiss on Escape when no suggestion", () => {
    const { props } = renderChatInput({ suggestion: "" });

    fireEvent.keyDown(screen.getByRole("textbox", { name: "Prompt" }), { key: "Escape" });

    expect(props.onDismiss).not.toHaveBeenCalled();
  });

  it("submits on Enter when not busy and prompt is non-empty", () => {
    const onSubmit = vi.fn((e) => e?.preventDefault?.());
    renderChatInput({ onSubmit });

    fireEvent.keyDown(screen.getByRole("textbox", { name: "Prompt" }), { key: "Enter" });

    expect(onSubmit).toHaveBeenCalled();
  });

  it("does not submit on Shift+Enter", () => {
    const { props } = renderChatInput();

    fireEvent.keyDown(screen.getByRole("textbox", { name: "Prompt" }), {
      key: "Enter",
      shiftKey: true,
    });

    expect(props.onSubmit).toHaveBeenCalledTimes(0);
  });
});
