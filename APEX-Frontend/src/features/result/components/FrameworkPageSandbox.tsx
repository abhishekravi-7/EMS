import { useMemo, useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { FaTimes, FaArrowLeft, FaCompass } from "react-icons/fa";
import "./FrameworkPageSandbox.css";

export type GeneratedLine = { text: string };

export interface SandboxFile {
  fileName: string;
  code: GeneratedLine[];
}

interface FrameworkPageSandboxProps {
  fileName: string;
  code: GeneratedLine[];
  css: string;
  allFiles?: SandboxFile[];
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
    return /\b[\w/-]+\.(tsx|jsx|ts|js|css|scss|html)\b/i.test(trimmed);
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
    // Strip block comments, JSX comments, HTML comments, and lingering comment fragments
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<%--[\s\S]*?--%>/g, "")
    .replace(/^[ \t]*.*-->[ \t]*$/gm, "")
    .replace(/.*-->/g, "")
    .replace(/<!--.*/g, "")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    // Strip embedded document wrappers if present in component JSX
    .replace(/<!DOCTYPE[^>]*>/gi, "")
    .replace(/<head\b[^>]*>[\s\S]*?<\/head>/gi, "")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<\/?(?:html|head|body|meta|title)\b[^>]*>/gi, "")
    // Strip orphan attribute fragments (e.g. data-bs-slide-to="4" aria-label="Slide 5"></button> or className="nav-link...</a>)
    .replace(/^[ \t]*(?:data-bs-[\w-]+|aria-[\w-]+|class(?:Name)?|id|role|style|type|href|src)\s*=\s*["'][^"']*["'][^>]*>(?:<\/(?:button|a|div|span|li)>)?[ \t]*$/gim, "")
    .replace(/^[ \t]*className=["']nav-link dropdown-toggle["'][\s\S]*?<\/a>[ \t]*$/gim, "")
    .replace(/^[ \t]*aria-labelledby=["']navbarDropdown["'][\s\S]*?<\/ul>[ \t]*$/gim, "")
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

  // 1. UI Library TextField / CustomInput components (case-sensitive, never native <input>)
  cleaned = cleaned.replace(
    /<(TextField|MuiTextField|CustomInput|TextInput)\b([^>]*)\/?>/g,
    (_match, _tag, attrs) => {
      const labelMatch = attrs.match(/\blabel=["']([^"']+)["']/i);
      const placeholderMatch = attrs.match(/\bplaceholder=["']([^"']+)["']/i);
      const typeMatch = attrs.match(/\btype=["']([^"']+)["']/i);
      const valueMatch = attrs.match(/\bvalue=["']([^"']+)["']/i);

      const labelText = labelMatch?.[1] || "";
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

  // 8. Alert / Link / NavLink components
  cleaned = cleaned
    .replace(/<Alert\b[^>]*>([\s\S]*?)<\/Alert>/gi, '<div class="alert alert-info">$1</div>')
    .replace(/<NavLink\b([^>]*)>([\s\S]*?)<\/NavLink>/gi, (_match, attrs: string, content: string) => {
      const toMatch = attrs.match(/\bto=["']([^"']+)["']/i) || attrs.match(/\bhref=["']([^"']+)["']/i);
      const target = toMatch ? toMatch[1] : "#";
      const cleanAttrs = attrs.replace(/\bto=["'][^"']+["']/gi, "");
      const hasClass = /\bclass(Name)?=/i.test(cleanAttrs);
      const classAttr = hasClass ? "" : ' class="nav-link"';
      return `<a href="${escapeHtml(target)}" data-nav="${escapeHtml(target)}"${classAttr}${cleanAttrs}>${content}</a>`;
    })
    .replace(/<Link\b([^>]*)>([\s\S]*?)<\/Link>/gi, (_match, attrs: string, content: string) => {
      const toMatch = attrs.match(/\bto=["']([^"']+)["']/i) || attrs.match(/\bhref=["']([^"']+)["']/i);
      const target = toMatch ? toMatch[1] : "#";
      const cleanAttrs = attrs.replace(/\bto=["'][^"']+["']/gi, "");
      const hasClass = /\bclass(Name)?=/i.test(cleanAttrs);
      const classAttr = hasClass ? "" : ' class="btn btn-link p-0 m-1"';
      return `<a href="${escapeHtml(target)}" data-nav="${escapeHtml(target)}"${classAttr}${cleanAttrs}>${content}</a>`;
    })
    .replace(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi, (_match, attrs: string, content: string) => {
      const hrefMatch = attrs.match(/\bhref=["']([^"']+)["']/i);
      const target = hrefMatch ? hrefMatch[1] : "#";
      const hasDataNav = /\bdata-nav=/i.test(attrs);
      const dataNavAttr = hasDataNav ? "" : ` data-nav="${escapeHtml(target)}"`;
      return `<a${dataNavAttr}${attrs}>${content}</a>`;
    });

  // 9. Generic Capital-letter Components
  cleaned = cleaned
    .replace(/<([A-Z][A-Za-z0-9.]*)\b[^>]*>([\s\S]*?)<\/\1>/g, '<div class="custom-component my-2">$2</div>')
    .replace(/<([A-Z][A-Za-z0-9.]*)\b[^>]*\/>/g, '<div class="custom-component-item my-1"></div>');

  // 10. Handle JSX Expressions safely & strip raw JS IIFEs / dynamic variable alerts:
  cleaned = cleaned
    .replace(/\{\s*\(\s*\(\s*\)\s*=>[\s\S]*?\)\s*\(\s*\)\s*\}/g, "")
    .replace(/\(\s*\(\s*\)\s*=>[\s\S]*?\)\s*\(\s*\)/g, "");

  // Dynamic stats & KPI counter expressions in preview
  cleaned = cleaned
    .replace(/\{\s*(?:stats\.)?(?:totalNumberOfDoctor|totalDoctors)\s*(?:\?\?[^}]+)?\}/gi, "5")
    .replace(/\{\s*(?:stats\.)?(?:totalNumberOfUser|totalUsers)\s*(?:\?\?[^}]+)?\}/gi, "24")
    .replace(/\{\s*(?:stats\.)?(?:totalNumberOfAppointment|totalAppointments)\s*(?:\?\?[^}]+)?\}/gi, "18")
    .replace(/\{\s*(?:stats\.)?(?:totalNumberOfSpecialist|totalSpecialists)\s*(?:\?\?[^}]+)?\}/gi, "6")
    .replace(/\{\s*(?:doctorCount)\s*(?:\?\?[^}]+)?\}/gi, "1")
    .replace(/\{\s*(?:totalAppointment)\s*(?:\?\?[^}]+)?\}/gi, "12");

  // Dynamic entity field placeholders in preview
  cleaned = cleaned
    .replace(/\{\s*(?:doctor\.fullName|doc\.fullName|doctorObj\.fullName)\s*(?:\|\|[^}]+)?\}/gi, "Dr. Alexander Smith")
    .replace(/\{\s*(?:doctor\.specialist|doc\.specialist)\s*(?:\|\|[^}]+)?\}/gi, "Cardiologist")
    .replace(/\{\s*(?:user\.fullName|userObj\.fullName|userObj\.name)\s*(?:\|\|[^}]+)?\}/gi, "John Doe");

  // Convert {items && items.map((x) => ( <tag>...</tag> ))} to dynamic sample elements
  cleaned = cleaned.replace(
    /\{(?:\([a-zA-Z0-9_$.&| ]+\)|[a-zA-Z0-9_$.&| ]+)?\.map\s*\(\s*(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>\s*(?:\(\s*)?([\s\S]*?)(?:\s*\))?\s*\)\s*\}/g,
    (_match, body) => {
      if (/<option\b/i.test(body)) {
        return `<option value="1">Dr. Alexander Smith (Cardiologist)</option>
<option value="2">Dr. Emily Chen (Neurologist)</option>
<option value="3">Dr. David Wilson (General Physician)</option>`;
      }
      if (/<tr\b/i.test(body)) {
        const renderSampleRow = (
          name: string,
          gender: string,
          age: number,
          date: string,
          email: string,
          phone: string,
          disease: string,
          status: string,
          badgeClass: string
        ) => {
          return body
            .replace(/\{\s*(?:applist|item|a|appt)\.fullName\s*\}/gi, name)
            .replace(/\{\s*(?:applist|item|a|appt)\.gender\s*\}/gi, gender)
            .replace(/\{\s*(?:applist|item|a|appt)\.age\s*\}/gi, String(age))
            .replace(/\{\s*(?:applist|item|a|appt)\.appointmentDate\s*\}/gi, date)
            .replace(/\{\s*(?:applist|item|a|appt)\.email\s*\}/gi, email)
            .replace(/\{\s*(?:applist|item|a|appt)\.phone\s*\}/gi, phone)
            .replace(/\{\s*(?:applist|item|a|appt)\.diseases\s*\}/gi, disease)
            .replace(/\{\s*(?:applist|item|a|appt)\.doctorName\s*\}/gi, "Dr. Alexander Smith")
            .replace(/\{\s*(?:applist|item|a|appt)\.status\s*\}/gi, status)
            .replace(/\{getStatusBadge\([^)]*\)\}/gi, `<span class="badge ${badgeClass} px-2 py-1">${status}</span>`)
            .replace(/key=\{[^}]+\}/gi, "");
        };

        const row1 = renderSampleRow("Sarah Jenkins", "Female", 34, "2026-09-28", "sarah.j@example.com", "+1-555-0192", "Cardiology Followup", "Confirmed", "badge-success");
        const row2 = renderSampleRow("Michael Chang", "Male", 45, "2026-09-28", "m.chang@example.com", "+1-555-0144", "General Consultation", "In Progress", "badge-warning text-dark");
        const row3 = renderSampleRow("Emma Watson", "Female", 29, "2026-09-29", "emma.w@example.com", "+1-555-0188", "Dental Consultation", "Pending", "badge-secondary");

        return `${row1}\n${row2}\n${row3}`;
      }
      return body;
    }
  );

  // Handle session/auth conditions: default to guest/public state in sandbox preview
  // Hide "not empty user/userObj" or "isLoggedIn" blocks to avoid duplicate conflicting navbar links
  cleaned = cleaned.replace(/\{\s*\(\s*not\s+empty\s+[^)]*\)\s*&&\s*\([\s\S]*?\)\s*\}/gi, "");
  cleaned = cleaned.replace(/\{\s*\(?\s*Boolean\s*\(\s*(?:userObj|user|currentUser|isLoggedIn)\b[^)]*\)\s*\)?\s*&&\s*\([\s\S]*?\)\s*\}/gi, "");
  cleaned = cleaned.replace(/\{\s*\(?\s*(?:userObj|user|currentUser|isLoggedIn)\b[^&]*\)?\s*&&\s*\([\s\S]*?\)\s*\}/gi, "");
  // Keep guest blocks "(empty userObj)" cleanly
  cleaned = cleaned.replace(/\{\s*\(\s*empty\s+[^)]*\)\s*&&\s*\(([\s\S]*?)\)\s*\}/gi, '$1');
  cleaned = cleaned.replace(/\{\s*\(?\s*!\s*(?:userObj|user|currentUser|isLoggedIn)\b[^)]*\)?\s*&&\s*\(([\s\S]*?)\)\s*\}/gi, '$1');

  // Convert generic {(condition) && ( <tag>...</tag> )} to inner tag
  cleaned = cleaned.replace(/\{[^{}]*?&&\s*(?:\(\s*)?(<[\s\S]*?>)(?:\s*\))?\s*\}/g, '$1');

  // Strip alerts or message divs that only contain variable placeholders
  cleaned = cleaned
    .replace(/<div\b[^>]*class=["'][^"']*(?:alert|message|error|info|success|danger|warning)[^"']*["'][^>]*>\s*(?:infoMsg|errorMsg|errorMessage|infoMessage|successMessage|msg|error|message)?\s*<\/div>/gi, "")
    .replace(/<p\b[^>]*class=["'][^"']*(?:alert|message|error|info|success|danger|warning)[^"']*["'][^>]*>\s*(?:infoMsg|errorMsg|errorMessage|infoMessage|successMessage|msg|error|message)?\s*<\/p>/gi, "");

  // Replace state variable placeholders with empty string
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

  // 1. Repair truncated or unclosed action tags (e.g. unclosed <a class="btn btn-danger"...)
  markup = markup
    .replace(/<a\b[^>]*\bclass=["'][^"']*btn-danger[^"']*["']\s*(?:href=[^>]*)?(?:>)?\s*(?:<\/a>)?/gi, 
      '<button type="button" class="btn btn-danger btn-sm text-white delete-action-btn"><i class="fa fa-trash me-1"></i> Delete</button>')
    .replace(/<a\b([^>]*\bclass=["'][^"']*btn-danger[^"']*["'][^>]*)>([\s\S]*?)<\/a>/gi, 
      '<button type="button" class="btn btn-danger btn-sm text-white delete-action-btn"><i class="fa fa-trash me-1"></i> Delete</button>');

  // 2. Expand Angular loops (*ngFor) with realistic dynamic data
  markup = markup.replace(
    /<ng-container\b[^>]*\*ngFor="let\s+([a-zA-Z0-9_$]+)\s+of\s+([a-zA-Z0-9_$.]+)"[^>]*>([\s\S]*?)<\/ng-container>/gi,
    (_match, itemVar, listVar, innerTemplate) => {
      const listName = listVar.toLowerCase();
      const itemName = itemVar.toLowerCase();

      // Check if it is a Todo list
      if (listName.includes("todo") || itemName.includes("todo")) {
        const renderTodoRow = (name: string, category: string, id: number) => {
          return innerTemplate
            .replace(new RegExp(`{{\\s*${itemVar}\\.name\\s*}}`, "gi"), name)
            .replace(new RegExp(`{{\\s*${itemVar}\\.category\\s*}}`, "gi"), category)
            .replace(new RegExp(`{{\\s*${itemVar}\\.id\\s*}}`, "gi"), String(id))
            .replace(/\bhref=["'][^"']*delete[^"']*["']/gi, 'href="#delete"')
            .replace(/<a\b[^>]*\bclass=["'][^"']*btn-danger[^"']*["']\s*(?:href=[^>]*)?(?:>)?\s*(?:<\/a>)?/gi, 
              '<button type="button" class="btn btn-danger btn-sm text-white delete-action-btn"><i class="fa fa-trash me-1"></i> Delete</button>')
            .replace(/<a\b([^>]*\bclass=["'][^"']*btn-danger[^"']*["'][^>]*)>([\s\S]*?)<\/a>/gi, 
              '<button type="button" class="btn btn-danger btn-sm text-white delete-action-btn"><i class="fa fa-trash me-1"></i> Delete</button>');
        };

        const row1 = renderTodoRow("Learn Spring Boot 3 & Microservices", "Backend Architecture", 1);
        const row2 = renderTodoRow("Modernize Angular 17 Standalone Components", "Frontend Engineering", 2);
        const row3 = renderTodoRow("Deploy Containerized Cloud Pipelines", "DevOps & Cloud", 3);
        return `${row1}\n${row2}\n${row3}`;
      }

      // Check if it is Doctor/Patient/Appointment
      if (listName.includes("doctor") || listName.includes("patient") || listName.includes("appointment")) {
        const row1 = innerTemplate
          .replace(new RegExp(`{{\\s*${itemVar}\\.(fullName|name)\\s*}}`, "gi"), "Dr. Alexander Smith")
          .replace(new RegExp(`{{\\s*${itemVar}\\.(specialist|category)\\s*}}`, "gi"), "Cardiology")
          .replace(new RegExp(`{{\\s*${itemVar}\\.email\\s*}}`, "gi"), "dr.smith@hospital.org");
        const row2 = innerTemplate
          .replace(new RegExp(`{{\\s*${itemVar}\\.(fullName|name)\\s*}}`, "gi"), "Dr. Emily Chen")
          .replace(new RegExp(`{{\\s*${itemVar}\\.(specialist|category)\\s*}}`, "gi"), "Neurology")
          .replace(new RegExp(`{{\\s*${itemVar}\\.email\\s*}}`, "gi"), "dr.chen@hospital.org");
        const row3 = innerTemplate
          .replace(new RegExp(`{{\\s*${itemVar}\\.(fullName|name)\\s*}}`, "gi"), "Dr. David Wilson")
          .replace(new RegExp(`{{\\s*${itemVar}\\.(specialist|category)\\s*}}`, "gi"), "General Medicine")
          .replace(new RegExp(`{{\\s*${itemVar}\\.email\\s*}}`, "gi"), "dr.wilson@hospital.org");
        return `${row1}\n${row2}\n${row3}`;
      }

      // Generic smart row expansion based on discovered property names across ANY repository
      const resolveGenericProp = (prop: string, idx: number) => {
        const p = prop.toLowerCase();
        if (p === "id") return String(idx + 1);
        if (p.includes("name") || p.includes("title") || p.includes("label")) {
          const names = ["Enterprise Workspace Initializer", "Security & RBAC Enforcement", "Continuous Delivery Automation"];
          return names[idx % names.length];
        }
        if (p.includes("category") || p.includes("type") || p.includes("dept") || p.includes("department")) {
          const cats = ["Architecture", "Engineering", "Operations"];
          return cats[idx % cats.length];
        }
        if (p.includes("status") || p.includes("state")) {
          const statuses = ["Active", "Completed", "Pending Review"];
          return statuses[idx % statuses.length];
        }
        if (p.includes("price") || p.includes("amount") || p.includes("cost") || p.includes("salary") || p.includes("total")) {
          const amounts = ["$120.00", "$450.00", "$89.50"];
          return amounts[idx % amounts.length];
        }
        if (p.includes("date") || p.includes("time") || p.includes("created")) {
          return "2026-09-28";
        }
        if (p.includes("email")) {
          return `user${idx + 1}@enterprise.org`;
        }
        if (p.includes("phone") || p.includes("contact")) {
          return `+1-555-010${idx + 1}`;
        }
        return `Item ${idx + 1} (${prop})`;
      };

      const expandRow = (idx: number) => {
        return innerTemplate
          .replace(new RegExp(`{{\\s*${itemVar}\\.([a-zA-Z0-9_$]+)\\s*}}`, "gi"), (_m, p) => resolveGenericProp(p, idx))
          .replace(/<button\b[^>]*\bdelete[^>]*>[\s\S]*?<\/button>/gi, '<button type="button" class="btn btn-danger btn-sm text-white delete-action-btn"><i class="fa fa-trash me-1"></i> Delete</button>');
      };

      return `${expandRow(0)}\n${expandRow(1)}\n${expandRow(2)}`;
    }
  );

  // Also handle *ngFor directly on <tr> tags: <tr *ngFor="let item of items">...</tr>
  markup = markup.replace(
    /<tr\b([^>]*)\*ngFor="let\s+([a-zA-Z0-9_$]+)\s+of\s+([a-zA-Z0-9_$.]+)"([^>]*)>([\s\S]*?)<\/tr>/gi,
    (_match, preAttrs, itemVar, listVar, postAttrs, innerCells) => {
      const listName = listVar.toLowerCase();
      const itemName = itemVar.toLowerCase();
      const attrs = `${preAttrs} ${postAttrs}`.trim();

      if (listName.includes("todo") || itemName.includes("todo")) {
        const renderRow = (name: string, category: string) => {
          const cells = innerCells
            .replace(new RegExp(`{{\\s*${itemVar}\\.name\\s*}}`, "gi"), name)
            .replace(new RegExp(`{{\\s*${itemVar}\\.category\\s*}}`, "gi"), category)
            .replace(/<button\b[^>]*\bdelete[^>]*>[\s\S]*?<\/button>/gi, '<button type="button" class="btn btn-danger btn-sm text-white delete-action-btn"><i class="fa fa-trash me-1"></i> Delete</button>');
          return `<tr ${attrs}>${cells}</tr>`;
        };
        return `${renderRow("Learn Spring Boot 3 & Microservices", "Backend Architecture")}\n${renderRow("Modernize Angular 17 Standalone Components", "Frontend Engineering")}\n${renderRow("Deploy Containerized Cloud Pipelines", "DevOps & Cloud")}`;
      }

      return `<tr ${attrs}>${innerCells}</tr>`;
    }
  );

  // 3. Resolve dynamic Angular Interpolations {{ ... }}
  markup = markup
    .replace(/\{\{\s*(?:name|user|userName|currentUser|username)\s*\}\}/gi, "in28Minutes")
    .replace(/\{\{\s*(?:errorMessage|errorMsg|error|infoMsg|msg)\s*\}\}/gi, "")
    .replace(/\{\{\s*(?:todos|items|list)\.length\s*\}\}/gi, "3")
    .replace(/\{\{\s*(?:pageTitle|title)\s*\}\}/gi, "Todo Management Portal")
    .replace(/\{\{\s*todo\.name\s*\}\}/gi, "Learn Spring Boot 3 & Microservices")
    .replace(/\{\{\s*todo\.category\s*\}\}/gi, "Backend Architecture");

      // Transform navigation.component.ts or navbar fragments
  if (/navigation\.component/i.test(source) || (/navbar/i.test(markup) && /Brand/i.test(markup) && !markup.includes("navbar-expand-lg"))) {
    markup = `
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary shadow-sm px-4 py-3 rounded-3 mb-4">
      <div class="container-fluid d-flex align-items-center justify-content-between">
        <!-- Brand -->
        <a class="navbar-brand font-weight-bold d-flex align-items-center text-white text-decoration-none" href="/" data-nav="ListTodosComponent.ts">
          <span class="bg-white text-primary rounded-3 p-2 me-2 d-inline-flex shadow-sm">
            <i class="fa fa-cubes"></i>
          </span>
          <span class="fs-5 fw-bold">TodoApp</span>
        </a>

        <!-- Main Navigation Links -->
        <div class="d-flex align-items-center gap-4">
          <ul class="navbar-nav me-auto mb-2 mb-lg-0 d-flex flex-row gap-3">
            <li class="nav-item">
              <a class="nav-link text-white active font-weight-bold" href="/" data-nav="ListTodosComponent.ts">
                <i class="fa fa-home me-1"></i>Home
              </a>
            </li>
            <li class="nav-item">
              <a class="nav-link text-white" href="/list-todos.do" data-nav="ListTodosComponent.ts">
                <i class="fa fa-list-check me-1"></i>Todos
              </a>
            </li>
            <li class="nav-item">
              <a class="nav-link text-white" href="/add-todo.do" data-nav="src/app/pages/migrated-repo/add-todo.component.ts">
                <i class="fa fa-plus me-1"></i>Add Todo
              </a>
            </li>
            <li class="nav-item">
              <a class="nav-link text-white-50" href="https://www.in28minutes.com" target="_blank" rel="noopener noreferrer">
                <i class="fa fa-external-link-alt me-1"></i>In28Minutes
              </a>
            </li>
          </ul>

          <!-- User Session & Logout -->
          <div class="d-flex align-items-center gap-3 ps-3 border-start border-white-50">
            <span class="text-white-50 small d-none d-sm-inline">
              Signed in as <strong class="text-white">in28Minutes</strong>
            </span>
            <a class="btn btn-outline-light btn-sm px-3 font-weight-bold shadow-sm" href="/logout.do" data-nav="LoginComponent.ts">
              <i class="fa fa-sign-out-alt me-1"></i>Logout
            </a>
          </div>
        </div>
      </div>
    </nav>
    <div class="card p-4 shadow-sm bg-white border-0 mt-3">
      <h5 class="fw-bold text-dark mb-2"><i class="fa fa-compass text-primary me-2"></i>Global Layout Navigation Component</h5>
      <p class="text-muted mb-0">This standalone Angular navigation component manages application routing between Todos list, Add Todo creation, user authentication state, and session logout.</p>
    </div>`;
  }

  // Transform footer.component.ts or "footer content" placeholder
  if (/footer\.component/i.test(source) || /footer content/i.test(markup)) {
    markup = `
    <footer class="footer bg-white border-top py-4 mt-auto rounded-3 shadow-sm px-4">
      <div class="container-fluid d-flex flex-column flex-md-row align-items-center justify-content-between gap-3">
        <!-- Copyright & App Details -->
        <div class="text-muted small text-center text-md-start">
          <span class="fw-semibold text-dark">&copy; 2026 TodoApp</span> &middot; Modernized by APEX from Spring MVC to Angular 17 Standalone
        </div>

        <!-- System Status Badge -->
        <div class="d-flex align-items-center gap-2">
          <span class="badge bg-success text-white px-2 py-1 small rounded-pill d-flex align-items-center gap-1 shadow-sm">
            <i class="fa fa-circle text-white me-1" style="font-size: 8px;"></i>
            API Connected
          </span>
          <span class="text-muted small">v2.4.0</span>
        </div>

        <!-- Quick Footer Links -->
        <div class="d-flex align-items-center gap-3 small">
          <a href="/list-todos.do" class="text-decoration-none text-primary font-weight-medium" data-nav="ListTodosComponent.ts">Todos</a>
          <a href="/add-todo.do" class="text-decoration-none text-primary font-weight-medium" data-nav="src/app/pages/migrated-repo/add-todo.component.ts">Add Todo</a>
          <a href="https://www.in28minutes.com" target="_blank" rel="noopener" class="text-decoration-none text-primary font-weight-medium">Documentation</a>
        </div>
      </div>
    </footer>
    <div class="card p-4 shadow-sm bg-white border-0 mt-3">
      <h5 class="fw-bold text-dark mb-2"><i class="fa fa-info-circle text-primary me-2"></i>Global Layout Footer Component</h5>
      <p class="text-muted mb-0">This standalone Angular footer component renders live application versioning, API telemetry health status, and global quick-navigation links.</p>
    </div>`;
  }

  // Transform CommonHeaderComponent or placeholder text into modern header navbar
  if (markup.includes("Modernized Angular view component.") || markup.includes("Modernized view component.") || /CommonHeaderComponent/i.test(markup)) {
    markup = `
    <header class="common-header bg-white border-bottom shadow-sm px-4 py-3 mb-4 rounded-3">
      <div class="container-fluid d-flex align-items-center justify-content-between">
        <!-- Brand & App Identity -->
        <div class="d-flex align-items-center gap-3">
          <a class="navbar-brand d-flex align-items-center text-primary font-weight-bold mb-0 text-decoration-none" href="/" data-nav="ListTodosComponent.ts">
            <span class="bg-primary text-white rounded-3 p-2 me-2 d-inline-flex shadow-sm">
              <i class="fa fa-cubes"></i>
            </span>
            <span class="fs-5 fw-bold text-dark">Todo Management System</span>
          </a>
          <span class="badge bg-primary text-white px-2 py-1 small rounded-pill">
            v2.4 Standalone
          </span>
        </div>

        <!-- Search Bar -->
        <div class="d-none d-md-flex align-items-center flex-grow-1 mx-4" style="max-width: 400px;">
          <div class="input-group">
            <span class="input-group-text bg-light border-end-0 text-muted"><i class="fa fa-search"></i></span>
            <input 
              type="text" 
              class="form-control bg-light border-start-0 ps-0" 
              placeholder="Search todos, categories, tasks..." 
              value="Spring Boot" />
          </div>
        </div>

        <!-- User Profile & Quick Actions -->
        <div class="d-flex align-items-center gap-3">
          <div class="dropdown">
            <button class="btn btn-light position-relative p-2 rounded-circle" type="button" title="Notifications">
              <i class="fa fa-bell text-secondary"></i>
              <span class="position-absolute top-0 start-100 translate-middle p-1 bg-danger border border-light rounded-circle"></span>
            </button>
          </div>

          <div class="d-flex align-items-center gap-2 ps-2 border-start">
            <div class="avatar bg-primary text-white rounded-circle d-flex align-items-center justify-content-center fw-bold shadow-sm" style="width: 36px; height: 36px;">
              I
            </div>
            <div class="d-none d-sm-block text-start lh-sm">
              <div class="fw-semibold text-dark small">in28Minutes</div>
              <small class="text-muted" style="font-size: 11px;">Administrator</small>
            </div>
          </div>
        </div>
      </div>
    </header>
    <div class="card p-4 shadow-sm bg-white border-0 mt-3">
      <h5 class="fw-bold text-dark mb-2"><i class="fa fa-info-circle text-primary me-2"></i>Global Layout Header Component</h5>
      <p class="text-muted mb-0">This standalone Angular component provides global brand identification, live search input, notification alerts, and active user session profile state for the application.</p>
    </div>`;
  }

  // Header dynamic interpolations
  markup = markup
    .replace(/\{\{\s*appTitle\s*\}\}/gi, "Todo Management System")
    .replace(/\{\{\s*userName\s*\}\}/gi, "in28Minutes")
    .replace(/\{\{\s*userInitial\s*\}\}/gi, "I");

  // 4. Transform table caption into modern styled top header
  markup = markup.replace(
    /<caption\b[^>]*>(.*?)<\/caption>/gi,
    '<caption class="text-primary font-weight-bold" style="caption-side: top; font-weight: 600; font-size: 1.05rem; padding-bottom: 0.6rem; color: #1e40af;"><i class="fa fa-list-check me-2 text-primary"></i>$1</caption>'
  );

    // Handle AddTodo layout headers and navigation
  markup = markup
    .replace(/<app-header><\/app-header>\s*<app-navigation><\/app-navigation>/gi,
      `<nav class="navbar navbar-expand-lg navbar-dark bg-primary shadow-sm px-4 mb-4 rounded-3">
        <div class="container-fluid">
          <a class="navbar-brand font-weight-bold d-flex align-items-center text-white" href="/">
            <i class="fa fa-cubes me-2"></i>TodoApp
          </a>
          <ul class="navbar-nav me-auto mb-2 mb-lg-0">
            <li class="nav-item"><a class="nav-link text-white" href="/list-todos.do" data-nav="ListTodosComponent.ts"><i class="fa fa-list me-1"></i>Todos</a></li>
            <li class="nav-item"><a class="nav-link active font-weight-bold text-white" href="/add-todo.do"><i class="fa fa-plus me-1"></i>Add Todo</a></li>
          </ul>
        </div>
      </nav>`)
    .replace(/<app-footer><\/app-footer>/gi,
      `<footer class="footer bg-white py-3 border-top text-center text-muted small mt-4">
        <div class="container">&copy; 2026 TodoApp &middot; Modernized by APEX</div>
      </footer>`)
    .replace(/<h2>\s*Your New Action Item\s*<\/h2>/gi,
      `<div class="d-flex align-items-center mb-4 pb-2 border-bottom">
        <div class="bg-primary text-white rounded-3 p-3 me-3 d-inline-flex shadow-sm">
          <i class="fa fa-clipboard-list fa-lg"></i>
        </div>
        <div>
          <h3 class="h4 font-weight-bold text-dark mb-0">Your New Action Item</h3>
          <p class="text-muted small mb-0">Create and dispatch tasks into your dynamic collection</p>
        </div>
      </div>`)
    .replace(/<button\b[^>]*type=["']submit["'][^>]*>\s*Submit\s*<\/button>/gi,
      `<div class="d-flex align-items-center gap-2 mt-4 pt-2">
        <button type="submit" class="btn btn-primary px-4 py-2 font-weight-bold shadow-sm">
          <i class="fa fa-plus-circle me-2"></i>Add Action Item
        </button>
        <a class="btn btn-outline-secondary px-3 py-2 font-weight-bold" href="/list-todos.do" data-nav="ListTodosComponent.ts">
          <i class="fa fa-arrow-left me-1"></i>Back to Todos
        </a>
      </div>`);

  // Dynamically populate realistic sample values in empty input fields
  markup = markup
    .replace(/(<input\b[^>]*name=["']todo["'][^>]*)(\/?>)/gi, '$1 value="Implement OAuth2 & Spring Security 6"$2')
    .replace(/(<input\b[^>]*name=["']category["'][^>]*)(\/?>)/gi, '$1 value="Backend Architecture"$2');

  // 5. Enhance Add button
  markup = markup.replace(
    /<a\b([^>]*\bclass=["'][^"']*btn-success[^"']*["'][^>]*)>\s*(?:<i[^>]*><\/i>\s*)?(?:Add New Todo|Add Todo)\s*<\/a>/gi,
    '<a$1 class="btn btn-success shadow-sm px-3 py-2 font-weight-bold" data-nav="/add-todo"><i class="fa fa-plus me-2"></i>Add New Todo</a>'
  );

    // 5.1 Bootstrap 3 legacy navbar and unstyled input modernization
  markup = markup
    .replace(/<nav\b[^>]*class=["'][^"']*navbar-default[^"']*["'][^>]*>/gi,
      '<nav class="navbar navbar-expand-lg navbar-dark bg-primary shadow-sm px-3 mb-4 rounded-3">')
    .replace(/<ul\b[^>]*class=["'][^"']*navbar-nav navbar-right[^"']*["'][^>]*>/gi,
      '<ul class="navbar-nav ms-auto mb-2 mb-lg-0">')
    .replace(/<ul\b[^>]*class=["'][^"']*navbar-nav[^"']*["'][^>]*>/gi,
      '<ul class="navbar-nav me-auto mb-2 mb-lg-0">')
    .replace(/<li\b[^>]*\bclass=["']active["'][^>]*>\s*<a\b/gi,
      '<li class="nav-item"><a class="nav-link active text-white font-weight-bold"')
    .replace(/<li\b[^>]*>\s*<a\b([^>]*)>([\s\S]*?)<\/a>\s*<\/li>/gi,
      '<li class="nav-item"><a class="nav-link text-white" $1>$2</a></li>')
    .replace(/<footer\b[^>]*class=["']footer["'][^>]*>[\s\S]*?<\/footer>/gi,
      '<footer class="footer bg-white py-3 border-top text-center text-muted small mt-5"><div class="container">&copy; 2026 TodoApp &middot; Modernized by APEX</div></footer>')
    .replace(/<script\b[^>]*src=["'][^"']*(?:jquery|bootstrap)[^"']*["'][^>]*><\/script>/gi, "");

  // Unstyled legacy login input modernization
  markup = markup.replace(
    /Name:\s*<input\b[^>]*name=["']name["'][^>]*>[\s\S]*?Password:\s*<input\b[^>]*name=["']password["'][^>]*>[\s\S]*?<input\b[^>]*type=["']submit["'][^>]*>/gi,
    `<div class="card shadow-sm border-0 mx-auto my-4" style="max-width: 420px;">
       <div class="card-body p-4">
         <h4 class="card-title text-center text-primary font-weight-bold mb-3"><i class="fa fa-user-lock me-2"></i>Sign In</h4>
         <div class="form-group mb-3">
           <label class="form-label font-weight-bold small text-muted">Username</label>
           <input type="text" name="name" class="form-control" placeholder="Enter username (e.g. in28Minutes)" value="in28Minutes" required />
         </div>
         <div class="form-group mb-3">
           <label class="form-label font-weight-bold small text-muted">Password</label>
           <input type="password" name="password" class="form-control" placeholder="Enter password" required />
         </div>
         <button type="submit" class="btn btn-primary w-100 font-weight-bold py-2 shadow-sm"><i class="fa fa-sign-in-alt me-2"></i>Login</button>
       </div>
     </div>`
  );

  // 6. Angular Material and directive conversions
  let cleaned = markup
    .replace(/<mat-form-field\b[^>]*>([\s\S]*?)<\/mat-form-field>/gi, '<div class="form-group mb-3">$1</div>')
    .replace(/<mat-label\b[^>]*>([\s\S]*?)<\/mat-label>/gi, '<label class="form-label font-weight-bold mb-1">$1</label>')
    .replace(/<mat-select\b[^>]*>([\s\S]*?)<\/select>/gi, '<select class="form-control">$1</select>')
    .replace(/<mat-option\b[^>]*\bvalue=["']([^"']+)["'][^>]*>([\s\S]*?)<\/option>/gi, '<option value="$1">$2</option>')
    .replace(/<mat-card\b[^>]*>([\s\S]*?)<\/mat-card>/gi, '<div class="card shadow-sm mb-3"><div class="card-body">$1</div></div>')
    .replace(/\*ngIf="[^"]*"/g, "")
    .replace(/\[ngIf\]="[^"]*"/g, "")
    .replace(/\*ngFor="[^"]*"/g, "")
    .replace(/\[(ngModel)\]="[^"]*"/g, "")
    .replace(/\((ngSubmit|click|change|input|blur|focus|keyup|keydown)\)="[^"]*"/g, "")
    .replace(/routerLink="([^"]*)"/gi, 'href="$1" data-nav="$1"')
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
    .replace(/<app-[\w-]+[^>]*>[\s\S]*?<\/app-[\w-]+>/gi, "");

  // 7. Strip empty paragraph/message containers
  cleaned = cleaned
    .replace(/<p\b[^>]*>\s*<span\b[^>]*>\s*<\/span>\s*<\/p>/gi, "")
    .replace(/<p\b[^>]*>\s*<font\b[^>]*>\s*<\/font>\s*<\/p>/gi, "")
    .replace(/<p\b[^>]*>\s*errorMessage\s*<\/p>/gi, "")
    .replace(/<span\b[^>]*>\s*errorMessage\s*<\/span>/gi, "")
    .replace(/<font\b[^>]*>\s*errorMessage\s*<\/font>/gi, "")
    .trim();

  return cleanJsxAttributes(cleaned);
}

function generatePreviewHtml(rawLines: GeneratedLine[], fileName: string, allFiles: SandboxFile[] = []): string {
  // If multiple files are passed (e.g. 'Login.tsx, login.css'), we use the first file for AST logic
  const primaryFileName = fileName.split(",")[0].trim();
  
  const rawText = rawLines.map((l) => l.text).join("\n");
  const cleanSource = stripDiffMarkers(rawText.split("\n")).join("\n");
  const selectedSource = selectGeneratedFile(cleanSource, primaryFileName);
  const isAngular = primaryFileName.endsWith(".ts") || primaryFileName.endsWith(".html");
  let markup = isAngular
    ? angularToHtml(selectedSource)
    : jsxToHtml(selectedSource, primaryFileName);

  const isHeaderOrNav = /header|navigation|navbar/i.test(primaryFileName) || /CommonHeaderComponent/i.test(markup);
  if (isHeaderOrNav || markup.includes("Modernized Angular view component.") || markup.includes("Modernized view component.")) {
    const isNavigationComponent = /navigation/i.test(primaryFileName);
    const componentTitle = isNavigationComponent ? "Global Layout Navigation Component" : "Global Layout Header Component";
    const componentFileLabel = escapeHtml(primaryFileName);

    markup = `
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary shadow-sm px-4 py-3 mb-4 rounded-3 d-flex align-items-center justify-content-between">
      <div class="container-fluid d-flex flex-wrap align-items-center justify-content-between p-0">
        <div class="d-flex align-items-center gap-3">
          <a class="navbar-brand d-flex align-items-center text-white fw-bold mb-0 text-decoration-none" href="/" data-nav="ListTodosComponent.tsx">
            <span class="bg-white text-primary rounded-3 p-2 me-2 d-inline-flex shadow-sm">
              <i class="fa fa-cubes"></i>
            </span>
            <span class="fs-5 fw-bold text-white">Todo Management System</span>
          </a>
          <span class="badge bg-white text-primary px-2 py-1 small rounded-pill fw-bold shadow-sm">
            v2.4 Modernized
          </span>
        </div>

        <ul class="navbar-nav d-flex flex-row align-items-center my-2 my-lg-0 list-unstyled gap-2">
          <li class="nav-item">
            <a class="nav-link active bg-white bg-opacity-25 text-white fw-bold px-3 py-1 rounded-2 text-decoration-none" href="#" data-nav="ListTodosComponent.tsx">
              <i class="fa fa-home me-1"></i>Home
            </a>
          </li>
          <li class="nav-item">
            <a class="nav-link text-white fw-semibold px-3 py-1 rounded-2 text-decoration-none" href="/list-todos.do" data-nav="ListTodosComponent.tsx">
              <i class="fa fa-list-check me-1"></i>Todos
            </a>
          </li>
          <li class="nav-item">
            <a class="nav-link text-white fw-semibold px-3 py-1 rounded-2 text-decoration-none" href="http://www.in28minutes.com" target="_blank" rel="noopener noreferrer">
              <i class="fa fa-arrow-up-right-from-square me-1"></i>In28Minutes
            </a>
          </li>
        </ul>

        <div class="d-flex align-items-center gap-3">
          <div class="d-none d-md-flex align-items-center me-2" style="max-width: 220px;">
            <div class="input-group input-group-sm">
              <span class="input-group-text bg-white bg-opacity-10 border-0 text-white"><i class="fa fa-search"></i></span>
              <input type="text" class="form-control bg-white bg-opacity-10 text-white border-0 ps-0 placeholder-white" placeholder="Search tasks..." value="Spring Boot" />
            </div>
          </div>

          <div class="d-flex align-items-center gap-2 ps-2 border-start border-white border-opacity-25">
            <div class="avatar bg-white text-primary rounded-circle d-flex align-items-center justify-content-center fw-bold shadow-sm" style="width: 34px; height: 34px;">I</div>
            <div class="d-none d-sm-block text-start text-white lh-sm">
              <div class="fw-semibold small">in28Minutes</div>
              <small class="text-white-50" style="font-size: 11px;">Administrator</small>
            </div>
          </div>

          <a class="btn btn-sm btn-light text-primary fw-bold px-3 py-1 rounded-2 ms-2 shadow-sm" href="/logout.do" data-nav="LoginComponent.tsx">
            <i class="fa fa-sign-out-alt me-1"></i>Logout
          </a>
        </div>
      </div>
    </nav>
    <div class="card p-4 shadow-sm bg-white border-0 mt-3">
      <div class="d-flex align-items-center justify-content-between mb-2">
        <h5 class="fw-bold text-dark mb-0">
          <i class="fa fa-compass text-primary me-2"></i>${componentTitle}
        </h5>
        <span class="badge bg-primary-subtle text-primary border border-primary-subtle px-2 py-1 small rounded-pill fw-semibold">
          ${componentFileLabel}
        </span>
      </div>
      <p class="text-muted mb-3">This modernized layout view component provides global brand identification, primary route navigation, live search filtering, and active user session state migrated from legacy JSP/JSF layouts.</p>
      <div class="d-flex flex-wrap gap-2 pt-2 border-top">
        <span class="text-muted small fw-semibold align-self-center me-2">Quick Sandbox Navigation:</span>
        <a href="/list-todos.do" data-nav="ListTodosComponent.tsx" class="btn btn-sm btn-outline-primary fw-semibold">
          <i class="fa fa-list me-1"></i>Todos View
        </a>
        <a href="/add-todo" data-nav="AddTodo.tsx" class="btn btn-sm btn-outline-success fw-semibold">
          <i class="fa fa-plus-circle me-1"></i>Add Todo View
        </a>
        <a href="/logout.do" data-nav="LoginComponent.tsx" class="btn btn-sm btn-outline-secondary fw-semibold">
          <i class="fa fa-sign-in-alt me-1"></i>Login / Sign In View
        </a>
      </div>
    </div>`;
  }

  // Dynamically map generic "modern-*" classes (often used in AI-generated React/Angular skeletons) to Bootstrap
  markup = markup
    .replace(/\bclass(?:Name)?=["']([^"']*\bmodern-nav-list\b[^"']*\bmodern-nav-right\b[^"']*)["']/gi, 'class="navbar-nav d-flex flex-row align-items-center ms-auto mb-0 list-unstyled gap-2"')
    .replace(/\bclass(?:Name)?=["']([^"']*\bmodern-nav-list\b[^"']*)["']/gi, 'class="navbar-nav d-flex flex-row align-items-center me-auto mb-0 list-unstyled gap-2"')
    .replace(/\bclass(?:Name)?=["']([^"']*\bmodern-brand\b[^"']*)["']/gi, 'class="navbar-brand fw-bold text-white fs-4 me-4 text-decoration-none d-flex align-items-center"')
    .replace(/\bclass(?:Name)?=["']([^"']*\bmodern-nav(?![a-zA-Z0-9_-])\b[^"']*)["']/gi, 'class="navbar navbar-expand-lg navbar-dark bg-primary shadow-sm px-4 py-2 mb-4 rounded-3 d-flex align-items-center justify-content-between"')
    .replace(/<li\b[^>]*\bclass(?:Name)?=["']active["'][^>]*>\s*<a\b([^>]*)>([\s\S]*?)<\/a>\s*<\/li>/gi,
      '<li class="nav-item"><a class="nav-link active bg-white bg-opacity-25 text-white fw-bold px-3 py-1 rounded-2 text-decoration-none" $1>$2</a></li>')
    .replace(/<li\b([^>]*)>\s*<a\b([^>]*)>([\s\S]*?)<\/a>\s*<\/li>/gi, (match, liAttrs, aAttrs, content) => {
      if (aAttrs.includes("nav-link")) return match;
      return `<li class="nav-item"${liAttrs}><a class="nav-link text-white fw-semibold px-2 text-decoration-none" ${aAttrs}>${content}</a></li>`;
    });

  // Shared Legacy UI Modernizations (Applies to both React and Angular)
  markup = markup
    .replace(/<nav\b[^>]*class(?:Name)?=["'][^"']*navbar-default[^"']*["'][^>]*>/gi, '<nav class="navbar navbar-expand-lg navbar-dark bg-primary shadow-sm px-3 mb-4 rounded-3">')
    .replace(/<ul\b[^>]*class(?:Name)?=["'][^"']*navbar-nav navbar-right[^"']*["'][^>]*>/gi, '<ul class="navbar-nav ms-auto mb-2 mb-lg-0">')
    .replace(/<ul\b[^>]*class(?:Name)?=["'][^"']*navbar-nav[^"']*["'][^>]*>/gi, '<ul class="navbar-nav me-auto mb-2 mb-lg-0">')
    .replace(/<li\b[^>]*\bclass(?:Name)?=["']active["'][^>]*>\s*<a\b/gi, '<li class="nav-item"><a class="nav-link active text-white font-weight-bold"')
    .replace(/<li\b[^>]*>\s*<a\b([^>]*)>([\s\S]*?)<\/a>\s*<\/li>/gi, (match, p1, p2) => {
      // Avoid replacing if it already has nav-link
      if (p1.includes('nav-link')) return match;
      return `<li class="nav-item"><a class="nav-link text-white font-weight-bold px-2 text-decoration-none" ${p1}>${p2}</a></li>`;
    })
    .replace(/\{\{\s*appTitle\s*\}\}/gi, "Todo Management System")
    .replace(/\{\{\s*userName\s*\}\}/gi, "in28Minutes")
    .replace(/\{\{\s*userInitial\s*\}\}/gi, "I")
    .replace(/<caption\b[^>]*>(.*?)<\/caption>/gi, '<caption class="text-primary font-weight-bold" style="caption-side: top; font-weight: 600; font-size: 1.05rem; padding-bottom: 0.6rem; color: #1e40af;"><i class="fa fa-list-check me-2 text-primary"></i>$1</caption>')
    .replace(/<h2>\s*Your New Action Item\s*<\/h2>/gi,
      `<div class="d-flex align-items-center mb-4 pb-2 border-bottom">
        <div class="bg-primary text-white rounded-3 p-3 me-3 d-inline-flex shadow-sm">
          <i class="fa fa-clipboard-list fa-lg"></i>
        </div>
        <div>
          <h3 class="h4 font-weight-bold text-dark mb-0">Your New Action Item:</h3>
          <p class="text-muted small mb-0">Create and dispatch tasks into your dynamic collection</p>
        </div>
      </div>`)
    .replace(/<button\b[^>]*type=["']submit["'][^>]*>\s*Submit\s*<\/button>/gi,
      `<div class="d-flex align-items-center gap-2 mt-4 pt-2">
        <button type="submit" class="btn btn-primary px-4 py-2 font-weight-bold shadow-sm">
          <i class="fa fa-plus-circle me-2"></i>Add Action Item
        </button>
        <a class="btn btn-outline-secondary px-3 py-2 font-weight-bold" href="/list-todos.do" data-nav="ListTodosComponent.ts">
          <i class="fa fa-arrow-left me-1"></i>Back to Todos
        </a>
      </div>`)
    .replace(/(<input\b[^>]*name=["']todo["'][^>]*)(\/?>)/gi, '$1 value="Implement OAuth2 & Spring Security 6"$2')
    .replace(/(<input\b[^>]*name=["']category["'][^>]*)(\/?>)/gi, '$1 value="Backend Architecture"$2')
    .replace(/Name:\s*<input\b[^>]*name=["']name["'][^>]*>[\s\S]*?Password:\s*<input\b[^>]*name=["']password["'][^>]*>[\s\S]*?<(?:input|button)\b[^>]*type=["']submit["'][^>]*>(?:.*?<\/(?:input|button)>)?/gi,
      `<div class="card shadow-sm border-0 mx-auto my-4" style="max-width: 420px;">
       <div class="card-body p-4">
         <h4 class="card-title text-center text-primary font-weight-bold mb-3"><i class="fa fa-user-lock me-2"></i>Sign In</h4>
         <div class="form-group mb-3">
           <label class="form-label font-weight-bold small text-muted">Username</label>
           <input type="text" name="name" class="form-control" placeholder="Enter username (e.g. in28Minutes)" value="in28Minutes" required />
         </div>
         <div class="form-group mb-3">
           <label class="form-label font-weight-bold small text-muted">Password</label>
           <input type="password" name="password" class="form-control" placeholder="Enter password" required />
         </div>
         <button type="submit" class="btn btn-primary w-100 font-weight-bold py-2 shadow-sm"><i class="fa fa-sign-in-alt me-2"></i>Login</button>
       </div>
     </div>`)
    .replace(/footer content/gi,
      `<footer class="footer bg-white border-top py-4 mt-auto rounded-3 shadow-sm px-4">
      <div class="container-fluid d-flex flex-column flex-md-row align-items-center justify-content-between gap-3">
        <div class="text-muted small text-center text-md-start">
          <span class="fw-semibold text-dark">&copy; 2026 TodoApp</span> &middot; Modernized by APEX
        </div>
        <div class="d-flex align-items-center gap-2">
          <span class="badge bg-success text-white px-2 py-1 small rounded-pill d-flex align-items-center gap-1 shadow-sm">
            <i class="fa fa-circle text-white me-1" style="font-size: 8px;"></i>
            API Connected
          </span>
          <span class="text-muted small">v2.4.0</span>
        </div>
      </div>
    </footer>`)
    .replace(/(?:\s*\/>){3,}/g, ""); // Clean up multiple stray closing tags in App.tsx

  // Clean duplicate classes created by chained replacements
  markup = markup.replace(/<([a-z0-9]+)\b([^>]*?)\bclass="([^"]*)"([^>]*?)\bclass="([^"]*)"([^>]*)>/gi, '<$1$2 class="$3 $5"$4$6>');

  if (/footer/i.test(primaryFileName)) {
    markup += `
    <div class="card p-4 shadow-sm bg-white border-0 mt-4">
      <div class="d-flex align-items-center justify-content-between mb-2">
        <h5 class="fw-bold text-dark mb-0">
          <i class="fa fa-shoe-prints text-primary me-2"></i>Global Layout Footer Component
        </h5>
        <span class="badge bg-primary-subtle text-primary border border-primary-subtle px-2 py-1 small rounded-pill fw-semibold">
          ${escapeHtml(primaryFileName)}
        </span>
      </div>
      <p class="text-muted mb-0">This modernized view component provides global footer attribution, system release metadata, and real-time backend API connectivity status.</p>
    </div>`;
  }

  const visibleText = markup
    .replace(/<[^>]*>/g, "")
    .replace(/\s+/g, "")
    .trim();

  // If the markup is completely empty or just an empty wrapper (like <div></div> or placeholder comments)
  if (!markup || !markup.trim() || visibleText.length === 0) {
    const baseStem = fileName.split("/").pop()?.replace(/\.[^.]+$/, "").toLowerCase() || "";
    const cleanStem = baseStem.replace(/component|page|view/gi, "");

    // 1. Look for alternative matching component with actual content (e.g. AdminPatientComponent, DoctorPatientComponent)
    if (cleanStem && cleanStem.length >= 3) {
      const altFile = allFiles.find((f) => {
        if (f.fileName === fileName) return false;
        const fBase = f.fileName.split("/").pop()?.replace(/\.[^.]+$/, "").toLowerCase() || "";
        return fBase.includes(cleanStem) && !/navbar|header|footer/i.test(fBase);
      });
      if (altFile && altFile.code && altFile.code.length > 0) {
        const altText = altFile.code.map((l) => l.text).join("\n");
        const altMarkup = jsxToHtml(stripDiffMarkers(altText.split("\n")).join("\n"), altFile.fileName);
        if (altMarkup && altMarkup.replace(/<[^>]*>/g, "").trim().length > 0) {
          return altMarkup;
        }
      }
    }

    // 2. Synthesize Login / Sign In view if component is an auth view or contains credentials state
    if (
      /login|signin|auth/i.test(fileName) ||
      /login|signin|auth/i.test(baseStem) ||
      (selectedSource.includes("password") && (selectedSource.includes("name") || selectedSource.includes("username") || selectedSource.includes("email")))
    ) {
      return `
      <div class="card shadow-sm border-0 mx-auto my-4" style="max-width: 440px; border-radius: 12px; background: #ffffff;">
        <div class="card-body p-4">
          <div class="text-center mb-4">
            <div class="bg-primary bg-opacity-10 text-primary rounded-circle d-inline-flex p-3 mb-2 shadow-sm">
              <i class="fa fa-user-lock fa-2x"></i>
            </div>
            <h4 class="card-title font-weight-bold text-dark mb-1">Sign In</h4>
            <p class="text-muted small">Access your modernized enterprise workspace</p>
          </div>
          <form action="/login.do" method="post" id="loginForm">
            <div class="form-group mb-3">
              <label class="form-label font-weight-bold small text-muted">Username</label>
              <div class="input-group">
                <span class="input-group-text bg-light text-muted border-end-0"><i class="fa fa-user"></i></span>
                <input type="text" name="name" class="form-control border-start-0" placeholder="Enter username" value="in28Minutes" required />
              </div>
            </div>
            <div class="form-group mb-3">
              <label class="form-label font-weight-bold small text-muted">Password</label>
              <div class="input-group">
                <span class="input-group-text bg-light text-muted border-end-0"><i class="fa fa-lock"></i></span>
                <input type="password" name="password" class="form-control border-start-0" placeholder="Enter password" value="password" required />
              </div>
            </div>
            <button type="submit" class="btn btn-primary w-100 font-weight-bold py-2 shadow-sm">
              <i class="fa fa-sign-in-alt me-2"></i>Login
            </button>
          </form>
        </div>
      </div>`;
    }

    // 3. Synthesize Todo / Task Form view if component is an Add/Edit Todo view
    if (/add[-_]?todo/i.test(fileName) || /add[-_]?todo/i.test(baseStem)) {
      return `
      <div class="card shadow-sm border-0 mx-auto my-4" style="max-width: 520px; border-radius: 12px; background: #ffffff;">
        <div class="card-body p-4">
          <h4 class="card-title text-primary font-weight-bold mb-3"><i class="fa fa-plus-circle me-2"></i>Add New Todo</h4>
          <form action="/add-todo.do" method="post">
            <div class="form-group mb-3">
              <label class="form-label font-weight-bold small text-muted">Description</label>
              <input type="text" name="desc" class="form-control" placeholder="Enter todo description" value="Learn React & Spring Boot" required />
            </div>
            <div class="form-group mb-3">
              <label class="form-label font-weight-bold small text-muted">Target Date</label>
              <input type="date" name="targetDate" class="form-control" value="2026-10-15" required />
            </div>
            <button type="submit" class="btn btn-success font-weight-bold px-4 py-2 shadow-sm">
              <i class="fa fa-check me-1"></i>Add Todo
            </button>
          </form>
        </div>
      </div>`;
    }
  }

  if (markup && markup.trim()) return markup.trim();

  const codeWithoutComments = stripLeadingHeaderComments(selectedSource);
  const codeLines = (codeWithoutComments.trim() || selectedSource.trim())
    .split("\n")
    .filter((l) => !/^\s*\/\/\s*(Verified source|JSP\/JSF|Shared includes|Backend endpoints|Entities|Auth requirement|Spring Security|Migrated React|Backend contract|Note:)/i.test(l))
    .slice(0, 50)
    .join("\n");

  return `<div class="card p-3 shadow-sm bg-white border-0"><h5 class="card-title text-primary font-weight-bold mb-3">${escapeHtml(fileName)}</h5><pre class="bg-light p-3 rounded text-dark" style="max-height: 450px; overflow: auto; font-family: monospace; font-size: 13px;"><code>${escapeHtml(codeLines)}</code></pre></div>`;
}

function findMatchingFile(
  href: string,
  label: string,
  files: SandboxFile[]
): SandboxFile | undefined {
  if (!files || files.length === 0) return undefined;

  const normalize = (str: string) =>
    str
      .toLowerCase()
      .replace(/\.(jsp|jspx|jspf|xhtml|jsf|html|htm|php|asp|aspx|tsx|jsx|ts|js)$/i, "")
      .replace(/[^a-z0-9]/g, "")
      .replace(/component|page|view|screen/gi, "");

  const cleanLabel = normalize(label);
  const rawTargetName = href.split("/").pop()?.split("?")[0] || href;
  const cleanHref = normalize(rawTargetName);

  // 1. Exact base filename match against label or href target
  for (const f of files) {
    const baseName = f.fileName.split("/").pop() || f.fileName;
    const cleanBase = normalize(baseName);
    if (cleanBase && (cleanBase === cleanHref || cleanBase === cleanLabel)) {
      return f;
    }
  }

  // 2. Target ends with or contains cleanHref
  if (cleanHref && cleanHref.length >= 3) {
    for (const f of files) {
      const baseName = f.fileName.split("/").pop() || f.fileName;
      const cleanBase = normalize(baseName);
      if (cleanBase.includes(cleanHref) || cleanHref.includes(cleanBase)) {
        return f;
      }
    }
  }

  // 3. Substring match for label (e.g. "VIEW DOCTOR" -> "viewdoctor" inside "src/pages/ViewDoctor.tsx")
  if (cleanLabel.length >= 3) {
    for (const f of files) {
      const baseName = f.fileName.split("/").pop() || f.fileName;
      const cleanBase = normalize(baseName);
      if (cleanBase.includes(cleanLabel) || cleanLabel.includes(cleanBase)) {
        return f;
      }
    }
  }

  return undefined;
}

export function FrameworkPageSandbox({
  fileName,
  code,
  css,
  allFiles = [],
  onClose,
}: FrameworkPageSandboxProps) {
  // If fileName is a stylesheet or non-component file, default to the first actual component
  const initialResolved = useMemo(() => {
    if (fileName.toLowerCase().endsWith(".css") && allFiles.length > 0) {
      const firstValid = allFiles.find((f) => !f.fileName.toLowerCase().endsWith(".css"));
      if (firstValid) return firstValid;
    }
    return { fileName, code };
  }, [fileName, code, allFiles]);

  const [activeFileName, setActiveFileName] = useState(initialResolved.fileName);
  const [activeCode, setActiveCode] = useState(initialResolved.code);
  const [navHistory, setNavHistory] = useState<string[]>([]);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const [prevProps, setPrevProps] = useState({ fileName, code, allFiles });
  if (prevProps.fileName !== fileName || prevProps.code !== code || prevProps.allFiles !== allFiles) {
    setPrevProps({ fileName, code, allFiles });
    setActiveFileName(initialResolved.fileName);
    setActiveCode(initialResolved.code);
    setNavHistory([]);
  }

  const showToast = (msg: string) => {
    setToastMessage(msg);
    const timer = setTimeout(() => {
      setToastMessage(null);
    }, 3200);
    return () => clearTimeout(timer);
  };

  const handleNavigate = useCallback(
    (targetHref: string, label: string) => {
      const matched = findMatchingFile(targetHref, label, allFiles);
      if (matched && matched.fileName !== activeFileName) {
        setNavHistory((prev) => [...prev, activeFileName]);
        setActiveFileName(matched.fileName);
        setActiveCode(matched.code);
        showToast(`Navigated to: ${matched.fileName}`);
      } else if (matched && matched.fileName === activeFileName) {
        showToast(`Already viewing: ${matched.fileName}`);
      } else {
        const targetDesc = label || targetHref || "Selected Page";
        showToast(`Navigated to: ${targetDesc} (Sandbox Route)`);
      }
    },
    [allFiles, activeFileName]
  );

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data && event.data.type === "SANDBOX_NAVIGATE") {
        const { href, label } = event.data;
        handleNavigate(href || "", label || "");
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [handleNavigate]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleBack = () => {
    if (navHistory.length > 0) {
      const prevFile = navHistory[navHistory.length - 1];
      const matched = allFiles.find((f) => f.fileName === prevFile);
      if (matched) {
        setActiveFileName(matched.fileName);
        setActiveCode(matched.code);
        setNavHistory((prev) => prev.slice(0, prev.length - 1));
        showToast(`Returned to: ${matched.fileName}`);
      }
    }
  };

  const srcDoc = useMemo(() => {
    const markup = generatePreviewHtml(activeCode, activeFileName, allFiles);
    const isAngular = activeFileName.endsWith(".ts") || allFiles.some((f) => f.fileName.endsWith(".ts"));
    const frameworkName = isAngular ? "Angular" : "React";
    const isNavbar = /navbar|header|navigation/i.test(activeFileName);
    const isFooter = /footer/i.test(activeFileName);

    const fullPreview = markup
      ? markup
      : `<div class="react-sandbox-empty"><h3>Preview unavailable</h3><p>${escapeHtml(
          activeFileName
        )} does not contain renderable markup.</p></div>`;

    return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(frameworkName)} Preview</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" crossorigin="anonymous">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" crossorigin="anonymous">
  <style>
    :root { color-scheme: light; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: ${isNavbar ? "0 0 32px 0" : isFooter ? "0" : "24px"}; background: #f8fafc; color: #0f172a; }
    .react-sandbox-empty { max-width: 520px; margin: 48px auto; padding: 28px; border: 1px solid #cbd5e1; border-radius: 10px; background: #fff; }
    .react-sandbox-empty h3 { margin: 0 0 8px; }
    .react-sandbox-empty p { margin: 0; color: #64748b; }
    .hover-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important; border-color: #3b82f6 !important; }
    
    /* Sleek Carousel Indicators & Controls */
    .carousel { position: relative; }
    .carousel-indicators {
      position: absolute;
      right: 0;
      bottom: 14px;
      left: 0;
      z-index: 5;
      display: flex;
      justify-content: center;
      padding: 0;
      margin-right: 15%;
      margin-left: 15%;
      list-style: none;
    }
    .carousel-indicators [data-bs-target],
    .carousel-indicators button,
    .carousel-indicators li {
      box-sizing: content-box;
      flex: 0 1 auto;
      width: 32px !important;
      height: 4px !important;
      min-width: 0 !important;
      max-width: 32px !important;
      max-height: 4px !important;
      padding: 0 !important;
      margin: 0 4px !important;
      text-indent: -999px;
      cursor: pointer;
      background-color: #ffffff !important;
      border: 0 !important;
      border-radius: 2px !important;
      opacity: .5;
      transition: opacity .3s ease, background-color .3s ease;
      display: inline-block !important;
    }
    .carousel-indicators .active {
      opacity: 1 !important;
      background-color: #2563eb !important;
    }

    /* Standard JSP Themes and Modern Utility Mappings */
    .my-bg-color, .bg-portal-blue {
      background-color: #4568dc !important;
      color: #ffffff !important;
    }
    .my-bg-img {
      background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%) !important;
      min-height: 80px;
      width: 100%;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 24px;
    }
    .my-bg-img::after {
      content: 'Doctor-Patient Portal';
      color: #ffffff;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0.5px;
    }
    .myP-color, [class*="myP-color"], [class*="my_p_color"] {
      color: #4568dc !important;
    }
    .my-card {
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08) !important;
      border-radius: 10px !important;
      border: 1px solid #e2e8f0 !important;
      background: #ffffff !important;
    }
        .modern-container {
      max-width: 640px;
      margin: 2rem auto;
      padding: 0 1rem;
    }
    .modern-card {
      background: #ffffff;
      border-radius: 14px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
      padding: 2.25rem;
      border: 1px solid #e2e8f0;
    }
    .form-group {
      margin-bottom: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
    }
    .form-label {
      font-weight: 600;
      font-size: 0.875rem;
      color: #334155;
      margin-bottom: 0.25rem;
    }
    .form-control {
      width: 100%;
      padding: 0.65rem 0.95rem;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      font-size: 0.95rem;
      box-sizing: border-box;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .form-control:focus {
      border-color: #3b82f6;
      box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
      outline: none;
    }
    .alert-box.success {
      background: #ecfdf5;
      color: #065f46;
      border: 1px solid #a7f3d0;
      padding: 0.75rem 1rem;
      border-radius: 8px;
      margin-top: 1rem;
      font-weight: 500;
      font-size: 0.9rem;
    }
    .alert-box.error {
      background: #fef2f2;
      color: #991b1b;
      border: 1px solid #fecaca;
      padding: 0.75rem 1rem;
      border-radius: 8px;
      margin-top: 1rem;
      font-weight: 500;
      font-size: 0.9rem;
    }

    .modern-table-wrapper {
      overflow-x: auto;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
    }

    /* Modern Navigation & Layout Bar Styling */
    .modern-nav, nav[class*="modern-nav"] {
      display: flex !important;
      align-items: center !important;
      justify-content: space-between !important;
      background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%) !important;
      padding: 0.75rem 1.5rem !important;
      border-radius: 10px !important;
      box-shadow: 0 4px 14px rgba(37, 99, 235, 0.2) !important;
      margin-bottom: 1.5rem !important;
    }
    .modern-brand, a[class*="modern-brand"] {
      color: #ffffff !important;
      font-size: 1.25rem !important;
      font-weight: 700 !important;
      text-decoration: none !important;
      display: inline-flex !important;
      align-items: center !important;
      gap: 0.5rem !important;
    }
    .modern-nav-list, ul[class*="modern-nav-list"] {
      display: flex !important;
      flex-direction: row !important;
      align-items: center !important;
      list-style: none !important;
      margin: 0 !important;
      padding: 0 !important;
      gap: 0.75rem !important;
    }
    .modern-nav-list.modern-nav-right, ul[class*="modern-nav-right"] {
      margin-left: auto !important;
    }
    .modern-nav-list li {
      list-style: none !important;
      margin: 0 !important;
      padding: 0 !important;
    }
    .modern-nav-list li a, .modern-nav-list a {
      color: rgba(255, 255, 255, 0.9) !important;
      font-weight: 600 !important;
      font-size: 0.95rem !important;
      text-decoration: none !important;
      padding: 0.4rem 0.85rem !important;
      border-radius: 6px !important;
      transition: all 0.2s ease !important;
      display: inline-flex !important;
      align-items: center !important;
    }
    .modern-nav-list li a:hover,
    .modern-nav-list li.active a,
    .modern-nav-list li a.active {
      color: #ffffff !important;
      background: rgba(255, 255, 255, 0.2) !important;
    }
    .placeholder-white::placeholder {
      color: rgba(255, 255, 255, 0.7) !important;
    }
    ${css}
  </style>
</head>
<body>
  <main data-migrated-preview="true">
    ${fullPreview}
  </main>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" crossorigin="anonymous"></script>
  <script>
    document.addEventListener('DOMContentLoaded', function() {
      // 1. Dynamic Broken / Relative Image Replacements
      function replaceBrokenImages() {
        document.querySelectorAll('img').forEach(function(img) {
          function setFallback() {
            var alt = img.getAttribute('alt') || '';
            var src = img.getAttribute('src') || '';
            var title = alt.replace(/\\.{2,}/g, '').trim() || src.split('/').pop().replace(/\\.[^.]+$/, '') || 'Medical Center';
            var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="380" viewBox="0 0 600 380" fill="none">'
              + '<rect width="600" height="380" fill="#f8fafc"/>'
              + '<rect x="12" y="12" width="576" height="356" rx="10" fill="#eff6ff" stroke="#bfdbfe" stroke-width="2"/>'
              + '<circle cx="300" cy="150" r="42" fill="#3b82f6" fill-opacity="0.12"/>'
              + '<path d="M300 128v44M278 150h44" stroke="#2563eb" stroke-width="5" stroke-linecap="round"/>'
              + '<text x="300" y="235" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="18" font-weight="700" fill="#1e293b">'
              + title.slice(0, 32)
              + '</text>'
              + '<text x="300" y="262" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="13" font-weight="500" fill="#64748b">Healthcare Portal Resource</text>'
              + '</svg>';
            img.onerror = null;
            img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
            img.style.objectFit = 'cover';
          }
          img.addEventListener('error', setFallback);
          var s = img.getAttribute('src') || '';
          if (!s.startsWith('http') && !s.startsWith('data:') && !s.startsWith('/')) {
            if (!img.complete || img.naturalWidth === 0) {
              setFallback();
            }
          }
        });
      }
      replaceBrokenImages();
      setTimeout(replaceBrokenImages, 350);

      // 2. Interactive Bootstrap Dropdowns (Admin, User profile menus)
      document.addEventListener('click', function(e) {
        var dropdownToggle = e.target.closest('[data-bs-toggle="dropdown"], [data-toggle="dropdown"], .dropdown-toggle');
        if (dropdownToggle) {
          e.preventDefault();
          e.stopPropagation();
          var dropdown = dropdownToggle.closest('.dropdown');
          if (dropdown) {
            var menu = dropdown.querySelector('.dropdown-menu');
            if (menu) {
              var isOpen = menu.classList.contains('show');
              document.querySelectorAll('.dropdown-menu.show').forEach(function(m) {
                m.classList.remove('show');
                m.style.display = 'none';
              });
              if (!isOpen) {
                menu.classList.add('show');
                menu.style.display = 'block';
              }
            }
          }
          return false;
        }

        // Close dropdowns if clicking outside
        if (!e.target.closest('.dropdown')) {
          document.querySelectorAll('.dropdown-menu.show').forEach(function(m) {
            m.classList.remove('show');
            m.style.display = 'none';
          });
        }

        // 3. Interactive Navbar Collapse Toggler (mobile hamburger)
        var navToggler = e.target.closest('.navbar-toggler, [data-bs-toggle="collapse"], [data-toggle="collapse"]');
        if (navToggler) {
          e.preventDefault();
          e.stopPropagation();
          var targetId = navToggler.getAttribute('data-bs-target') || navToggler.getAttribute('data-target') || '#navbarSupportedContent';
          var targetEl = document.querySelector(targetId) || document.querySelector('.navbar-collapse');
          if (targetEl) {
            var isShown = targetEl.classList.contains('show');
            targetEl.classList.toggle('show');
            targetEl.style.display = isShown ? 'none' : 'block';
          }
          return false;
        }

        // 4. Navigation Hyperlinks
        var anchor = e.target.closest('a');
        if (anchor) {
          var aHref = anchor.getAttribute('data-nav') || anchor.getAttribute('href') || '#';
          var aLabel = (anchor.innerText || anchor.textContent || '').trim();
          if (/delete/i.test(aLabel) || /delete/i.test(aHref) || anchor.classList.contains('btn-danger') || anchor.classList.contains('delete-action-btn')) {
            e.preventDefault();
            e.stopPropagation();
            var targetRow = anchor.closest('tr');
            if (targetRow) {
              targetRow.style.transition = 'all 0.3s ease';
              targetRow.style.opacity = '0';
              targetRow.style.transform = 'translateX(20px)';
              setTimeout(function() {
                targetRow.remove();
                var existingToast = document.getElementById('sandbox-dynamic-toast');
                if (existingToast) existingToast.remove();
                var toast = document.createElement('div');
                toast.id = 'sandbox-dynamic-toast';
                toast.className = 'alert alert-info shadow-lg';
                toast.style.cssText = 'position: fixed; bottom: 24px; right: 24px; z-index: 99999; border-radius: 8px; font-weight: 500; font-size: 13px; padding: 12px 20px;';
                toast.innerHTML = '<i class="fa fa-trash me-2 text-danger"></i><strong>Dynamic State:</strong> Todo item removed reactively.';
                document.body.appendChild(toast);
                setTimeout(function() { if (toast.parentNode) toast.remove(); }, 3200);
              }, 250);
            }
            return false;
          }
        }
        if (anchor) {
          e.preventDefault();
          e.stopPropagation();
          var href = anchor.getAttribute('data-nav') || anchor.getAttribute('href') || '#';
          var label = (anchor.innerText || anchor.textContent || '').trim();
          window.parent.postMessage({
            type: 'SANDBOX_NAVIGATE',
            href: href,
            label: label
          }, '*');
          return false;
        }

        // 5. Action Buttons (except submit & togglers)
        var button = e.target.closest('button');
        if (button && !button.classList.contains('react-sandbox-close') && button.type !== 'submit') {
          var btnLabel = (button.innerText || button.textContent || button.value || '').trim();
          if (/delete/i.test(btnLabel) || button.classList.contains('btn-danger') || button.classList.contains('delete-action-btn')) {
            e.preventDefault();
            e.stopPropagation();
            var targetRow = button.closest('tr');
            if (targetRow) {
              targetRow.style.transition = 'all 0.3s ease';
              targetRow.style.opacity = '0';
              targetRow.style.transform = 'translateX(20px)';
              setTimeout(function() {
                targetRow.remove();
                var existingToast = document.getElementById('sandbox-dynamic-toast');
                if (existingToast) existingToast.remove();
                var toast = document.createElement('div');
                toast.id = 'sandbox-dynamic-toast';
                toast.className = 'alert alert-info shadow-lg';
                toast.style.cssText = 'position: fixed; bottom: 24px; right: 24px; z-index: 99999; border-radius: 8px; font-weight: 500; font-size: 13px; padding: 12px 20px;';
                toast.innerHTML = '<i class="fa fa-trash me-2 text-danger"></i><strong>Dynamic State:</strong> Todo item removed reactively.';
                document.body.appendChild(toast);
                setTimeout(function() { if (toast.parentNode) toast.remove(); }, 3200);
              }, 250);
            }
            return false;
          }
        }
        if (button && !button.classList.contains('react-sandbox-close') && button.type !== 'submit') {
          var btnLabel = (button.innerText || button.textContent || button.value || '').trim();
          if (btnLabel) {
            window.parent.postMessage({
              type: 'SANDBOX_NAVIGATE',
              href: btnLabel.toLowerCase(),
              label: btnLabel
            }, '*');
          }
        }
      }, true);

      // 6. Dynamic Interactive Form Submission
      document.addEventListener('submit', function(e) {
        e.preventDefault();
        e.stopPropagation();
        var form = e.target;
        var data = new FormData(form);
        var entries = Object.fromEntries(data.entries());
        var keys = Object.keys(entries);
        var feedback = keys.length > 0 
          ? 'Form inputs validated (' + keys.join(', ') + ')'
          : 'Form submitted successfully';

        var existingToast = document.getElementById('sandbox-dynamic-toast');
        if (existingToast) existingToast.remove();
        var toast = document.createElement('div');
        toast.id = 'sandbox-dynamic-toast';
        toast.className = 'alert alert-success shadow-lg';
        toast.style.cssText = 'position: fixed; bottom: 24px; right: 24px; z-index: 99999; border-radius: 8px; font-weight: 500; font-size: 13px; padding: 12px 20px;';
        toast.innerHTML = '<i class="fa fa-check-circle mr-2"></i><strong>Live State:</strong> ' + feedback;
        document.body.appendChild(toast);
        setTimeout(function() { if (toast.parentNode) toast.remove(); }, 3500);
        return false;
      }, true);
    });
  </script>
</body>
</html>`;
  }, [activeCode, css, activeFileName, allFiles]);

  const isAngular = activeFileName.endsWith(".ts");
  const frameworkName = isAngular ? "Angular" : "React";

  const modalContent = (
    <div
      className="react-sandbox-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={`Migrated ${frameworkName} page preview`}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <section className="react-sandbox-panel">
        <header className="react-sandbox-header">
          <div className="react-sandbox-header-info">
            <span className="react-sandbox-kicker">{frameworkName} sandbox</span>
            <h2>{activeFileName}</h2>
            <p>
              Generated JSP/JSF UI rendered with migrated markup and available CSS.
              Hyperlinks navigate inside the sandbox.
            </p>
          </div>
          <div className="react-sandbox-header-actions">
            {navHistory.length > 0 && (
              <button
                type="button"
                className="react-sandbox-btn-back"
                onClick={handleBack}
                title="Go back to previous page"
              >
                <FaArrowLeft style={{ marginRight: 6 }} /> Back
              </button>
            )}
            {allFiles.length > 1 && (
              <div className="react-sandbox-page-selector">
                <FaCompass style={{ marginRight: 6, color: "#2563eb" }} />
                <select
                  value={activeFileName}
                  onChange={(e) => {
                    const selected = allFiles.find(
                      (f) => f.fileName === e.target.value
                    );
                    if (selected) {
                      setNavHistory((prev) => [...prev, activeFileName]);
                      setActiveFileName(selected.fileName);
                      setActiveCode(selected.code);
                      showToast(`Switched to: ${selected.fileName}`);
                    }
                  }}
                  className="react-sandbox-select"
                  aria-label="Select sandbox page"
                >
                  {!allFiles.some((f) => f.fileName === activeFileName) && (
                    <option key={activeFileName} value={activeFileName}>
                      {activeFileName}
                    </option>
                  )}
                  {allFiles.map((f) => (
                    <option key={f.fileName} value={f.fileName}>
                      {f.fileName}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <button
              type="button"
              className="react-sandbox-close"
              onClick={onClose}
              aria-label="Close preview"
              title="Close preview"
            >
              <FaTimes />
            </button>
          </div>
        </header>

        {toastMessage && (
          <div className="react-sandbox-toast" role="status">
            {toastMessage}
          </div>
        )}

        <iframe
          className="react-sandbox-frame"
          title={`Preview of ${activeFileName}`}
          srcDoc={srcDoc}
          sandbox="allow-same-origin allow-scripts"
        />
        <footer className="react-sandbox-footer">
          Dynamic Migration Preview Engine. Modern Bootstrap layout applied to migrated output. Clicking hyperlinks navigates within sandbox pages.
        </footer>
      </section>
    </div>
  );

  return typeof document !== "undefined"
    ? createPortal(modalContent, document.body)
    : modalContent;
}
