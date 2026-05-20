/**
 * @file Search-term highlighting utilities for rendered message content.
 *
 * Provides case-insensitive substring highlighting that wraps matched
 * segments in <mark> elements. Works both on raw text strings and within
 * React element trees (recursing into children) so that Markdown-rendered
 * assistant messages can be highlighted without breaking their structure.
 */

import React from "react";

export function highlightTextSegment(text, query) {
  if (!query || !text) return text;

  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();
  const parts = [];
  let lastIndex = 0;
  let keyCounter = 0;
  let hasMatch = false;

  let index = lowerText.indexOf(lowerQuery, lastIndex);
  while (index !== -1) {
    hasMatch = true;
    if (index > lastIndex) {
      parts.push(text.slice(lastIndex, index));
    }
    parts.push(
      <mark className="search-highlight" key={keyCounter++}>
        {text.slice(index, index + query.length)}
      </mark>
    );
    lastIndex = index + query.length;
    index = lowerText.indexOf(lowerQuery, lastIndex);
  }

  if (!hasMatch) return text;

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

export function highlightChildren(children, query) {
  if (!query) return children;
  return React.Children.map(children, (child) => {
    if (typeof child === "string") {
      return highlightTextSegment(child, query);
    }
    if (React.isValidElement(child) && child.props?.children) {
      return React.cloneElement(
        child,
        {},
        highlightChildren(child.props.children, query)
      );
    }
    return child;
  });
}
