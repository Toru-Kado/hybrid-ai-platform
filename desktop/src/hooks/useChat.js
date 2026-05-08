import { useEffect, useRef, useState } from "react";

import { api, streamChatApi } from "../api";
import { readCompactViewport, DEFAULT_SIDEBAR_WIDTH, clampSidebarWidth } from "../layout";
import { getStoredSidebarPrefs, storeSidebarPrefs } from "../sidebar-prefs";
import {
  buildErrorState,
  classifyErrorCategory,
  findLatestAssistantPair,
  mergeSession,
  replaceSession,
  writeToClipboard,
} from "../utils";
import { buildTranscriptContent, buildTranscriptFilename } from "../transcript";

export default function useChat() {
  const [health, setHealth] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [temperature, setTemperature] = useState(0.2);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [errorState, setErrorState] = useState(null);
  const [notice, setNotice] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isRenamingSession, setIsRenamingSession] = useState(false);
  const [renameTitle, setRenameTitle] = useState("");
  const [sessionFilter, setSessionFilter] = useState("");
  const [streamingMessageId, setStreamingMessageId] = useState(null);
  const [isCompactLayout, setIsCompactLayout] = useState(() => readCompactViewport());
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    if (readCompactViewport()) return false;
    const stored = getStoredSidebarPrefs();
    return stored && typeof stored.isOpen === "boolean" ? stored.isOpen : true;
  });
  const [isControlsOpen, setIsControlsOpen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const stored = getStoredSidebarPrefs();
    return stored && Number.isFinite(stored.width) ? clampSidebarWidth(stored.width) : DEFAULT_SIDEBAR_WIDTH;
  });

  const threadRef = useRef(null);
  const nextThreadScrollRef = useRef("top");
  const resizeCleanupRef = useRef(() => {});
  const previousCompactRef = useRef(readCompactViewport());
  const mountedRef = useRef(true);

  const latestAssistantPair = findLatestAssistantPair(messages);
  const isBusy = isLoading || streamingMessageId !== null;

  const normalizedSessionFilter = sessionFilter.trim().toLowerCase();
  const filteredSessions = sessions.filter((session) => {
    if (!normalizedSessionFilter) {
      return true;
    }
    const haystack = `${session.title || ""} ${session.preview || ""}`.toLowerCase();
    return haystack.includes(normalizedSessionFilter);
  });

  useEffect(() => {
    mountedRef.current = true;
    initializeApp();
    return () => {
      mountedRef.current = false;
      resizeCleanupRef.current();
    };
  }, []);

  useEffect(() => {
    const container = threadRef.current;
    if (!container) {
      return;
    }
    if (nextThreadScrollRef.current === "top") {
      container.scrollTop = 0;
      nextThreadScrollRef.current = null;
      return;
    }
    if (nextThreadScrollRef.current === "bottom" || isLoading || streamingMessageId !== null) {
      container.scrollTop = container.scrollHeight;
      if (nextThreadScrollRef.current === "bottom") {
        nextThreadScrollRef.current = null;
      }
    }
  }, [messages, isLoading, streamingMessageId]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    function syncLayoutMode() {
      setIsCompactLayout(readCompactViewport());
    }

    window.addEventListener("resize", syncLayoutMode);
    return () => {
      window.removeEventListener("resize", syncLayoutMode);
    };
  }, []);

  useEffect(() => {
    const previousCompact = previousCompactRef.current;
    if (previousCompact === isCompactLayout) {
      return;
    }
    previousCompactRef.current = isCompactLayout;
    setIsSidebarOpen(!isCompactLayout);
    if (isCompactLayout) {
      setIsControlsOpen(false);
    }
  }, [isCompactLayout]);

  useEffect(() => {
    storeSidebarPrefs({ width: sidebarWidth, isOpen: isSidebarOpen });
  }, [sidebarWidth, isSidebarOpen]);

  useEffect(() => {
    if (isRenamingSession) {
      return;
    }
    setRenameTitle(activeSession?.title || "");
  }, [activeSession, isRenamingSession]);

  function clearFeedback() {
    setErrorState(null);
    setNotice("");
  }

  async function initializeApp(options = {}) {
    const { preferredSessionId = null } = options;
    setIsLoadingSessions(true);
    clearFeedback();

    try {
      const [healthPayload, sessionsPayload] = await Promise.all([
        api().health(),
        api().listSessions(),
      ]);
      if (!mountedRef.current) {
        return;
      }
      setHealth(healthPayload);
      const nextSessions = sessionsPayload.sessions || [];
      setSessions(nextSessions);

      if (nextSessions.length === 0) {
        setActiveSession(null);
        setMessages([]);
        return;
      }

      const selectedSessionId =
        preferredSessionId &&
        nextSessions.some((session) => session.session_id === preferredSessionId)
          ? preferredSessionId
          : nextSessions[0].session_id;
      await loadSession(selectedSessionId);
    } catch (caught) {
      if (!mountedRef.current) {
        return;
      }
      setHealth(null);
      setSessions([]);
      setActiveSession(null);
      setMessages([]);
      setErrorState(
        buildErrorState(caught?.message, {
          context: "bootstrap",
          retry: { action: "initialize", label: "Retry connection" },
        }),
      );
    } finally {
      if (mountedRef.current) {
        setIsLoadingSessions(false);
      }
    }
  }

  async function loadSession(sessionId) {
    setStreamingMessageId(null);
    setIsLoadingHistory(true);
    clearFeedback();
    try {
      const payload = await api().getSession(sessionId);
      if (!mountedRef.current) {
        return;
      }
      nextThreadScrollRef.current = "top";
      setActiveSession(payload.session);
      setMessages(payload.messages || []);
      setIsRenamingSession(false);
    } catch (caught) {
      if (mountedRef.current) {
        setErrorState(
          buildErrorState(caught?.message, {
            context: "history",
            retry: { action: "session", label: "Retry loading session", sessionId },
          }),
        );
      }
    } finally {
      if (mountedRef.current) {
        setIsLoadingHistory(false);
      }
    }
  }

  async function createSession() {
    setStreamingMessageId(null);
    clearFeedback();
    try {
      const payload = await api().createSession({});
      const session = payload.session;
      setSessions((current) => [session, ...current]);
      setActiveSession(session);
      setMessages([]);
      setIsRenamingSession(true);
      setRenameTitle(session.title);
      if (isCompactLayout) {
        setIsSidebarOpen(false);
      }
    } catch (caught) {
      setErrorState(buildErrorState(caught?.message, { context: "session_create" }));
    }
  }

  async function submitPrompt(event) {
    event.preventDefault();
    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt) {
      setErrorState(
        buildErrorState("Write a prompt first.", {
          context: "prompt",
        }),
      );
      return;
    }

    await sendPrompt({
      session_id: activeSession?.session_id,
      prompt: trimmedPrompt,
      system_prompt: systemPrompt || undefined,
      temperature: Number(temperature),
      max_tokens: Number(maxTokens),
    });
  }

  async function sendPrompt(requestPayload) {
    const trimmedPrompt = requestPayload.prompt.trim();

    const pendingUserMessage = {
      message_id: `pending-user-${Date.now()}`,
      role: "user",
      content: trimmedPrompt,
      created_at: new Date().toISOString(),
      metadata: null,
    };
    const assistantMessageId = `assistant-${Date.now()}`;
    const pendingAssistantMessage = {
      message_id: assistantMessageId,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
      metadata: { is_streaming: true },
    };
    let persistedUserMessage = null;
    let streamedSession = null;
    let sawDelta = false;

    setIsLoading(true);
    clearFeedback();
    nextThreadScrollRef.current = "bottom";
    setStreamingMessageId(assistantMessageId);
    setMessages((current) => [...current, pendingUserMessage, pendingAssistantMessage]);
    setPrompt("");

    try {
      await streamChatApi()(requestPayload, {
        onSession: async (session) => {
          streamedSession = session;
          setActiveSession(session);
          setSessions((current) => mergeSession(current, session));
        },
        onUserMessage: async (message) => {
          persistedUserMessage = message;
          setMessages((current) =>
            current.map((item) =>
              item.message_id === pendingUserMessage.message_id ? message : item,
            ),
          );
        },
        onTextDelta: async (text) => {
          if (!sawDelta) {
            sawDelta = true;
            setIsLoading(false);
          }
          setMessages((current) =>
            current.map((item) =>
              item.message_id === assistantMessageId
                ? {
                    ...item,
                    content: `${item.content || ""}${text}`,
                    metadata: {
                      ...(item.metadata || {}),
                      is_streaming: true,
                    },
                  }
                : item,
            ),
          );
        },
        onComplete: async (payload) => {
          const session = payload.session;
          setActiveSession(session);
          setSessions((current) => mergeSession(current, session));
          setMessages((current) =>
            current.map((item) =>
              item.message_id === assistantMessageId
                ? {
                    ...payload.message,
                    content: payload.message.content || item.content,
                  }
                : item,
            ),
          );
        },
      });
    } catch (caught) {
      const isAuthError =
        !requestPayload._ssoRetried &&
        classifyErrorCategory(caught?.message || "") === "auth" &&
        typeof window.assistantApi?.ssoLogin === "function";

      if (isAuthError) {
        setMessages((current) =>
          current.filter((item) => {
            if (item.message_id === assistantMessageId) {
              return false;
            }
            if (!persistedUserMessage && item.message_id === pendingUserMessage.message_id) {
              return false;
            }
            return true;
          }),
        );
        setIsLoading(false);
        setStreamingMessageId(null);
        setNotice("AWS session expired. Signing in\u2026");
        try {
          await window.assistantApi.ssoLogin();
          setNotice("AWS session refreshed. Retrying\u2026");
          await sendPrompt({ ...requestPayload, _ssoRetried: true });
          return;
        } catch (_loginError) {
          // SSO login failed — fall through to show the original error
        }
      }

      setMessages((current) =>
        current.filter((item) => {
          if (item.message_id === assistantMessageId) {
            return false;
          }
          if (!persistedUserMessage && item.message_id === pendingUserMessage.message_id) {
            return false;
          }
          return true;
        }),
      );
      if (!persistedUserMessage || !streamedSession) {
        setPrompt(trimmedPrompt);
      }
      setErrorState(
        buildErrorState(caught?.message, {
          context: "prompt",
          retry:
            !persistedUserMessage && !streamedSession
              ? { action: "prompt", label: "Retry request", payload: requestPayload }
              : { action: "restore_prompt", label: "Use prompt again", prompt: trimmedPrompt },
        }),
      );
    } finally {
      setIsLoading(false);
      setStreamingMessageId(null);
    }
  }

  function toggleSidebar() {
    setIsSidebarOpen((current) => !current);
  }

  async function submitRenameSession(event) {
    event.preventDefault();
    if (!activeSession) {
      return;
    }

    const nextTitle = renameTitle.trim();
    if (!nextTitle) {
      setErrorState(buildErrorState("Session title cannot be empty.", { context: "session_rename" }));
      return;
    }

    clearFeedback();
    try {
      const payload = await api().renameSession(activeSession.session_id, { title: nextTitle });
      setActiveSession(payload.session);
      setSessions((current) => replaceSession(current, payload.session));
      setIsRenamingSession(false);
    } catch (caught) {
      setErrorState(buildErrorState(caught?.message, { context: "session_rename" }));
    }
  }

  async function deleteActiveSession() {
    if (!activeSession) {
      return;
    }
    if (!window.confirm(`Delete "${activeSession.title}"?`)) {
      return;
    }

    setStreamingMessageId(null);
    clearFeedback();
    try {
      await api().deleteSession(activeSession.session_id);
      const remainingSessions = sessions.filter(
        (item) => item.session_id !== activeSession.session_id,
      );
      setSessions(remainingSessions);
      setIsRenamingSession(false);
      if (remainingSessions.length > 0) {
        await loadSession(remainingSessions[0].session_id);
      } else {
        setActiveSession(null);
        setMessages([]);
      }
    } catch (caught) {
      setErrorState(buildErrorState(caught?.message, { context: "session_delete" }));
    }
  }

  async function exportActiveSession(format) {
    if (!activeSession) {
      return;
    }

    clearFeedback();
    try {
      const result = await api().saveTranscript({
        format,
        suggestedName: buildTranscriptFilename(activeSession, format),
        content: buildTranscriptContent(activeSession, messages, format),
      });
      if (!result?.canceled) {
        setNotice(`Exported ${format === "json" ? "JSON" : "Markdown"} transcript.`);
      }
    } catch (caught) {
      setErrorState(buildErrorState(caught?.message, { context: "export" }));
    }
  }

  async function copyMessageContent(message) {
    try {
      await writeToClipboard(message.content || "");
      setNotice(message.role === "assistant" ? "Copied assistant message." : "Copied prompt.");
      setErrorState(null);
    } catch (caught) {
      setErrorState(buildErrorState(caught?.message, { context: "clipboard" }));
    }
  }

  async function copyCodeBlock(code) {
    try {
      await writeToClipboard(code);
      setNotice("Copied code block.");
      setErrorState(null);
    } catch (caught) {
      setErrorState(buildErrorState(caught?.message, { context: "clipboard" }));
    }
  }

  async function regenerateLatestReply() {
    if (!latestAssistantPair || isBusy) {
      return;
    }

    const { userMessage } = latestAssistantPair;
    const userMetadata = userMessage.metadata || {};

    setNotice("Regenerating the latest reply from the last prompt.");
    await sendPrompt({
      session_id: activeSession?.session_id,
      prompt: userMessage.content,
      system_prompt:
        typeof userMetadata.system_prompt === "string" && userMetadata.system_prompt.trim()
          ? userMetadata.system_prompt
          : systemPrompt || undefined,
      temperature: Number(temperature),
      max_tokens: Number(maxTokens),
    });
  }

  async function retryFromError() {
    const retry = errorState?.retry;
    if (!retry) {
      return;
    }

    if (retry.action === "initialize") {
      await initializeApp();
      return;
    }

    if (retry.action === "session" && retry.sessionId) {
      await loadSession(retry.sessionId);
      return;
    }

    if (retry.action === "prompt" && retry.payload) {
      await sendPrompt(retry.payload);
      return;
    }

    if (retry.action === "restore_prompt" && retry.prompt) {
      setPrompt(retry.prompt);
      setErrorState(null);
    }
  }

  function startSidebarResize(event) {
    if (isCompactLayout) {
      return;
    }

    const startX = event.clientX;
    const startWidth = sidebarWidth;

    function handlePointerMove(moveEvent) {
      const delta = moveEvent.clientX - startX;
      setSidebarWidth(clampSidebarWidth(startWidth + delta));
    }

    function stopResizing() {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", stopResizing);
      resizeCleanupRef.current = () => {};
    }

    resizeCleanupRef.current = stopResizing;
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopResizing);
  }

  return {
    health,
    sessions,
    filteredSessions,
    activeSession,
    messages,
    prompt,
    setPrompt,
    systemPrompt,
    setSystemPrompt,
    temperature,
    setTemperature,
    maxTokens,
    setMaxTokens,
    errorState,
    setErrorState,
    notice,
    isLoading,
    isLoadingSessions,
    isLoadingHistory,
    isRenamingSession,
    setIsRenamingSession,
    renameTitle,
    setRenameTitle,
    sessionFilter,
    setSessionFilter,
    streamingMessageId,
    isCompactLayout,
    isSidebarOpen,
    setIsSidebarOpen,
    isControlsOpen,
    setIsControlsOpen,
    sidebarWidth,
    isBusy,
    latestAssistantPair,
    threadRef,
    createSession,
    loadSession,
    submitPrompt,
    toggleSidebar,
    submitRenameSession,
    deleteActiveSession,
    exportActiveSession,
    copyMessageContent,
    copyCodeBlock,
    regenerateLatestReply,
    retryFromError,
    startSidebarResize,
  };
}
