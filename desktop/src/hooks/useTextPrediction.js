/**
 * @file Inline text prediction (ghost-text) hook.
 *
 * Provides speculative autocompletion suggestions as the user types a prompt.
 * After a debounce period, sends the current input to the backend /api/complete
 * endpoint and displays the returned continuation as faded "ghost text" in the
 * composer. Users accept suggestions via Tab (full) or Ctrl+Right (word-by-word),
 * or dismiss with Escape.
 *
 * Predictions are best-effort: network/model failures are silently swallowed.
 * The feature can be toggled on/off from the preferences panel.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api";
import {
  getTextPredictionEnabled,
  storeTextPredictionEnabled,
} from "../prediction-prefs";

const DEBOUNCE_MS = 300;
const MIN_TEXT_LENGTH = 3;

export default function useTextPrediction({ prompt, isBusy }) {
  const [suggestion, setSuggestion] = useState("");
  const [isEnabled, setIsEnabled] = useState(() => getTextPredictionEnabled());
  const debounceRef = useRef(null);
  const abortRef = useRef(null);
  const lastPromptRef = useRef("");

  useEffect(() => {
    if (prompt !== lastPromptRef.current) {
      setSuggestion("");
      lastPromptRef.current = prompt;
    }
  }, [prompt]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (abortRef.current) abortRef.current.abort = true;

    if (!isEnabled || isBusy || prompt.trim().length < MIN_TEXT_LENGTH) {
      setSuggestion("");
      return;
    }

    debounceRef.current = setTimeout(() => {
      fetchPrediction(prompt);
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [prompt, isEnabled, isBusy]);

  function fetchPrediction(text) {
    const token = { abort: false };
    abortRef.current = token;

    api()
      .complete({ text, max_tokens: 50 })
      .then((result) => {
        if (!token.abort && result.completion) {
          setSuggestion(result.completion);
        }
      })
      .catch(() => {
        // Silently fail — prediction is best-effort
      });
  }

  const acceptFull = useCallback(() => {
    if (!suggestion) return null;
    const accepted = suggestion;
    setSuggestion("");
    return accepted;
  }, [suggestion]);

  const acceptWord = useCallback(() => {
    if (!suggestion) return null;
    const match = suggestion.match(/^\s*\S+/);
    if (!match) return null;
    const word = match[0];
    setSuggestion(suggestion.slice(word.length));
    return word;
  }, [suggestion]);

  const dismiss = useCallback(() => {
    setSuggestion("");
  }, []);

  const setEnabled = useCallback((enabled) => {
    setIsEnabled(enabled);
    storeTextPredictionEnabled(enabled);
    if (!enabled) setSuggestion("");
  }, []);

  return {
    suggestion,
    isEnabled,
    setIsEnabled: setEnabled,
    acceptFull,
    acceptWord,
    dismiss,
  };
}
