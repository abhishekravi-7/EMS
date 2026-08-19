import React, { useEffect, useId, useRef, useState, useCallback, useMemo } from "react";
import { API_BASE_URL } from "@/services/config/env";
import { useChatbot } from "@/shared/context/ChatbotContext";
import "./FloatingChatbot.css";

type Role = "user" | "assistant" | "system";

interface ComparisonTableSpec {
  caption?: string;
  headers: string[];
  rows: string[][];
}

interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  rationale?: string[];
  comparisonTable?: ComparisonTableSpec | null;
  details?: Record<string, unknown> | null;
  createdAt: string;
}

type ContentBlock =
  | { kind: "paragraph"; text: string }
  | { kind: "heading"; text: string; level: number }
  | { kind: "list"; items: string[]; ordered: boolean }
  | { kind: "table"; table: ComparisonTableSpec };

// Props are no longer needed
// interface Props {
//   repoUrl?: string | null;
//   strategyContext?: StrategyPageContext | null;
// }

// New type for source references returned by the backend
interface SourceReference {
  title: string;
  url: string;
  excerpt?: string;
}

const normalizeComparisonTable = (value: unknown): ComparisonTableSpec | null => {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  const headers = Array.isArray(candidate.headers)
    ? candidate.headers.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
  const rows = Array.isArray(candidate.rows)
    ? candidate.rows
        .map((row: unknown) =>
          Array.isArray(row)
            ? row.filter((item): item is string => typeof item === "string").map((item) => item.trim())
            : []
        )
        .filter((row) => row.length > 0)
    : [];
  if (headers.length < 2 || rows.length === 0) return null;
  return {
    caption: typeof candidate.caption === "string" ? candidate.caption : undefined,
    headers,
    rows,
  };
};

const isMarkdownTableDivider = (line: string) =>
  /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);

const splitMarkdownTableRow = (line: string) =>
  line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((part) => part.trim());

const renderInlineMarkdown = (text: string) => {
  const segments = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return segments.map((segment, segmentIndex) => {
    if (segment.startsWith("**") && segment.endsWith("**") && segment.length > 4) {
      return (
        <strong key={`${segmentIndex}_${segment}`} className="strategy-chat-inline-strong">
          {segment.slice(2, -2)}
        </strong>
      );
    }
    if (segment.startsWith("`") && segment.endsWith("`") && segment.length > 2) {
      return (
        <code key={`${segmentIndex}_${segment}`} className="strategy-chat-inline-code">
          {segment.slice(1, -1)}
        </code>
      );
    }
    return <React.Fragment key={`${segmentIndex}_${segment}`}>{segment}</React.Fragment>;
  });
};

const parseMarkdownContentBlocks = (content: string): ContentBlock[] => {
  const lines = (content || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: ContentBlock[] = [];
  const paragraphLines: string[] = [];
  let index = 0;

  const flushParagraph = () => {
    const text = paragraphLines.join("\n").trim();
    if (text) {
      blocks.push({ kind: "paragraph", text });
    }
    paragraphLines.length = 0;
  };

  while (index < lines.length) {
    const line = lines[index] || "";

    // Headings
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      blocks.push({
        kind: "heading",
        level: headingMatch[1].length,
        text: headingMatch[2].trim(),
      });
      index += 1;
      continue;
    }

    // Lists (simplified)
    const listMatch = line.match(/^(\s*)([-*+]|\d+\.)\s+(.+)$/);
    if (listMatch) {
      flushParagraph();
      const items: string[] = [];
      const isOrdered = /^\d+\./.test(listMatch[2]);

      let listIndex = index;
      while (listIndex < lines.length) {
        const itemLine = lines[listIndex] || "";
        const itemMatch = itemLine.match(/^(\s*)([-*+]|\d+\.)\s+(.+)$/);
        if (!itemMatch) break;
        items.push(itemMatch[3].trim());
        listIndex += 1;
      }

      blocks.push({ kind: "list", items, ordered: isOrdered });
      index = listIndex;
      continue;
    }

    // Tables
    const nextLine = lines[index + 1] || "";
    if (line.includes("|") && isMarkdownTableDivider(nextLine)) {
      flushParagraph();
      const headers = splitMarkdownTableRow(line);
      const rows: string[][] = [];
      index += 2;

      while (index < lines.length) {
        const rowLine = lines[index] || "";
        if (!rowLine.trim() || !rowLine.includes("|")) {
          break;
        }
        const cells = splitMarkdownTableRow(rowLine);
        if (cells.length > 1) {
          rows.push(cells);
        }
        index += 1;
      }

      if (headers.length > 1 && rows.length > 0) {
        const columnCount = Math.max(headers.length, ...rows.map((row) => row.length));
        blocks.push({
          kind: "table",
          table: {
            headers: headers.slice(0, columnCount),
            rows: rows.map((row) =>
              Array.from({ length: columnCount }, (_, colIndex) => row[colIndex] || "")
            ),
          },
        });
      }
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
    } else {
      paragraphLines.push(line);
    }
    index += 1;
  }

  flushParagraph();
  return blocks;
};

/**
 * Memoized block component to prevent unnecessary re-renders of stable markdown parts.
 */
const MarkdownBlock = React.memo(({ block, messageId, index }: { block: ContentBlock; messageId: string; index: number }) => {
  if (block.kind === "heading") {
    const headingTag = `h${Math.min(block.level, 6)}` as keyof React.JSX.IntrinsicElements;
    return React.createElement(
      headingTag,
      { key: `${messageId}_h_${index}`, className: "strategy-chat-heading" },
      renderInlineMarkdown(block.text)
    );
  }

  if (block.kind === "list") {
    const listTag = block.ordered ? "ol" : "ul";
    return React.createElement(
      listTag,
      { key: `${messageId}_l_${index}`, className: "strategy-chat-list" },
      block.items.map((item: string, i: number) =>
        React.createElement(
          "li",
          { key: `${messageId}_l_${index}_${i}`, className: "strategy-chat-list-item" },
          renderInlineMarkdown(item)
        )
      )
    );
  }

  if (block.kind === "paragraph") {
    return (
      <div key={`${messageId}_p_${index}`} className="strategy-chat-rich-text">
        {renderInlineMarkdown(block.text)}
      </div>
    );
  }

  const blockColumnCount = Math.max(
    block.table.headers.length,
      ...block.table.rows.map((row: string[]) => row.length)
  );

  return (
    <div key={`${messageId}_t_${index}`} className="strategy-chat-table-wrap">
      <table className="strategy-chat-table">
        <thead>
          <tr key={`${messageId}_tr_h_${index}`}>
            {Array.from({ length: blockColumnCount }, (_, headerIndex) => (
              <th key={`${messageId}_th_${index}_${headerIndex}`}>
                {renderInlineMarkdown(block.table.headers[headerIndex] || "")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
            {block.table.rows.map((row: string[], rowIndex: number) => (
              <tr key={`${messageId}_tr_${index}_${rowIndex}`}>
              {Array.from({ length: blockColumnCount }, (_, colIndex: number) => (
                <td key={`${messageId}_td_${index}_${rowIndex}_${colIndex}`}>
                  {renderInlineMarkdown(row[colIndex] || "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});

const AssistantMessageContent = React.memo(({ message, sources }: { message: ChatMessage, sources: SourceReference[] }) => {
  const blocks = useMemo(() => parseMarkdownContentBlocks(message.content || ""), [message.content]);

  const comparisonTable = useMemo(() => normalizeComparisonTable(message.details?.comparison_table), [message.details]);
  const hasMarkdownTable = blocks.some((block) => block.kind === "table");

  const elements = blocks.map((block, index) => (
    <MarkdownBlock key={`${message.id}_block_${index}`} block={block} messageId={message.id} index={index} />
  ));

  if (!hasMarkdownTable && comparisonTable) {
    const columnCount = Math.max(
      comparisonTable.headers.length,
      ...comparisonTable.rows.map((row: string[]) => row.length)
    );
    elements.push(
      <div key={`${message.id}_comparison`} className="strategy-chat-table-wrap">
        {comparisonTable.caption && (
          <div className="strategy-chat-table-caption">{comparisonTable.caption}</div>
        )}
        <table className="strategy-chat-table">
          <thead>
            <tr>
              {Array.from({ length: columnCount }, (_, headerIndex) => (
                <th key={`${message.id}_c_th_${headerIndex}`}>
                  {comparisonTable?.headers[headerIndex] || ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {comparisonTable.rows.map((row: string[], rowIndex: number) => (
              <tr key={`${message.id}_c_tr_${rowIndex}`}>
                {Array.from({ length: columnCount }, (_, colIndex: number) => (
                  <td key={`${message.id}_c_td_${rowIndex}_${colIndex}`}>
                    {row[colIndex] || ""}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (elements.length > 0 || sources.length > 0) {
    return (
      <>
        {elements}
        {sources.length > 0 && (
          <div className="strategy-chat-sources">
            <h4>Sources</h4>
            <ul>
              {sources.map((s, i) => (
                <li key={i} className="strategy-chat-source-item">
                  <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a>
                  {s.excerpt && <p className="source-excerpt">{s.excerpt}</p>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </>
    );
  }

  return <div key={`${message.id}_empty`}>{message.content || "..."}</div>;
});

const STORAGE_KEY_PREFIX = "javaapex_strategy_chat_v1";

function makeStorageKey(repoUrl?: string | null) {
  const repoId = repoUrl ? repoUrl.replace(/[^a-z0-9-_]/gi, "_") : "global";
  return `${STORAGE_KEY_PREFIX}_${repoId}`;
}

export default function FloatingChatbot() {
  const { repoUrl, strategyContext } = useChatbot();
  const assistantName = "JavaApex Assistant";

  const AssistantLogo: React.FC<{ size?: number; className?: string }> = ({ size = 46, className }) => {
    const idSuffix = useId().replace(/:/g, "");
    const orbId = `assistant_orb_${idSuffix}`;
    const glowId = `assistant_glow_${idSuffix}`;
    const sparkleId = `assistant_sparkle_${idSuffix}`;

    return (
      <svg
        className={className}
        width={size}
        height={size}
        viewBox="0 0 96 96"
        fill="none"
        aria-hidden
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <radialGradient id={orbId} cx="0.28" cy="0.22" r="0.92">
            <stop offset="0" stopColor="#FF8BE8" />
            <stop offset="0.34" stopColor="#C66BFF" />
            <stop offset="0.68" stopColor="#6484FF" />
            <stop offset="1" stopColor="#2A86FF" />
          </radialGradient>
          <radialGradient id={glowId} cx="0.34" cy="0.28" r="0.8">
            <stop offset="0" stopColor="#FFFFFF" stopOpacity="1" />
            <stop offset="0.38" stopColor="#FFFFFF" stopOpacity="0.52" />
            <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={sparkleId} x1="28" y1="28" x2="68" y2="68" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#FFFFFF" />
            <stop offset="1" stopColor="#FFFFFF" stopOpacity="0.92" />
          </linearGradient>
        </defs>
        <circle cx="48" cy="48" r="39" fill={`url(#${orbId})`} />
        <circle cx="48" cy="48" r="31" fill={`url(#${glowId})`} opacity="0.95" />
        <circle cx="38" cy="32" r="11" fill="#FFFFFF" opacity="0.18" />
        <circle cx="61" cy="62" r="9" fill="#FFFFFF" opacity="0.1" />
        <path
          d="M48 25.5c1.2 3.2 2.7 5.4 4.8 6.6 2.1 1.2 4.4 1.8 7 1.8-2.6 0-4.9.6-7 1.8-2.1 1.2-3.6 3.4-4.8 6.6-1.2-3.2-2.7-5.4-4.8-6.6-2.1-1.2-4.4-1.8-7-1.8 2.6 0 4.9-.6 7-1.8 2.1-1.2 3.6-3.4 4.8-6.6Z"
          fill={`url(#${sparkleId})`}
          opacity="0.98"
        />
        <path
          d="M34.5 40.5c.9 2.3 1.9 3.9 3.4 4.8 1.5.8 3.1 1.2 5 1.2-1.9 0-3.5.4-5 1.2-1.5.8-2.5 2.4-3.4 4.8-.9-2.3-1.9-3.9-3.4-4.8-1.5-.8-3.1-1.2-5-1.2 1.9 0 3.5-.4 5-1.2 1.5-.8 2.5-2.4 3.4-4.8Z"
          fill={`url(#${sparkleId})`}
          opacity="0.95"
        />
        <path
          d="M52.2 46.2c.5 1.2 1 2 1.8 2.5.8.4 1.7.6 2.7.6-1 0-1.9.2-2.7.6-.8.5-1.3 1.3-1.8 2.5-.5-1.2-1-2-1.8-2.5-.8-.4-1.7-.6-2.7-.6 1 0 1.9-.2 2.7-.6.8-.5 1.3-1.3 1.8-2.5Z"
          fill={`url(#${sparkleId})`}
          opacity="1"
        />
      </svg>
    );
  };

  // Rotating descriptive messages for the answer phase
  const AnimatedRetrieving: React.FC = () => {
    const messages = [
      "Reading strategy page",
      "Using page context",
      "Preparing answer",
    ];
    const [idx, setIdx] = useState(0);
    useEffect(() => {
      const t = setInterval(() => setIdx((i) => (i + 1) % messages.length), 800);
      return () => clearInterval(t);
    }, [messages.length]);
    return (
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
          <circle cx="12" cy="12" r="10" stroke="#93c5fd" strokeWidth="2" opacity="0.18" />
          <path d="M22 12a10 10 0 0 0-10-10" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <span style={{ color: "#475569" }}>{messages[idx]}</span>
      </span>
    );
  };
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [hovered, setHovered] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const abortedByUserRef = useRef(false);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [isAutoScrolling, setIsAutoScrolling] = useState(true);

  // Map of assistant message ID to its source references
  const [sourcesMap, setSourcesMap] = useState<Record<string, SourceReference[]>>({});

  const storageKey = makeStorageKey(repoUrl);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) setMessages(JSON.parse(raw));
    } catch {
      // ignore
    }
  }, [storageKey]);

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(messages));
    } catch {
      // ignore
    }
  }, [messages, storageKey]);

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  const handleScroll = useCallback(() => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;

    // We are at the bottom if we're within 50px of the actual bottom
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;

    setIsAutoScrolling((prev) => {
        if (prev === isAtBottom) return prev;
        return isAtBottom;
    });

    setShowScrollButton((prev) => {
        const shouldShow = !isAtBottom;
        if (prev === shouldShow) return prev;
        return shouldShow;
    });
  }, []);

  useEffect(() => {
    if (open && isAutoScrolling) {
      scrollToBottom(sending ? "auto" : "smooth");
    }
  }, [open, messages, sending, isAutoScrolling]);

  useEffect(() => {
    if (open) {
        // initial scroll when opened
        setTimeout(() => scrollToBottom("auto"), 100);
    }
  }, [open]);

  // persist lastSeenAt when panel opens or messages are read
  

  const addMessage = (msg: ChatMessage) => setMessages((m) => [...m, msg]);

  const handleSend = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    if (!text) return;
    const userMsg: ChatMessage = {
      id: `u_${Date.now()}`,
      role: "user",
      content: text,
      createdAt: new Date().toISOString(),
    };
    addMessage(userMsg);
    setInput("");
    setOpen(true);
    setSending(true);

    const assistantPlaceholder: ChatMessage = {
      id: `a_${Date.now()}`,
      role: "assistant",
      content: "",
      createdAt: new Date().toISOString(),
    };
    addMessage(assistantPlaceholder);

    try {
      // Use POST streaming endpoint that emits SSE-like events
      const url = `${API_BASE_URL}/strategy/query/stream`;
      const controller = new AbortController();
      abortControllerRef.current = controller;
      abortedByUserRef.current = false;

      // Filter out technical phase messages and limit to last 3 rounds (6 messages)
      const chatHistory = messages
        .filter((m) => {
          const content = (m.content || "").toString();
          const phaseStates = ["Reading strategy page", "Using page context", "Preparing answer"];
          return !phaseStates.includes(content) && content.trim().length > 0;
        })
        .slice(-6)
        .map((m) => ({
          role: m.role,
          content: m.content,
        }));

      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          repo_url: repoUrl || undefined,
          question: text,
          strategy_context: strategyContext || undefined,
          history: chatHistory,
        }),
        signal: controller.signal,
      });

      if (!resp.ok || !resp.body) {
        // fallback to non-streaming if available
        throw new Error(`Streaming request failed: ${resp.status} ${resp.statusText}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      const flushEvent = (raw: string) => {
        const lines = raw.split("\n");
        let event: string | null = null;
        const dataLines: string[] = [];
        for (const ln of lines) {
          if (ln.startsWith("event:")) {
            event = ln.replace(/^event:\s*/, "").trim();
          } else if (ln.startsWith("data:")) {
            dataLines.push(ln.replace(/^data:\s*/, ""));
          }
        }
        if (dataLines.length === 0) return;
        try {
          const payload = JSON.parse(dataLines.join("\n"));
          if (event === "phase") {
            const msg = payload?.message || payload?.phase || "...";
            setMessages((prev) => prev.map((m) => (m.id === assistantPlaceholder.id ? { ...m, content: msg } : m)));
          } else if (event === "references") {
            const sources = payload?.sources || [];
            if (sources.length) {
              setSourcesMap((prev) => ({ ...prev, [assistantPlaceholder.id]: sources }));
            }
          } else if (event === "chunk") {
            const chunk = payload?.chunk || payload?.text || "";
            if (chunk) {
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantPlaceholder.id) return m;
                  const phaseStates = ["Reading strategy page", "Using page context", "Preparing answer"];
                  const current = (m.content || "").toString();
                  const base = phaseStates.includes(current) ? "" : current;
                  return { ...m, content: `${base}${chunk}`.replace(/\s{2,}/g, " ") };
                })
              );
            }
          } else if (event === "final") {
            const parsed = payload?.parsed || {};
            const details = payload?.details || {};
            const answer = parsed.answer || payload?.parsed?.answer || payload?.answer || "";
            const rationale = parsed.rationale || parsed.reasons || [];
            const comparisonTable = normalizeComparisonTable(details?.comparison_table || parsed?.comparison_table);
            // Extract source references from the payload
            const sources: SourceReference[] = payload?.sources || [];
            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== assistantPlaceholder.id) return m;
                // Preserve streamed content if it's longer and non-empty
                const phaseStates = ["Reading strategy page", "Using page context", "Preparing answer"];
                const current = (m.content || "").toString();
                const isPhase = phaseStates.includes(current);
                const finalContent = answer
                  ? ((!isPhase && current.length > answer.length) ? current : answer)
                  : (isPhase ? "..." : current || "...");
                return {
                  ...m,
                  content: finalContent,
                  rationale,
                  comparisonTable,
                  details: {
                    ...(details as Record<string, unknown>),
                    parsed,
                    comparison_table: comparisonTable,
                  },
                };
              })
            );
            // Store sources associated with this assistant message
            if (sources.length) {
              setSourcesMap((prev) => ({ ...prev, [assistantPlaceholder.id]: sources }));
            }
          } else if (event === "error") {
            const errMsg = payload?.message || JSON.stringify(payload);
            // Map known technical errors to user-friendly messages
            let displayMsg = errMsg;
            if (
              errMsg.includes("Local Ollama server could not be reached") ||
              errMsg.includes("OLLAMA_UNAVAILABLE") ||
              errMsg.includes("ollama serve")
            ) {
              displayMsg =
                "⚠️ The local AI service is unavailable. Please start Ollama: run `ollama serve` in a terminal, then try again.";
            } else if (errMsg.includes("OLLAMA_MODEL_NOT_FOUND") || errMsg.includes("ollama pull")) {
              displayMsg = `⚠️ The required AI model is not installed. ${errMsg}`;
            } else if (errMsg.includes("OLLAMA_TIMEOUT")) {
              displayMsg = "⚠️ The AI model took too long to respond. It may still be loading — please wait and try again.";
            } else if (errMsg.includes("All configured LLM providers failed")) {
              displayMsg =
                "⚠️ Both the primary and fallback AI services are unavailable. Please check your network connection or start Ollama (`ollama serve`).";
            } else if (
              errMsg.includes("CHAT_LLM_NOT_CONFIGURED") ||
              errMsg.includes("No chat model is available")
            ) {
              displayMsg =
                "⚠️ No AI model is configured. Please set LLM_2 in the backend .env or run a local Ollama server.";
            }
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantPlaceholder.id ? { ...m, content: `Error: ${displayMsg}` } : m
              )
            );
          }
        } catch {
          // ignore parse errors
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx = buffer.indexOf("\n\n");
        while (idx !== -1) {
          const raw = buffer.slice(0, idx).trim();
          if (raw) flushEvent(raw);
          buffer = buffer.slice(idx + 2);
          idx = buffer.indexOf("\n\n");
        }
      }

      // flush remaining
      if (buffer.trim()) flushEvent(buffer.trim());
    } catch (err) {
      // handle abort vs other errors
      const aborted = abortedByUserRef.current || (err instanceof Error && err.name === "AbortError");
      if (aborted) {
        const stopText = `Stopped by user.`;
        setMessages((prev) => prev.map((m) => (m.id === assistantPlaceholder.id ? { ...m, content: stopText } : m)));
      } else {
        const errorText = `Error: ${err instanceof Error ? err.message : String(err)}`;
        setMessages((prev) => prev.map((m) => (m.id === assistantPlaceholder.id ? { ...m, content: errorText } : m)));
      }
    } finally {
      setSending(false);
      try {
        abortControllerRef.current = null;
        abortedByUserRef.current = false;
      } catch { /* ignore */ }
    }
  };

  const handleStop = () => {
    const ctrl = abortControllerRef.current;
    if (ctrl) {
      abortedByUserRef.current = true;
      try {
        ctrl.abort();
      } catch { /* ignore */ }
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      // Press Enter to send, Shift+Enter for newline
      e.preventDefault();
      void handleSend();
    }
  };

  const clearHistory = () => {
    setMessages([]);
    try {
      localStorage.removeItem(storageKey);
    } catch { /* ignore */ }
  };

  const latestAssistantMessage = [...messages].reverse().find((message) => message.role === "assistant");
  const showingTypingState =
    sending ||
    ["Reading strategy page", "Using page context", "Preparing answer"].includes(
      (latestAssistantMessage?.content || "").toString()
    );

  return (
    <div>
      {/* Floating button */}
      <button
          onClick={() => setOpen((v) => !v)}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          aria-label="Open strategy chat"
          title="Open JavaApex Assistant"
          style={{
            position: "fixed",
            right: 20,
            bottom: 20,
            width: 60,
            height: 60,
            borderRadius: 30,
            background: "transparent",
            border: "none",
            boxShadow: hovered ? "0 10px 30px rgba(2,6,23,0.28)" : "0 6px 20px rgba(2,6,23,0.2)",
            cursor: "pointer",
            zIndex: 1100,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "transform 160ms ease, box-shadow 160ms ease",
            transform: hovered ? "scale(1.06) rotate(-6deg)" : "none",
            padding: 0,
          }}
        >
          <AssistantLogo size={34} />
        </button>

      {/* Chat panel */}
      <div
          ref={panelRef}
          className="strategy-chat-panel"
          style={{
            position: "fixed",
            right: 20,
            left: "auto",
            bottom: 100,
            top: "auto",
            width: 600,
            height: 700,
            maxWidth: "calc(100vw - 40px)",
            maxHeight: "calc(100vh - 120px)",
            zIndex: 1100,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            transition: "opacity 300ms ease, transform 300ms cubic-bezier(0.175, 0.885, 0.32, 1.275), visibility 300ms",
            transformOrigin: "bottom right",
            ...(!open ? {
                opacity: 0,
                transform: "scale(0.85) translateY(20px)",
                visibility: "hidden",
                pointerEvents: "none"
            } : {
                opacity: 1,
                transform: "scale(1) translateY(0)",
                visibility: "visible",
                pointerEvents: "auto"
            })
          }}
        >
          <div className="strategy-chat-header">
            <div className="strategy-chat-brand">
              <div className="strategy-chat-avatar" aria-hidden>
                <AssistantLogo size={54} className="strategy-chat-avatar-image" />
              </div>
              <div style={{ minWidth: 0 }}>
                <div className="strategy-chat-title">{assistantName}</div>
              </div>
            </div>
            <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
              <button onClick={clearHistory} title="Clear history" style={{ border: "none", background: "transparent", cursor: "pointer", color: "#6b7280", padding: 6 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M3 6h18" stroke="#6b7280" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6" stroke="#6b7280" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M10 11v6" stroke="#6b7280" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M14 11v6" stroke="#6b7280" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </button>
              <button onClick={() => setOpen(false)} title="Close" style={{ border: "none", background: "transparent", cursor: "pointer", color: "#6b7280", padding: 6 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="#6b7280" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </button>
            </div>
          </div>

          <div className="strategy-chat-body" ref={scrollContainerRef} onScroll={handleScroll}>
            <div className="strategy-chat-canvas">
              {showingTypingState && (
                <div className="strategy-chat-status">
                  <span className="strategy-chat-status-spinner" aria-hidden>
                    <span />
                  </span>
                  <span>Analyzing data, please wait...</span>
                </div>
              )}

              {messages.length === 0 ? (
                <div className="strategy-chat-empty-state" aria-live="polite">
                  <div className="strategy-chat-empty-state-badge">Chat ready</div>
                </div>
              ) : (
                <div className="strategy-chat-messages">
                  {messages.map((m) => (
                    <div
                      key={m.id}
                      className={`strategy-chat-row ${m.role === "user" ? "strategy-chat-row-user" : "strategy-chat-row-assistant"}`}
                    >
                      <div className="strategy-chat-message-stack">
                        <div
                          className={`strategy-chat-bubble ${
                            m.role === "user" ? "strategy-chat-bubble-user" : "strategy-chat-bubble-assistant"
                          }`}
                        >
                          {m.role === "assistant" &&
                          ["Reading strategy page", "Using page context", "Preparing answer"].includes((m.content || "").toString()) ? (
                            <AnimatedRetrieving />
                          ) : (
                            m.role === "assistant" ? (
                              <AssistantMessageContent
                                message={m}
                                sources={sourcesMap[m.id] ?? []}
                              />
                            ) : m.content || ""
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
            {showScrollButton && (
              <button
                className="strategy-chat-scroll-latest"
                onClick={() => {
                  setIsAutoScrolling(true);
                  scrollToBottom("smooth");
                }}
                title="Scroll to latest"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                  <path d="M7 13l5 5 5-5M7 6l5 5 5-5" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span>New messages</span>
              </button>
            )}
          </div>

          <div className="strategy-chat-composer-shell">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (sending) {
                  handleStop();
                } else {
                  void handleSend();
                }
              }}
              className="strategy-chat-composer"
            >
              <textarea
                ref={textareaRef}
                placeholder="Ask your queries"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={2}
                className="strategy-chat-input"
              />
              <button
                type="submit"
                className={`strategy-chat-send ${sending ? "strategy-chat-send-stop" : ""}`}
                aria-label={sending ? "Stop generation" : "Send question"}
                title={sending ? "Stop generation" : "Send question"}
              >
                {sending ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <rect x="7" y="7" width="10" height="10" rx="2.2" fill="currentColor" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <path d="M5 12h10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                    <path d="m12 5 7 7-7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </button>
            </form>
          </div>
        </div>
    </div>
  );
}
