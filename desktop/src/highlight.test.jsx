import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { highlightTextSegment, highlightChildren } from "./highlight";

describe("highlightTextSegment", () => {
  it("returns original text when query is empty", () => {
    expect(highlightTextSegment("hello world", "")).toBe("hello world");
  });

  it("returns original text when query is null", () => {
    expect(highlightTextSegment("hello world", null)).toBe("hello world");
  });

  it("wraps a single match in a mark element", () => {
    const result = highlightTextSegment("hello world", "world");
    const { container } = render(<p>{result}</p>);
    const marks = container.querySelectorAll("mark.search-highlight");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe("world");
  });

  it("wraps multiple matches", () => {
    const result = highlightTextSegment("foo bar foo baz foo", "foo");
    const { container } = render(<p>{result}</p>);
    const marks = container.querySelectorAll("mark.search-highlight");
    expect(marks).toHaveLength(3);
  });

  it("matches case-insensitively", () => {
    const result = highlightTextSegment("Hello HELLO hello", "hello");
    const { container } = render(<p>{result}</p>);
    const marks = container.querySelectorAll("mark.search-highlight");
    expect(marks).toHaveLength(3);
    expect(marks[0].textContent).toBe("Hello");
    expect(marks[1].textContent).toBe("HELLO");
    expect(marks[2].textContent).toBe("hello");
  });

  it("preserves surrounding text", () => {
    const result = highlightTextSegment("before match after", "match");
    const { container } = render(<p>{result}</p>);
    expect(container.textContent).toBe("before match after");
  });

  it("handles query not found in text", () => {
    const result = highlightTextSegment("hello world", "xyz");
    expect(result).toBe("hello world");
  });
});

describe("highlightChildren", () => {
  it("returns children unchanged when query is empty", () => {
    const children = "some text";
    expect(highlightChildren(children, "")).toBe("some text");
  });

  it("highlights string children", () => {
    const result = highlightChildren("search me for keyword here", "keyword");
    const { container } = render(<p>{result}</p>);
    const marks = container.querySelectorAll("mark.search-highlight");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe("keyword");
  });
});
