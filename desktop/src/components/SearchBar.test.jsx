import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import SearchBar from "./SearchBar";

const defaultProps = {
  isSearchOpen: true,
  searchQuery: "",
  searchMode: "session",
  localResults: [],
  crossResults: [],
  activeMatchIndex: 0,
  isSearching: false,
  onSetSearchQuery: vi.fn(),
  onSetSearchMode: vi.fn(),
  onNavigateMatch: vi.fn(),
  onClose: vi.fn(),
};

describe("SearchBar", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders nothing when isSearchOpen is false", () => {
    const { container } = render(
      <SearchBar {...defaultProps} isSearchOpen={false} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders search input when isSearchOpen is true", () => {
    render(<SearchBar {...defaultProps} />);
    expect(screen.getByRole("search")).toBeDefined();
    expect(screen.getByLabelText("Search query")).toBeDefined();
  });

  it("calls onSetSearchQuery when input changes", () => {
    const onSetSearchQuery = vi.fn();
    render(<SearchBar {...defaultProps} onSetSearchQuery={onSetSearchQuery} />);
    fireEvent.change(screen.getByLabelText("Search query"), {
      target: { value: "test" },
    });
    expect(onSetSearchQuery).toHaveBeenCalledWith("test");
  });

  it("calls onNavigateMatch(1) on Enter", () => {
    const onNavigateMatch = vi.fn();
    render(<SearchBar {...defaultProps} onNavigateMatch={onNavigateMatch} />);
    fireEvent.keyDown(screen.getByLabelText("Search query"), { key: "Enter" });
    expect(onNavigateMatch).toHaveBeenCalledWith(1);
  });

  it("calls onNavigateMatch(-1) on Shift+Enter", () => {
    const onNavigateMatch = vi.fn();
    render(<SearchBar {...defaultProps} onNavigateMatch={onNavigateMatch} />);
    fireEvent.keyDown(screen.getByLabelText("Search query"), {
      key: "Enter",
      shiftKey: true,
    });
    expect(onNavigateMatch).toHaveBeenCalledWith(-1);
  });

  it("calls onClose on Escape", () => {
    const onClose = vi.fn();
    render(<SearchBar {...defaultProps} onClose={onClose} />);
    fireEvent.keyDown(screen.getByLabelText("Search query"), { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when Close button is clicked", () => {
    const onClose = vi.fn();
    render(<SearchBar {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText("Close search"));
    expect(onClose).toHaveBeenCalled();
  });

  it("toggles search mode via checkbox", () => {
    const onSetSearchMode = vi.fn();
    render(<SearchBar {...defaultProps} onSetSearchMode={onSetSearchMode} />);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onSetSearchMode).toHaveBeenCalledWith("all");
  });

  it("shows match count when results exist", () => {
    render(
      <SearchBar
        {...defaultProps}
        searchQuery="test"
        localResults={[
          { messageId: 1, messageIndex: 0 },
          { messageId: 2, messageIndex: 1 },
        ]}
        activeMatchIndex={0}
      />
    );
    expect(screen.getByText("1 of 2")).toBeDefined();
  });

  it("shows 'No matches' when query exists but no results", () => {
    render(<SearchBar {...defaultProps} searchQuery="xyz" />);
    expect(screen.getByText("No matches")).toBeDefined();
  });

  it("shows 'Searching...' when isSearching is true", () => {
    render(<SearchBar {...defaultProps} searchQuery="test" isSearching={true} />);
    expect(screen.getByText("Searching...")).toBeDefined();
  });

  it("disables Prev/Next buttons when no results", () => {
    render(<SearchBar {...defaultProps} />);
    expect(screen.getByLabelText("Previous match").disabled).toBe(true);
    expect(screen.getByLabelText("Next match").disabled).toBe(true);
  });
});
