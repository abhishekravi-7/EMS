import { useMemo } from "react";
import { FaTimes } from "react-icons/fa";
import "./ReactPageSandbox.css";

type GeneratedLine = { text: string };

interface ReactPageSandboxProps {
  fileName: string;
  code: GeneratedLine[];
  css: string;
  onClose: () => void;
}

const escapeHtml = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function selectGeneratedFile(source: string, fileName: string): string {
  const lines = source.split(/\r?\n/);
  const normalizedFileName = fileName.replace(/\\/g, "/").toLowerCase();
  const markerPattern = /^\s*\/\/\s*(?:---\s*)?([^\s]+\.(?:tsx|jsx|ts|js|css|scss))(?:\s*---)?\s*$/i;
  const markerIndex = lines.findIndex((line) => {
    const match = line.match(markerPattern);
    return match?.[1].replace(/\\/g, "/").toLowerCase() === normalizedFileName;
  });

  if (markerIndex < 0) return source;
  const nextMarkerIndex = lines.findIndex((line, index) => index > markerIndex && markerPattern.test(line));
  return lines.slice(markerIndex + 1, nextMarkerIndex < 0 ? lines.length : nextMarkerIndex).join("\n");
}

function jsxToHtml(source: string): string {
  const returnMatch = source.match(/return\s*\(([\s\S]*?)\);/m);
  let markup = returnMatch?.[1] ?? "";
  if (!markup.trim()) return "";
  markup = markup
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/\bclassName=/g, "class=")
    .replace(/\bhtmlFor=/g, "for=")
    .replace(/\b(src|href|alt|title|placeholder|type|name|id|role|aria-[\w-]+)=\{`([^`]*)`\}/g, "$1=\"$2\"")
    .replace(/\b(src|href|alt|title|placeholder|type|name|id|role|aria-[\w-]+)=\{"([^"]*)"\}/g, "$1=\"$2\"")
    .replace(/\b(src|href|alt|title|placeholder|type|name|id|role|aria-[\w-]+)=\{([^{}]+)\}/g, (_match, name: string, value: string) => `${name}="${escapeHtml(value.trim())}"`)
    .replace(/\s+(onClick|onChange|onSubmit|onBlur|onFocus)=\{[^{}]*\}/g, "")
    .replace(/\s+style=\{\{([^{}]*)\}\}/g, (_match, value: string) => {
      const css = value
        .split(",")
        .map((part) => part.trim().replace(/([a-z])([A-Z])/g, "$1-$2").replace(/:/, ":"))
        .filter(Boolean)
        .join(";");
      return ` style="${escapeHtml(css)}"`;
    })
    .replace(/\{[^{}]*\}/g, "")
    .replace(/<([A-Z][\w.]*)[^>]*\/?>(?:<\/\1>)?/g, "")
    .replace(/\s*\/?>/g, (tag) => tag)
    .replace(/<([a-z][\w-]*)([^>]*)\s+\/\s*>/gi, "<$1$2></$1>");

  return markup.trim();
}

export function ReactPageSandbox({ fileName, code, css, onClose }: ReactPageSandboxProps) {
  const srcDoc = useMemo(() => {
    const source = code.map((line) => line.text).join("\n");
    const selectedSource = selectGeneratedFile(source, fileName);
    const markup = jsxToHtml(selectedSource);
    const preview = markup || `<div class="react-sandbox-empty"><h3>Preview unavailable</h3><p>${escapeHtml(fileName)} does not contain renderable JSX markup.</p></div>`;
    return `<!doctype html><html><head><meta charset="utf-8"><style>
      :root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
      body { margin: 0; padding: 32px; background: #f8fafc; color: #0f172a; }
      .react-sandbox-empty { max-width: 520px; margin: 48px auto; padding: 28px; border: 1px solid #cbd5e1; border-radius: 10px; background: #fff; }
      .react-sandbox-empty h3 { margin: 0 0 8px; }
      .react-sandbox-empty p { margin: 0; color: #64748b; }
      ${css}
    </style></head><body><main data-migrated-preview="true">${preview}</main></body></html>`;
  }, [code, css, fileName]);

  return (
    <div className="react-sandbox-backdrop" role="dialog" aria-modal="true" aria-label="Migrated React page preview">
      <section className="react-sandbox-panel">
        <header className="react-sandbox-header">
          <div>
            <span className="react-sandbox-kicker">React sandbox</span>
            <h2>{fileName}</h2>
            <p>Generated JSP/JSF UI rendered with the migrated markup and available CSS.</p>
          </div>
          <button type="button" className="react-sandbox-close" onClick={onClose} aria-label="Close React page preview" title="Close preview">
            <FaTimes />
          </button>
        </header>
        <iframe className="react-sandbox-frame" title={`Preview of ${fileName}`} srcDoc={srcDoc} sandbox="allow-same-origin" />
        <footer className="react-sandbox-footer">
          Static UI preview. API calls, navigation, and event handlers require the migrated application runtime.
        </footer>
      </section>
    </div>
  );
}
