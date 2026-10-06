import React, { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useChatbot } from "@/shared/context/ChatbotContext";
import { sendMessage, determineThinkingState } from "@/shared/services/chatService";
import { getUserSettings } from "@/features/admin/services/adminService";
import type {
  ChatMessage,
  ContentBlock,
  SourceReference,
  ComparisonTableSpec,
} from "@/shared/types/chat";
import "./FloatingChatbot.css";

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
    const line = lines[index] ?? "";

    // Fenced Code Block
    if (line.trim().startsWith("```")) {
      flushParagraph();
      const language = line.trim().slice(3).trim();
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length) {
        const codeLine = lines[index] ?? "";
        if (codeLine.trim().startsWith("```")) {
          index += 1;
          break;
        }
        codeLines.push(codeLine);
        index += 1;
      }
      blocks.push({
        kind: "code",
        code: codeLines.join("\n"),
        language: language || undefined,
      });
      continue;
    }

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

    // Lists
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
 * Fenced code block with language indicator and copy-to-clipboard functionality.
 */
const CodeBlock: React.FC<{ code: string; language?: string }> = ({ code, language }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    try {
      navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <div className="strategy-chat-code-wrapper">
      <div className="strategy-chat-code-header">
        <span className="strategy-chat-code-lang">{(language || "code").toUpperCase()}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="strategy-chat-code-copy-btn"
          aria-label="Copy code"
          title="Copy code"
        >
          {copied ? (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              <span>Copied!</span>
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="strategy-chat-code-pre">
        <code>{code}</code>
      </pre>
    </div>
  );
};

/**
 * Memoized block component for markdown elements.
 */
const MarkdownBlock = React.memo(({ block, messageId, index }: { block: ContentBlock; messageId: string; index: number }) => {
  if (block.kind === "code") {
    return (
      <CodeBlock
        key={`${messageId}_c_${index}`}
        code={block.code}
        language={block.language}
      />
    );
  }

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

const isThinkingContent = (content: string): boolean => {
  const c = (content || "").trim();
  const phases = [
    "Reading strategy page",
    "Using page context",
    "Preparing answer",
    "Preparing answer...",
    "Analyzing your application...",
    "Analyzing repository context...",
    "Analyzing testcase results...",
    "Analyzing data, please wait...",
  ];
  return phases.includes(c) || (c.endsWith("...") && c.length < 40);
};

const AssistantMessageContent = React.memo(({ message, sources }: { message: ChatMessage; sources: SourceReference[] }) => {
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
                  <a href={s.url} target="_blank" rel="noopener noreferrer">
                    {s.title}
                  </a>
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

interface DynamicRobotHeroProps {
  activeTheme?: "blue" | "purple" | "green" | "orange";
}

const DynamicRobotHero: React.FC<DynamicRobotHeroProps> = ({ activeTheme = "blue" }) => {
  const [tilt, setTilt] = useState({ x: 0, y: 0, active: false });
  const [bouncing, setBouncing] = useState(false);
  const [showSpeech, setShowSpeech] = useState(false);
  const speechTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    const rotateX = -(y / (rect.height / 2)) * 12;
    const rotateY = (x / (rect.width / 2)) * 12;
    setTilt({ x: rotateX, y: rotateY, active: true });
  };

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0, active: false });
  };

  const handleClick = () => {
    setBouncing(true);
    setShowSpeech(true);
    if (speechTimerRef.current) clearTimeout(speechTimerRef.current);
    speechTimerRef.current = setTimeout(() => {
      setShowSpeech(false);
      setBouncing(false);
    }, 2000);
  };

  useEffect(() => {
    return () => {
      if (speechTimerRef.current) clearTimeout(speechTimerRef.current);
    };
  }, []);

  return (
    <div
      className="strategy-chat-hero-image-container"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
      title="Click to interact with JavaApex Assistant!"
    >
      <div className={`strategy-robot-aura strategy-robot-aura-${activeTheme}`} />

      <svg
        className="strategy-robot-orbits"
        viewBox="0 0 200 140"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden
      >
        <ellipse
          cx="100"
          cy="70"
          rx="86"
          ry="32"
          stroke="url(#orbitGrad1)"
          strokeWidth="1.2"
          strokeDasharray="4 6"
          className="strategy-robot-orbit-ring"
        />
        <ellipse
          cx="100"
          cy="70"
          rx="70"
          ry="24"
          stroke="url(#orbitGrad2)"
          strokeWidth="1"
          strokeDasharray="3 5"
          className="strategy-robot-orbit-ring-reverse"
        />
        <defs>
          <linearGradient id="orbitGrad1" x1="14" y1="38" x2="186" y2="102" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.8" />
            <stop offset="50%" stopColor="#818cf8" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.8" />
          </linearGradient>
          <linearGradient id="orbitGrad2" x1="30" y1="46" x2="170" y2="94" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#a855f7" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.7" />
          </linearGradient>
        </defs>
        <circle cx="24" cy="64" r="2.5" fill="#38bdf8" className="strategy-robot-sparkle" />
        <circle cx="176" cy="76" r="2" fill="#818cf8" className="strategy-robot-sparkle" style={{ animationDelay: "0.8s" }} />
        <circle cx="138" cy="44" r="1.8" fill="#3b82f6" className="strategy-robot-sparkle" style={{ animationDelay: "1.4s" }} />
        <circle cx="62" cy="96" r="2.2" fill="#06b6d4" className="strategy-robot-sparkle" style={{ animationDelay: "2s" }} />
      </svg>

      <div
        className={`strategy-robot-figure ${tilt.active ? "" : "strategy-robot-floating"} ${bouncing ? "strategy-robot-bounce" : ""}`}
        style={
          tilt.active
            ? {
                transform: `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg) scale(1.04)`,
              }
            : undefined
        }
      >
        <img src="/robot-assistant.jpg" alt="JavaApex Assistant" />
      </div>

      {showSpeech && (
        <div className="strategy-robot-speech-bubble">
          👋 Ready to modernize your Java stack!
        </div>
      )}
    </div>
  );
};

// Thinking indicator component with subtle animation
const AnimatedRetrieving: React.FC<{ label?: string }> = ({ label = "Preparing answer..." }) => {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="strategy-chat-spin" style={{ color: "#3b82f6" }}>
        <circle cx="12" cy="2" r="2.5" fill="currentColor" opacity="1" />
        <circle cx="19" cy="5" r="2.5" fill="currentColor" opacity="0.8" />
        <circle cx="22" cy="12" r="2.5" fill="currentColor" opacity="0.6" />
        <circle cx="19" cy="19" r="2.5" fill="currentColor" opacity="0.4" />
        <circle cx="12" cy="22" r="2.5" fill="currentColor" opacity="0.2" />
        <circle cx="5" cy="19" r="2.5" fill="currentColor" opacity="0.2" />
        <circle cx="2" cy="12" r="2.5" fill="currentColor" opacity="0.2" />
        <circle cx="5" cy="5" r="2.5" fill="currentColor" opacity="0.2" />
      </svg>
      <span style={{ color: "#0f172a", fontWeight: 500, fontSize: "14px", whiteSpace: "nowrap" }}>
        {label}
      </span>
    </span>
  );
};

export default function FloatingChatbot() {
  const { repoUrl, strategyContext, projectContext, appContext, hideChatbot } = useChatbot();
  const assistantName = "JavaApex Assistant";

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
  const [heroTheme, setHeroTheme] = useState<"blue" | "purple" | "green" | "orange">("blue");

  const [sourcesMap, setSourcesMap] = useState<Record<string, SourceReference[]>>({});

  // LLM configuration check
  const [isLlmConfigured, setIsLlmConfigured] = useState<boolean | null>(null);
  const [isLlmDisabledByAdmin, setIsLlmDisabledByAdmin] = useState<boolean>(false);

  const checkLlmConfig = useCallback(() => {
    getUserSettings()
      .then((s) => {
        const perms = s.settings_permissions;
        const isAllowed = perms?.llm_settings !== false && s.system_llm_config?.llm_enabled !== "false";
        if (!isAllowed) {
          setIsLlmDisabledByAdmin(true);
          setIsLlmConfigured(false);
          return;
        }
        setIsLlmDisabledByAdmin(false);
        const llm = s.llm_values || {};
        const groqOk = Boolean(llm.groq_api_key && llm.groq_model);
        const hfOk = Boolean(llm.huggingface_api_key && llm.huggingface_model);
        const ollamaOk = Boolean(llm.ollama_url);
        setIsLlmConfigured(groqOk || hfOk || ollamaOk);
      })
      .catch(() => {
        setIsLlmConfigured(null);
      });
  }, []);

  // Re-check every time the panel opens
  useEffect(() => {
    if (open) checkLlmConfig();
  }, [open, checkLlmConfig]);

  // Also re-check immediately when settings are saved from the settings page
  useEffect(() => {
    window.addEventListener("javaapex:settings-saved", checkLlmConfig);
    return () => window.removeEventListener("javaapex:settings-saved", checkLlmConfig);
  }, [checkLlmConfig]);

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
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;

    setIsAutoScrolling((prev) => (prev === isAtBottom ? prev : isAtBottom));
    setShowScrollButton((prev) => (prev === !isAtBottom ? prev : !isAtBottom));
  }, []);

  useEffect(() => {
    if (open && isAutoScrolling) {
      scrollToBottom(sending ? "auto" : "smooth");
    }
  }, [open, messages, sending, isAutoScrolling]);

  useEffect(() => {
    if (open) {
      setTimeout(() => {
        scrollToBottom("auto");
        textareaRef.current?.focus();
      }, 100);
    }
  }, [open]);

  const addMessage = (msg: ChatMessage) => setMessages((m) => [...m, msg]);

  const handleSend = async (textToSend?: string) => {
    const text = (typeof textToSend === "string" ? textToSend : input).trim();
    if (!text || sending) return;

    // Cache input in case of immediate dispatch error
    const prevInput = input;
    setInput("");
    setOpen(true);
    setSending(true);

    const userMessage: ChatMessage = {
      id: `u_${Date.now()}`,
      role: "user",
      content: text,
      createdAt: new Date().toISOString(),
    };
    addMessage(userMessage);

    // Initial contextual thinking label
    const initialThinking = determineThinkingState(text);

    const assistantPlaceholder: ChatMessage = {
      id: `a_${Date.now()}`,
      role: "assistant",
      content: initialThinking,
      createdAt: new Date().toISOString(),
    };
    addMessage(assistantPlaceholder);

    const controller = new AbortController();
    abortControllerRef.current = controller;
    abortedByUserRef.current = false;

    let streamedBuffer = "";

    try {
      const result = await sendMessage({
        question: text,
        repoUrl,
        strategyContext,
        projectContext,
        appContext,
        history: [...messages, userMessage],
        onPhase: (phase) => {
          if (!streamedBuffer) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantPlaceholder.id ? { ...m, content: phase } : m
              )
            );
          }
        },
        onReferences: (sources) => {
          if (sources.length > 0) {
            setSourcesMap((prev) => ({ ...prev, [assistantPlaceholder.id]: sources }));
          }
        },
        onChunk: (chunk) => {
          streamedBuffer += chunk;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantPlaceholder.id ? { ...m, content: streamedBuffer } : m
            )
          );
        },
        signal: controller.signal,
      });

      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantPlaceholder.id) return m;
          return {
            ...m,
            content: result.answer || streamedBuffer || "...",
            rationale: result.rationale,
            comparisonTable: result.comparisonTable,
          };
        })
      );

      if (result.sources && result.sources.length > 0) {
        setSourcesMap((prev) => ({ ...prev, [assistantPlaceholder.id]: result.sources! }));
      }
    } catch (err: unknown) {
      const aborted =
        abortedByUserRef.current ||
        (err instanceof Error && (err.name === "AbortError" || err.message === "AbortError"));

      if (aborted) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantPlaceholder.id
              ? { ...m, content: streamedBuffer || "Response stopped by user." }
              : m
          )
        );
      } else {
        const isNotConfigured = err instanceof Error && err.message === "LLM_NOT_CONFIGURED";

        // Graceful error display without exposing technical stack traces or tokens
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantPlaceholder.id
              ? {
                  ...m,
                  content: isNotConfigured
                    ? "LLM is not configured, please setup in settings."
                    : "I couldn't complete that request right now. Please try asking again or select one of the quick actions.",
                }
              : m
          )
        );
        // Preserve user input text if nothing was streamed
        if (!streamedBuffer) {
          setInput(prevInput);
        }
      }
    } finally {
      setSending(false);
      abortControllerRef.current = null;
      abortedByUserRef.current = false;
      setTimeout(() => {
        textareaRef.current?.focus();
      }, 50);
    }
  };

  const handleStop = () => {
    const ctrl = abortControllerRef.current;
    if (ctrl) {
      abortedByUserRef.current = true;
      try {
        ctrl.abort();
      } catch {
        // ignore
      }
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const clearHistory = () => {
    setMessages([]);
    try {
      localStorage.removeItem(storageKey);
    } catch {
      // ignore
    }
  };

  if (hideChatbot) return null;

  return (
    <div>
      {/* Floating launcher */}
      <div className="strategy-chat-launcher-container">
        {hovered && (
          <div className="strategy-chat-launcher-tooltip">
            {open ? "Close Assistant" : "✨ Ask JavaApex Assistant"}
          </div>
        )}
        <button
          onClick={() => setOpen((v) => !v)}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          aria-label={open ? "Close JavaApex Assistant" : "Open JavaApex Assistant"}
          title={open ? "Close JavaApex Assistant" : "Open JavaApex Assistant"}
          className={`strategy-chat-launcher-btn ${open ? "strategy-chat-launcher-open" : ""}`}
        >
          <span className="strategy-chat-launcher-halo" aria-hidden />
          {!open && <span className="strategy-chat-launcher-radar" aria-hidden />}

          {open ? (
            <span className="strategy-chat-launcher-close-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </span>
          ) : (
            <>
              <div className="strategy-chat-launcher-avatar-wrap">
                <img src="/robot-assistant.jpg" alt="JavaApex Robot" className="strategy-chat-launcher-avatar" />
              </div>
              <span className="strategy-chat-launcher-sparkle" aria-hidden>✨</span>
              <span className="strategy-chat-launcher-badge" aria-hidden title="Online" />
            </>
          )}
        </button>
      </div>

      {/* Chat panel */}
      <div
        ref={panelRef}
        className="strategy-chat-panel"
        style={{
          position: "fixed",
          right: 24,
          left: "auto",
          bottom: 168,
          top: "auto",
          width: 520,
          height: 640,
          maxWidth: "calc(100vw - 32px)",
          maxHeight: "calc(100vh - 190px)",
          zIndex: 1250,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          transition: "opacity 300ms ease, transform 300ms cubic-bezier(0.175, 0.885, 0.32, 1.275), visibility 300ms",
          transformOrigin: "bottom right",
          ...(!open
            ? {
                opacity: 0,
                transform: "scale(0.85) translateY(20px)",
                visibility: "hidden",
                pointerEvents: "none",
              }
            : {
                opacity: 1,
                transform: "scale(1) translateY(0)",
                visibility: "visible",
                pointerEvents: "auto",
              }),
        }}
      >
        {/* Header */}
        <div className="strategy-chat-header">
          <div className="strategy-chat-brand">
            <div className="strategy-chat-avatar" aria-hidden>
              <div className="strategy-chat-avatar-img-wrap">
                <img src="/robot-assistant.jpg" alt="JavaApex Robot" className="strategy-chat-avatar-photo" />
              </div>
              <span className="strategy-chat-online-indicator" />
            </div>
            <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: "2px" }}>
              <div className="strategy-chat-title">{assistantName}</div>
              <div className="strategy-chat-subtitle">Online and ready to help</div>
            </div>
          </div>
          <div className="strategy-chat-header-actions">
            <button onClick={clearHistory} title="Clear history" className="strategy-chat-header-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 6h18" />
                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                <line x1="10" y1="11" x2="10" y2="17" />
                <line x1="14" y1="11" x2="14" y2="17" />
              </svg>
            </button>
            <button onClick={() => setOpen(false)} title="Close" className="strategy-chat-header-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        {/* Body */}
        {/* LLM not configured banner */}
        {isLlmConfigured === false && (
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              background: "#fffbeb",
              borderBottom: "1.5px solid #fde68a",
              padding: "10px 16px",
              fontSize: 13,
              color: "#92400e",
              lineHeight: 1.4,
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 1 }}>
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span>
              <strong>LLM not configured.</strong> Please go to{" "}
              <strong>User Settings → Intelligence</strong> to set up your AI provider (Groq, Hugging Face, or Ollama) before chatting.
            </span>
          </div>
        )}
        <div className="strategy-chat-body" ref={scrollContainerRef} onScroll={handleScroll}>
          <div className="strategy-chat-canvas">
            {messages.length === 0 ? (
              <div className="strategy-chat-hero">
                <DynamicRobotHero activeTheme={heroTheme} />
                <div className="strategy-chat-hero-title">
                  Hi! I'm <span style={{ color: "#2563eb" }}>JavaApex</span> Assistant
                </div>
                <div className="strategy-chat-hero-subtitle">
                  Ask me anything about your migration, code, dependencies, or modernization journey.
                </div>
                <div className="strategy-chat-hero-suggestions">
                  <button
                    type="button"
                    className="strategy-chat-suggestion-card"
                    onClick={() =>
                      void handleSend(
                        "Explain the important parts of my application and identify the main components."
                      )
                    }
                    onMouseEnter={() => setHeroTheme("blue")}
                    onMouseLeave={() => setHeroTheme("blue")}
                  >
                    <div className="strategy-chat-suggestion-icon" style={{ background: "#eff6ff", color: "#2563eb" }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="16 18 22 12 16 6"></polyline>
                        <polyline points="8 6 2 12 8 18"></polyline>
                      </svg>
                    </div>
                    <div className="strategy-chat-suggestion-text">
                      <strong>Explain Code</strong>
                      <span>Architecture & components</span>
                    </div>
                    <div className="strategy-chat-suggestion-arrow">›</div>
                  </button>

                  <button
                    type="button"
                    className="strategy-chat-suggestion-card"
                    onClick={() =>
                      void handleSend(
                        "Analyze the dependencies detected in my project and identify compatibility or migration concerns."
                      )
                    }
                    onMouseEnter={() => setHeroTheme("purple")}
                    onMouseLeave={() => setHeroTheme("blue")}
                  >
                    <div className="strategy-chat-suggestion-icon" style={{ background: "#faf5ff", color: "#9333ea" }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
                      </svg>
                    </div>
                    <div className="strategy-chat-suggestion-text">
                      <strong>Dependencies</strong>
                      <span>Frameworks & bytecode</span>
                    </div>
                    <div className="strategy-chat-suggestion-arrow">›</div>
                  </button>

                  <button
                    type="button"
                    className="strategy-chat-suggestion-card"
                    onClick={() =>
                      void handleSend(
                        "Based on the current migration findings, what fixes should I prioritize?"
                      )
                    }
                    onMouseEnter={() => setHeroTheme("green")}
                    onMouseLeave={() => setHeroTheme("blue")}
                  >
                    <div className="strategy-chat-suggestion-icon" style={{ background: "#f0fdf4", color: "#16a34a" }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M9 18h6"></path>
                        <path d="M10 22h4"></path>
                        <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"></path>
                      </svg>
                    </div>
                    <div className="strategy-chat-suggestion-text">
                      <strong>Suggest Fixes</strong>
                      <span>Prioritized remediation</span>
                    </div>
                    <div className="strategy-chat-suggestion-arrow">›</div>
                  </button>

                  <button
                    type="button"
                    className="strategy-chat-suggestion-card"
                    onClick={() =>
                      void handleSend(
                        "What migration insights should be included in the migration report?"
                      )
                    }
                    onMouseEnter={() => setHeroTheme("orange")}
                    onMouseLeave={() => setHeroTheme("blue")}
                  >
                    <div className="strategy-chat-suggestion-icon" style={{ background: "#fff7ed", color: "#ea580c" }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                        <line x1="16" y1="13" x2="8" y2="13"></line>
                        <line x1="16" y1="17" x2="8" y2="17"></line>
                        <polyline points="10 9 9 9 8 9"></polyline>
                      </svg>
                    </div>
                    <div className="strategy-chat-suggestion-text">
                      <strong>Migration Report</strong>
                      <span>Executive insights</span>
                    </div>
                    <div className="strategy-chat-suggestion-arrow">›</div>
                  </button>
                </div>
              </div>
            ) : (
              <div className="strategy-chat-messages">
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={`strategy-chat-row ${
                      m.role === "user" ? "strategy-chat-row-user" : "strategy-chat-row-assistant"
                    }`}
                  >
                    <div className="strategy-chat-message-stack">
                      <div
                        className={`strategy-chat-bubble ${
                          m.role === "user"
                            ? "strategy-chat-bubble-user"
                            : "strategy-chat-bubble-assistant"
                        }`}
                      >
                        {m.role === "assistant" && isThinkingContent(m.content) ? (
                          <AnimatedRetrieving label={m.content} />
                        ) : m.role === "assistant" ? (
                          <AssistantMessageContent
                            message={m}
                            sources={sourcesMap[m.id] ?? []}
                          />
                        ) : (
                          <div className="strategy-chat-user-content">
                            <div className="strategy-chat-user-text">{m.content || ""}</div>
                            <div className="strategy-chat-user-meta">
                              <span className="strategy-chat-user-time">
                                {new Date(m.createdAt || Date.now()).toLocaleTimeString([], {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </span>
                              <div className="strategy-chat-user-avatar">
                                <svg viewBox="0 0 24 24" fill="currentColor">
                                  <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                                </svg>
                              </div>
                            </div>
                          </div>
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

        {/* Input Composer */}
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
            <div className="strategy-chat-composer-inner">
              <button type="button" className="strategy-chat-attach" aria-label="Attach file">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
                </svg>
              </button>
              <div className="strategy-chat-input-wrapper">
                <textarea
                  ref={textareaRef}
                  placeholder={
                    isLlmDisabledByAdmin
                      ? "⛔ LLM Chat disabled by Super Admin"
                      : isLlmConfigured === false
                      ? "⚙️ LLM setup needed — configure in User Settings → Intelligence"
                      : "Ask your queries..."
                  }
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={1}
                  disabled={isLlmConfigured === false || isLlmDisabledByAdmin}
                  className="strategy-chat-input"
                  style={isLlmConfigured === false || isLlmDisabledByAdmin ? { opacity: 0.55, cursor: "not-allowed" } : undefined}
                />
              </div>
              {!input && isLlmConfigured !== false && !isLlmDisabledByAdmin && <span className="strategy-chat-hint">Press Enter to send</span>}
            </div>
            <button
              type="submit"
              disabled={isLlmConfigured === false || isLlmDisabledByAdmin || (!input.trim() && !sending)}
              className={`strategy-chat-send ${sending ? "strategy-chat-send-stop" : ""}`}
              aria-label={sending ? "Stop generation" : "Send question"}
              title={
                isLlmDisabledByAdmin
                  ? "LLM feature is disabled by Super Admin"
                  : isLlmConfigured === false
                  ? "Configure LLM in User Settings first"
                  : sending
                  ? "Stop generation"
                  : "Send question"
              }
            >
              <span className="strategy-chat-send-icon-wrapper">
                {sending ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <rect x="7" y="7" width="10" height="10" rx="2.2" fill="currentColor" />
                  </svg>
                ) : (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" stroke="none">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                  </svg>
                )}
              </span>
            </button>
          </form>
          <div className="strategy-chat-footer">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
              <polyline points="9 12 11 14 15 10"></polyline>
            </svg>
            Your data stays secure and private.
          </div>
        </div>
      </div>
    </div>
  );
}
