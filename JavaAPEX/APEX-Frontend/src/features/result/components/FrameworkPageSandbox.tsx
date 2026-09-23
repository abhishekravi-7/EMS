import { useMemo } from "react";
import { FaTimes } from "react-icons/fa";
import "./FrameworkPageSandbox.css";

type GeneratedLine = { text: string };

interface FrameworkPageSandboxProps {
  fileName: string;
  code: GeneratedLine[];
  css: string;
  onClose: () => void;
}

const escapeHtml = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** Strip diff prefix characters from each line before parsing */
function stripDiffMarkers(lines: string[]): string[] {
  return lines.map((line) => {
    if (/^\+/.test(line)) return line.slice(1);
    if (/^-/.test(line)) return "";
    if (/^ /.test(line)) return line.slice(1);
    return line;
  });
}

function selectGeneratedFile(source: string, fileName: string): string {
  const lines = source.split(/\r?\n/);
  const normalizedFileName = fileName.replace(/\\/g, "/").toLowerCase();
  const baseName = normalizedFileName.split("/").pop() || normalizedFileName;

  const markerIndex = lines.findIndex((line) => {
    const trimmed = line.trim();
    if (!trimmed.startsWith("//") && !trimmed.startsWith("/*")) return false;
    const lower = trimmed.toLowerCase();
    return lower.includes(normalizedFileName) || lower.includes(baseName) || lower.includes(`/${baseName}`);
  });

  if (markerIndex < 0) return source;

  const nextMarkerIndex = lines.findIndex((l, i) => {
    if (i <= markerIndex) return false;
    const trimmed = l.trim();
    if (!trimmed.startsWith("//") && !trimmed.startsWith("/*")) return false;
    return /\b[\w\/-]+\.(tsx|jsx|ts|js|css|scss|html)\b/i.test(trimmed);
  });

  return lines.slice(markerIndex + 1, nextMarkerIndex < 0 ? lines.length : nextMarkerIndex).join("\n");
}

function stripJsxEventHandlers(code: string): string {
  let result = "";
  let i = 0;
  while (i < code.length) {
    const match = code.slice(i).match(/^(\s+on[A-Z]\w+\s*=\s*\{)/);
    if (match) {
      const matchLen = match[0].length;
      let depth = 1;
      let j = i + matchLen;
      let inString = false;
      let quoteChar = "";

      while (j < code.length && depth > 0) {
        const char = code[j];
        const prevChar = j > 0 ? code[j - 1] : "";

        if (inString) {
          if (char === quoteChar && prevChar !== "\\") inString = false;
        } else if (char === '"' || char === "'" || char === "`") {
          inString = true;
          quoteChar = char;
        } else if (char === "{") {
          depth++;
        } else if (char === "}") {
          depth--;
        }
        j++;
      }
      i = j;
    } else {
      result += code[i];
      i++;
    }
  }
  return result;
}

function cleanJsxAttributes(markup: string): string {
  if (!markup) return "";

  let cleaned = stripJsxEventHandlers(markup)
    // Strip block comments and JSX comments
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    // Convert React Fragments <> and </> to <div>
    .replace(/<>\s*/g, '<div class="react-fragment">')
    .replace(/<\/>/g, '</div>')
    .replace(/<React\.Fragment[^>]*>/g, '<div class="react-fragment">')
    .replace(/<\/React\.Fragment>/g, '</div>')
    // Standard attribute renaming
    .replace(/\bclassName=/g, "class=")
    .replace(/\bhtmlFor=/g, "for=")
    .replace(/\b([\w-]+)=\{`([^`]*)`\}/g, '$1="$2"')
    .replace(/\b([\w-]+)=\{"([^"]*)"\}/g, '$1="$2"')
    .replace(/\b([\w-]+)=\{'([^']*)'\}/g, '$1="$2"')
    .replace(/\s+style=\{\{([^{}]*)\}\}/g, (_match, value: string) => {
      const css = value
        .split(",")
        .map((p) => p.trim().replace(/([a-z])([A-Z])/g, "$1-$2").toLowerCase())
        .filter(Boolean)
        .join("; ");
      return ` style="${escapeHtml(css)}"`;
    });

  // 1. TextField / Input components
  cleaned = cleaned.replace(
    /<(?:TextField|MuiTextField|Input|Form\.Control|CustomInput|TextInput)\b([^>]*)\/?>/gi,
    (_match, attrs) => {
      const labelMatch = attrs.match(/label=["']([^"']+)["']/i);
      const nameMatch = attrs.match(/name=["']([^"']+)["']/i);
      const placeholderMatch = attrs.match(/placeholder=["']([^"']+)["']/i);
      const typeMatch = attrs.match(/type=["']([^"']+)["']/i);
      const valueMatch = attrs.match(/value=["']([^"']+)["']/i);

      const labelText = labelMatch?.[1] || nameMatch?.[1] || "";
      const inputType = typeMatch?.[1] || "text";
      const placeholder = placeholderMatch?.[1] || labelText || "";
      const val = valueMatch?.[1] ? ` value="${escapeHtml(valueMatch[1])}"` : "";

      const labelHtml = labelText ? `<label class="form-label font-weight-bold mb-1">${escapeHtml(labelText)}</label>` : "";
      return `<div class="form-group mb-3">${labelHtml}<input type="${escapeHtml(inputType)}" class="form-control" placeholder="${escapeHtml(placeholder)}"${val} /></div>`;
    }
  );

  // 2. Button components
  cleaned = cleaned
    .replace(/<(?:Button|MuiButton|IconButton|Form\.Button|CustomButton|SubmitButton)\b[^>]*>([\s\S]*?)<\/(?:Button|MuiButton|IconButton|Form\.Button|CustomButton|SubmitButton)>/gi, '<button type="button" class="btn btn-primary m-1">$1</button>')
    .replace(/<(?:Button|MuiButton|IconButton)\b[^>]*\/>/gi, '<button type="button" class="btn btn-primary m-1">Submit</button>');

  // 3. Select / MenuItem components
  cleaned = cleaned
    .replace(/<Select\b([^>]*)\blabel=["']([^"']+)["'][^>]*>([\s\S]*?)<\/Select>/gi, '<div class="form-group mb-3"><label class="form-label font-weight-bold">$2</label><select class="form-control">$3</select></div>')
    .replace(/<Select\b[^>]*>([\s\S]*?)<\/Select>/gi, '<select class="form-control">$1</select>')
    .replace(/<MenuItem\b[^>]*\bvalue=["']([^"']+)["'][^>]*>([\s\S]*?)<\/MenuItem>/gi, '<option value="$1">$2</option>')
    .replace(/<MenuItem\b[^>]*>([\s\S]*?)<\/MenuItem>/gi, '<option>$1</option>');

  // 4. Typography components
  cleaned = cleaned
    .replace(/<Typography\b[^>]*\bvariant=["'](h[1-6])["'][^>]*>([\s\S]*?)<\/Typography>/gi, '<$1 class="typography-$1">$2</$1>')
    .replace(/<Typography\b[^>]*>([\s\S]*?)<\/Typography>/gi, '<div class="typography-body my-1">$1</div>');

  // 5. Card / CardContent / CardHeader / Paper components
  cleaned = cleaned
    .replace(/<CardHeader\b[^>]*\btitle=["']([^"']+)["'][^>]*\/>/gi, '<div class="card-header font-weight-bold">$1</div>')
    .replace(/<(?:Card|Paper|MuiPaper)\b[^>]*>([\s\S]*?)<\/(?:Card|Paper|MuiPaper)>/gi, '<div class="card shadow-sm mb-3">$1</div>')
    .replace(/<CardContent\b[^>]*>([\s\S]*?)<\/CardContent>/gi, '<div class="card-body">$1</div>')
    .replace(/<CardActions\b[^>]*>([\s\S]*?)<\/CardActions>/gi, '<div class="card-footer bg-transparent border-0">$1</div>');

  // 6. Layout components: Container, Grid, Box, Stack, Row, Col
  cleaned = cleaned
    .replace(/<(?:Container|Box|Stack|MuiBox|MuiContainer)\b[^>]*>([\s\S]*?)<\/(?:Container|Box|Stack|MuiBox|MuiContainer)>/gi, '<div class="container my-2">$1</div>')
    .replace(/<Grid\b[^>]*\bcontainer[^>]*>([\s\S]*?)<\/Grid>/gi, '<div class="row">$1</div>')
    .replace(/<Grid\b[^>]*\bitem[^>]*>([\s\S]*?)<\/Grid>/gi, '<div class="col">$1</div>')
    .replace(/<Grid\b[^>]*>([\s\S]*?)<\/Grid>/gi, '<div class="col">$1</div>');

  // 7. Table components: Table, TableHead, TableBody, TableRow, TableCell
  cleaned = cleaned
    .replace(/<Table\b[^>]*>([\s\S]*?)<\/Table>/gi, '<table class="table table-bordered table-striped my-3">$1</table>')
    .replace(/<TableHead\b[^>]*>([\s\S]*?)<\/TableHead>/gi, '<thead class="thead-dark">$1</thead>')
    .replace(/<TableBody\b[^>]*>([\s\S]*?)<\/TableBody>/gi, '<tbody>$1</tbody>')
    .replace(/<TableRow\b[^>]*>([\s\S]*?)<\/TableRow>/gi, '<tr>$1</tr>')
    .replace(/<TableCell\b[^>]*>([\s\S]*?)<\/TableCell>/gi, '<td>$1</td>');

  // 8. Alert / Link components
  cleaned = cleaned
    .replace(/<Alert\b[^>]*>([\s\S]*?)<\/Alert>/gi, '<div class="alert alert-info">$1</div>')
    .replace(/<Link\b[^>]*\bto=["']([^"']+)["'][^>]*>([\s\S]*?)<\/Link>/gi, '<a href="#" class="btn btn-link p-0 m-1">$2</a>')
    .replace(/<Link\b[^>]*>([\s\S]*?)<\/Link>/gi, '<a href="#" class="btn btn-link p-0 m-1">$1</a>');

  // 9. Generic Capital-letter Components
  cleaned = cleaned
    .replace(/<([A-Z][A-Za-z0-9.]*)\b[^>]*>([\s\S]*?)<\/\1>/g, '<div class="custom-component my-2">$2</div>')
    .replace(/<([A-Z][A-Za-z0-9.]*)\b[^>]*\/>/g, '<div class="custom-component-item my-1"></div>');

  // 10. Handle JSX Expressions safely & strip raw JS IIFEs / dynamic variable alerts:
  // Strip inline IIFE expressions like {(() => { ... })()}
  cleaned = cleaned
    .replace(/\{\s*\(\s*\(\s*\)\s*=>[\s\S]*?\)\s*\(\s*\)\s*\}/g, "")
    .replace(/\(\s*\(\s*\)\s*=>[\s\S]*?\)\s*\(\s*\)/g, "");

  // Convert {items && items.map((x) => ( <tag>...</tag> ))} to sample inner tag
  cleaned = cleaned.replace(/\{[^{}]*?\.map\s*\(\s*(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>\s*(?:\(\s*)?(<[\s\S]*?>)(?:\s*\))?\s*\)\s*\}/g, '$1\n$1');

  // Convert {(condition) && ( <tag>...</tag> )} to inner tag
  cleaned = cleaned.replace(/\{[^{}]*?&&\s*(?:\(\s*)?(<[\s\S]*?>)(?:\s*\))?\s*\}/g, '$1');

  // Strip alerts or message divs that only contain variable placeholders (infoMsg, errorMsg, msg, error)
  cleaned = cleaned
    .replace(/<div\b[^>]*class=["'][^"']*(?:alert|message|error|info|success|danger|warning)[^"']*["'][^>]*>\s*(?:infoMsg|errorMsg|errorMessage|infoMessage|successMessage|msg|error|message)?\s*<\/div>/gi, "")
    .replace(/<p\b[^>]*class=["'][^"']*(?:alert|message|error|info|success|danger|warning)[^"']*["'][^>]*>\s*(?:infoMsg|errorMsg|errorMessage|infoMessage|successMessage|msg|error|message)?\s*<\/p>/gi, "");

  // Replace state variable placeholders with empty string so raw variable names don't render as text
  cleaned = cleaned.replace(/\{\s*(?:infoMsg|errorMsg|errorMessage|infoMessage|successMessage|msg|error|message|csrf|getCsrfToken\(\))\s*\}/gi, "");

  // Convert simple {variable} or {data.field} to variable name
  cleaned = cleaned.replace(/\{([A-Za-z0-9_$.]+)\}/g, '$1');

  // Clean remaining lone curly braces and leftover JS code fragments
  cleaned = cleaned
    .replace(/\{|\}/g, "")
    .replace(/const\s+\w+\s*=\s*[^;]+;/g, "")
    .replace(/\bgetCsrfToken\(\);?/gi, "");

  // Ensure void elements are properly closed for HTML5
  cleaned = cleaned
    .replace(/<(input|br|hr|img|link|meta|area|base|col|embed|param|source|track|wbr)([^>]*)\s*\/?>/gi, "<$1$2>")
    .replace(/<([a-z][\w-]*)([^>]*)\s+\/>/gi, "<$1$2></$1>");

  return cleaned.trim();
}

function stripLeadingHeaderComments(source: string): string {
  const lines = source.split(/\r?\n/);
  let firstCodeLine = 0;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (
      line.startsWith("//") ||
      line.startsWith("/*") ||
      line.startsWith("*") ||
      line.startsWith("#") ||
      line === ""
    ) {
      continue;
    }
    firstCodeLine = i;
    break;
  }
  return lines.slice(firstCodeLine).join("\n");
}

function extractAllJsxBlocks(code: string, fileName: string): string[] {
  const blocks: { name: string; jsx: string }[] = [];
  const stem = fileName.replace(/\\/g, "/").split("/").pop()?.replace(/\.[^.]+$/, "").toLowerCase() || "";

  const compRegex = /(?:function|const|class)\s+([A-Z][A-Za-z0-9_]*)/g;
  let compMatch;
  const compIndices: { name: string; index: number }[] = [];
  while ((compMatch = compRegex.exec(code)) !== null) {
    compIndices.push({ name: compMatch[1], index: compMatch.index });
  }

  const extractJsxFromPos = (startPos: number, isParen: boolean): string => {
    if (isParen) {
      let depth = 1;
      let inString = false;
      let quoteChar = "";
      let endIndex = -1;
      for (let i = startPos; i < code.length; i++) {
        const char = code[i];
        const prevChar = i > 0 ? code[i - 1] : "";
        if (inString) {
          if (char === quoteChar && prevChar !== "\\") inString = false;
          continue;
        }
        if (char === '"' || char === "'" || char === "`") {
          inString = true;
          quoteChar = char;
          continue;
        }
        if (char === "(") depth++;
        else if (char === ")") {
          depth--;
          if (depth === 0) {
            endIndex = i;
            break;
          }
        }
      }
      if (endIndex > startPos) {
        return code.slice(startPos, endIndex);
      }
    } else {
      const firstTag = code.indexOf("<", startPos);
      if (firstTag >= 0) {
        const sub = code.slice(firstTag);
        const tagMatch = sub.match(/^<([a-zA-Z0-9.]+)/);
        if (tagMatch) {
          const rootTag = tagMatch[1];
          const closeTag = `</${rootTag}>`;
          const closeIdx = sub.lastIndexOf(closeTag);
          if (closeIdx >= 0) {
            return code.slice(firstTag, firstTag + closeIdx + closeTag.length);
          }
        }
        return code.slice(firstTag, Math.min(code.length, firstTag + 1000));
      }
    }
    return "";
  };

  const returnRegex = /(?:\breturn\s*|=>\s*)(\(|\s*<)/g;
  let match;
  while ((match = returnRegex.exec(code)) !== null) {
    const isParen = match[1] === "(";
    const pos = match.index + match[0].length;
    const jsx = extractJsxFromPos(pos, isParen);

    if (jsx.trim() && jsx.includes("<")) {
      let compName = "Component";
      for (let i = compIndices.length - 1; i >= 0; i--) {
        if (compIndices[i].index < match.index) {
          compName = compIndices[i].name;
          break;
        }
      }
      if (/^\s*<Redirect\b/i.test(jsx.trim())) continue;
      blocks.push({ name: compName, jsx });
    }
  }

  if (blocks.length === 0) return [];

  if (stem) {
    const matchingBlocks = blocks.filter((b) => {
      const nameLower = b.name.toLowerCase();
      const stemClean = stem.replace(/component|page/g, "");
      const nameClean = nameLower.replace(/component|page/g, "");
      return (
        nameLower.includes(stem) ||
        stem.includes(nameLower) ||
        (stemClean.length > 2 && nameClean.includes(stemClean)) ||
        (nameClean.length > 2 && stemClean.includes(nameClean))
      );
    });
    if (matchingBlocks.length > 0) {
      return matchingBlocks.map((b) => b.jsx);
    }
  }

  return [blocks[0].jsx];
}

function extractRootTagBlock(source: string): string {
  const cleanCode = stripLeadingHeaderComments(source);
  const rootTagMatch = cleanCode.match(/<(div|form|main|section|article|header|nav|table|ul|ol|Container|Box|Card)\b[^>]*>[\s\S]*/im);
  if (rootTagMatch?.[0]) return cleanJsxAttributes(rootTagMatch[0]);
  return "";
}

function extractAllHtmlTags(source: string): string {
  const cleanCode = stripLeadingHeaderComments(source);
  const tagPattern = /(<\/?(?:div|form|input|button|label|select|option|textarea|table|tr|td|th|thead|tbody|span|p|h[1-6]|a|img|nav|header|footer|main|section|ul|li|ol)\b[^>]*\/?>)/gi;
  const parts: string[] = [];
  let m;
  while ((m = tagPattern.exec(cleanCode)) !== null) parts.push(m[1]);
  return parts.length ? cleanJsxAttributes(parts.join("\n")) : "";
}

function jsxToHtml(source: string, fileName: string = ""): string {
  const cleanCode = stripLeadingHeaderComments(source);
  if (!cleanCode.trim()) return "";

  const jsxBlocks = extractAllJsxBlocks(cleanCode, fileName);
  if (jsxBlocks.length > 0) {
    const combinedJsx = jsxBlocks.join("\n");
    const cleaned = cleanJsxAttributes(combinedJsx);
    if (cleaned.trim()) return cleaned.trim();
  }

  const rootBlock = extractRootTagBlock(cleanCode);
  if (rootBlock.trim()) return rootBlock.trim();

  const allTags = extractAllHtmlTags(cleanCode);
  if (allTags.trim()) return allTags.trim();

  return "";
}

function angularToHtml(source: string): string {
  const cleanCode = stripLeadingHeaderComments(source);
  const templateMatch =
    cleanCode.match(/template\s*:\s*`([\s\S]*?)`/m) ||
    cleanCode.match(/template\s*:\s*'([\s\S]*?)'/m);
  let markup = templateMatch?.[1] ?? cleanCode;

  let cleaned = markup
    .replace(/<mat-form-field\b[^>]*>([\s\S]*?)<\/mat-form-field>/gi, '<div class="form-group mb-3">$1</div>')
    .replace(/<mat-label\b[^>]*>([\s\S]*?)<\/mat-label>/gi, '<label class="form-label font-weight-bold mb-1">$1</label>')
    .replace(/<mat-select\b[^>]*>([\s\S]*?)<\/mat-select>/gi, '<select class="form-control">$1</select>')
    .replace(/<mat-option\b[^>]*\bvalue=["']([^"']+)["'][^>]*>([\s\S]*?)<\/option>/gi, '<option value="$1">$2</option>')
    .replace(/<mat-card\b[^>]*>([\s\S]*?)<\/mat-card>/gi, '<div class="card shadow-sm mb-3"><div class="card-body">$1</div></div>')
    .replace(/\*ngIf="[^"]*"/g, "")
    .replace(/\[ngIf\]="[^"]*"/g, "")
    .replace(/\*ngFor="[^"]*"/g, "")
    .replace(/\[(ngModel)\]="[^"]*"/g, "")
    .replace(/\((ngSubmit|click|change|input|blur|focus|keyup|keydown)\)="[^"]*"/g, "")
    .replace(/\[(src|href|alt|title|class|style|disabled|hidden|value|checked)\]="([^"]*)"/g,
      (_m, attr: string, value: string) =>
        value.startsWith("'") && value.endsWith("'") ? `${attr}="${value.slice(1, -1)}"` : `${attr}=""`
    )
    .replace(/\{\{\s*([^}]*)\s*\}\}/g, '$1')
    .replace(/<ng-container[^>]*>/gi, "")
    .replace(/<\/ng-container>/gi, "")
    .replace(/<ng-template[^>]*>/gi, "")
    .replace(/<\/ng-template>/gi, "")
    .replace(/<app-[\w-]+[^>]*\/>/gi, "")
    .replace(/<app-[\w-]+[^>]*>[\s\S]*?<\/app-[\w-]+>/gi, "")
    .trim();

  return cleanJsxAttributes(cleaned);
}

function generatePreviewHtml(rawLines: GeneratedLine[], fileName: string): string {
  const rawText = rawLines.map((l) => l.text).join("\n");
  const cleanSource = stripDiffMarkers(rawText.split("\n")).join("\n");
  const selectedSource = selectGeneratedFile(cleanSource, fileName);
  const isAngular = fileName.endsWith(".ts") || fileName.endsWith(".html");
  const markup = isAngular
    ? angularToHtml(selectedSource)
    : jsxToHtml(selectedSource, fileName);

  if (markup && markup.trim()) return markup.trim();

  const codeWithoutComments = stripLeadingHeaderComments(selectedSource);
  const codeLines = (codeWithoutComments.trim() || selectedSource.trim())
    .split("\n")
    .filter((l) => !/^\s*\/\/\s*(Verified source|JSP\/JSF|Shared includes|Backend endpoints|Entities|Auth requirement|Spring Security|Migrated React|Backend contract|Note:)/i.test(l))
    .slice(0, 50)
    .join("\n");

  return `<div class="card p-3 shadow-sm bg-white border-0"><h5 class="card-title text-primary font-weight-bold mb-3">${escapeHtml(fileName)}</h5><pre class="bg-light p-3 rounded text-dark" style="max-height: 450px; overflow: auto; font-family: monospace; font-size: 13px;"><code>${escapeHtml(codeLines)}</code></pre></div>`;
}

export function FrameworkPageSandbox({ fileName, code, css, onClose }: FrameworkPageSandboxProps) {
  const srcDoc = useMemo(() => {
    const markup = generatePreviewHtml(code, fileName);
    const isAngular = fileName.endsWith(".ts");
    const frameworkName = isAngular ? "Angular" : "React";
    const preview = markup
      ? markup
      : `<div class="react-sandbox-empty"><h3>Preview unavailable</h3><p>${escapeHtml(fileName)} does not contain renderable markup.</p></div>`;

    return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(frameworkName)} Preview</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css" crossorigin="anonymous">
  <style>
    :root { color-scheme: light; }
    body { font-family: Inter, ui-sans-serif, system-ui, sans-serif; margin: 0; padding: 24px; background: #f8fafc; color: #0f172a; }
    .react-sandbox-empty { max-width: 520px; margin: 48px auto; padding: 28px; border: 1px solid #cbd5e1; border-radius: 10px; background: #fff; }
    .react-sandbox-empty h3 { margin: 0 0 8px; }
    .react-sandbox-empty p { margin: 0; color: #64748b; }
    ${css}
  </style>
</head>
<body>
  <main data-migrated-preview="true">
    ${preview}
  </main>
</body>
</html>`;
  }, [code, css, fileName]);

  const isAngular = fileName.endsWith(".ts");
  const frameworkName = isAngular ? "Angular" : "React";

  return (
    <div className="react-sandbox-backdrop" role="dialog" aria-modal="true" aria-label={`Migrated ${frameworkName} page preview`}>
      <section className="react-sandbox-panel">
        <header className="react-sandbox-header">
          <div>
            <span className="react-sandbox-kicker">{frameworkName} sandbox</span>
            <h2>{fileName}</h2>
            <p>Generated JSP/JSF UI rendered with the migrated markup and available CSS.</p>
          </div>
          <button type="button" className="react-sandbox-close" onClick={onClose} aria-label="Close preview" title="Close preview">
            <FaTimes />
          </button>
        </header>
        <iframe
          className="react-sandbox-frame"
          title={`Preview of ${fileName}`}
          srcDoc={srcDoc}
          sandbox="allow-same-origin allow-scripts"
        />
        <footer className="react-sandbox-footer">
          Static UI preview. Bootstrap 4 injected for JSP style fidelity. API calls and event handlers require the migrated runtime.
        </footer>
      </section>
    </div>
  );
}
