import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";
import UpdateBanner from "./UpdateBanner";

describe("UpdateBanner", () => {
  let updateCallback;

  beforeEach(() => {
    updateCallback = null;
    window.assistantApi = {
      onUpdateEvent: vi.fn((cb) => {
        updateCallback = cb;
        return vi.fn(); // cleanup function
      }),
      downloadUpdate: vi.fn(),
      installUpdate: vi.fn(),
    };
  });

  afterEach(() => {
    cleanup();
    delete window.assistantApi;
  });

  it("renders nothing when no update is available", () => {
    const { container } = render(<UpdateBanner />);
    expect(container.querySelector(".update-banner")).toBeNull();
  });

  it("shows banner with version and Download button on update-available", () => {
    render(<UpdateBanner />);
    act(() => updateCallback({ type: "available", version: "1.2.0" }));
    expect(screen.getByText("Version 1.2.0 is available.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
  });

  it("shows progress during download", () => {
    render(<UpdateBanner />);
    act(() => updateCallback({ type: "available", version: "1.2.0" }));
    act(() => updateCallback({ type: "download-progress", percent: 42 }));
    expect(screen.getByText("Downloading update... 42%")).toBeInTheDocument();
  });

  it("shows Restart button when update is downloaded", () => {
    render(<UpdateBanner />);
    act(() => updateCallback({ type: "available", version: "1.2.0" }));
    act(() => updateCallback({ type: "downloaded", version: "1.2.0" }));
    expect(screen.getByText("Update ready — restart to apply.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Restart" })).toBeInTheDocument();
  });

  it("dismiss hides the banner", () => {
    const { container } = render(<UpdateBanner />);
    act(() => updateCallback({ type: "available", version: "1.2.0" }));
    expect(container.querySelector(".update-banner")).not.toBeNull();
    fireEvent.click(screen.getByLabelText("Dismiss update notification"));
    expect(container.querySelector(".update-banner")).toBeNull();
  });

  it("calls downloadUpdate on Download button click", () => {
    render(<UpdateBanner />);
    act(() => updateCallback({ type: "available", version: "1.2.0" }));
    fireEvent.click(screen.getByRole("button", { name: "Download" }));
    expect(window.assistantApi.downloadUpdate).toHaveBeenCalled();
  });

  it("calls installUpdate on Restart button click", () => {
    render(<UpdateBanner />);
    act(() => updateCallback({ type: "available", version: "1.2.0" }));
    act(() => updateCallback({ type: "downloaded", version: "1.2.0" }));
    fireEvent.click(screen.getByRole("button", { name: "Restart" }));
    expect(window.assistantApi.installUpdate).toHaveBeenCalled();
  });

  it("reverts to idle on error event (graceful offline)", () => {
    const { container } = render(<UpdateBanner />);
    act(() => updateCallback({ type: "available", version: "1.2.0" }));
    expect(container.querySelector(".update-banner")).not.toBeNull();
    act(() => updateCallback({ type: "error", message: "Network unavailable" }));
    expect(container.querySelector(".update-banner")).toBeNull();
  });
});
