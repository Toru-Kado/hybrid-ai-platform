import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

const DEBOUNCE_MS = 300;

export default function useMessageSearch({ messages, activeSession }) {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState("session");
  const [localResults, setLocalResults] = useState([]);
  const [crossResults, setCrossResults] = useState([]);
  const [activeMatchIndex, setActiveMatchIndex] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [targetMessageId, setTargetMessageId] = useState(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    function handleKeyDown(event) {
      if ((event.metaKey || event.ctrlKey) && event.key === "f") {
        event.preventDefault();
        setIsSearchOpen(true);
      }
      if (event.key === "Escape" && isSearchOpen) {
        closeSearch();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isSearchOpen]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    const trimmed = searchQuery.trim();
    if (!trimmed) {
      setLocalResults([]);
      setCrossResults([]);
      setActiveMatchIndex(0);
      return;
    }

    debounceRef.current = setTimeout(() => {
      if (searchMode === "session") {
        performLocalSearch(trimmed);
      } else {
        performCrossSearch(trimmed);
      }
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [searchQuery, searchMode, messages]);

  function performLocalSearch(query) {
    const lowerQuery = query.toLowerCase();
    const matches = [];
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i];
      const content = (msg.content || "").toLowerCase();
      if (content.includes(lowerQuery)) {
        matches.push({
          messageId: msg.message_id,
          messageIndex: i,
        });
      }
    }
    setLocalResults(matches);
    setCrossResults([]);
    setActiveMatchIndex(0);
  }

  async function performCrossSearch(query) {
    setIsSearching(true);
    try {
      const response = await api().searchMessages(query, {});
      setCrossResults(response.results || []);
      setLocalResults([]);
      setActiveMatchIndex(0);
    } catch (_error) {
      setCrossResults([]);
    } finally {
      setIsSearching(false);
    }
  }

  const navigateMatch = useCallback(
    (direction) => {
      const results = searchMode === "session" ? localResults : crossResults;
      if (results.length === 0) return;
      setActiveMatchIndex(
        (prev) => (prev + direction + results.length) % results.length
      );
    },
    [searchMode, localResults, crossResults]
  );

  function selectCrossResult(result) {
    setTargetMessageId(result.message_id);
  }

  function closeSearch() {
    setIsSearchOpen(false);
    setSearchQuery("");
    setLocalResults([]);
    setCrossResults([]);
    setActiveMatchIndex(0);
    setTargetMessageId(null);
  }

  const activeLocalMatch =
    searchMode === "session" && localResults.length > 0
      ? localResults[activeMatchIndex]
      : null;

  const activeCrossResult =
    searchMode === "all" && crossResults.length > 0
      ? crossResults[activeMatchIndex]
      : null;

  const highlightedMessageId =
    activeLocalMatch?.messageId ?? activeCrossResult?.message_id ?? targetMessageId ?? null;

  return {
    isSearchOpen,
    setIsSearchOpen,
    searchQuery,
    setSearchQuery,
    searchMode,
    setSearchMode,
    localResults,
    crossResults,
    activeMatchIndex,
    activeCrossResult,
    isSearching,
    highlightedMessageId,
    navigateMatch,
    selectCrossResult,
    closeSearch,
  };
}
