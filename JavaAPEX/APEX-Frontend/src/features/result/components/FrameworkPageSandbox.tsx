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

function findFileForComponent(compName: string, files: SandboxFile[]): SandboxFile | undefined {
  if (!compName || !files || files.length === 0) return undefined;
  const targetNorm = compName.toLowerCase().replace(/[^a-z0-9]/g, "");

  // 1. Exact or normalized filename match
  for (const f of files) {
    const baseName = f.fileName.split("/").pop()?.replace(/\.[^.]+$/, "") || "";
    const baseNorm = baseName.toLowerCase().replace(/[^a-z0-9]/g, "");
    if (baseNorm === targetNorm) return f;
  }

  // 2. Substring or component stem match
  for (const f of files) {
    const baseName = f.fileName.split("/").pop()?.replace(/\.[^.]+$/, "") || "";
    const baseNorm = baseName.toLowerCase().replace(/[^a-z0-9]/g, "");
    if (baseNorm.length >= 3 && targetNorm.length >= 3) {
      if (baseNorm.includes(targetNorm) || targetNorm.includes(baseNorm)) {
        return f;
      }
    }
  }

  return undefined;
}

function getFaIconClass(tagName: string): string {
  const lower = tagName.toLowerCase();
  if (lower.includes("delete") || lower.includes("trash")) return "fa-trash";
  if (lower.includes("edit") || lower.includes("pencil") || lower.includes("write")) return "fa-edit";
  if (lower.includes("search") || lower.includes("find")) return "fa-search";
  if (lower.includes("user") || lower.includes("person") || lower.includes("account")) return "fa-user";
  if (lower.includes("add") || lower.includes("plus") || lower.includes("create")) return "fa-plus";
  if (lower.includes("lock") || lower.includes("security") || lower.includes("key")) return "fa-lock";
  if (lower.includes("calendar") || lower.includes("date") || lower.includes("event")) return "fa-calendar";
  if (lower.includes("mail") || lower.includes("email") || lower.includes("envelope")) return "fa-envelope";
  if (lower.includes("check") || lower.includes("confirm") || lower.includes("success")) return "fa-check";
  if (lower.includes("close") || lower.includes("times") || lower.includes("cancel")) return "fa-times";
  if (lower.includes("phone") || lower.includes("call") || lower.includes("mobile")) return "fa-phone";
  if (lower.includes("home") || lower.includes("house")) return "fa-home";
  if (lower.includes("file") || lower.includes("doc") || lower.includes("page")) return "fa-file-alt";
  if (lower.includes("setting") || lower.includes("cog") || lower.includes("gear")) return "fa-cog";
  if (lower.includes("bell") || lower.includes("notice") || lower.includes("alert")) return "fa-bell";
  if (lower.includes("list") || lower.includes("menu")) return "fa-list";
  return "fa-circle-info";
}

function convertUiLibraryTag(tag: string, attrs: string, children: string): string | null {
  const lowerTag = tag.toLowerCase();

  if (["card", "paper", "muipaper", "mat-card"].includes(lowerTag)) {
    return `<div class="card shadow-sm mb-3"><div class="card-body p-4">${children}</div></div>`;
  }
  if (lowerTag === "cardcontent") {
    return `<div class="card-body p-4">${children}</div>`;
  }
  if (lowerTag === "cardactions") {
    return `<div class="card-footer bg-transparent border-0 d-flex gap-2">${children}</div>`;
  }
  if (["box", "container", "muibox", "muicontainer", "stack", "flex"].includes(lowerTag)) {
    const isRow = /\b(?:direction=["']row["']|flex-row|row)\b/i.test(attrs);
    const flexClass = isRow ? "d-flex flex-row align-items-center gap-3 my-2" : "container my-2";
    return `<div class="${flexClass}">${children}</div>`;
  }
  if (lowerTag === "grid") {
    if (/\bcontainer\b/i.test(attrs)) {
      return `<div class="row g-3 my-2">${children}</div>`;
    }
    return `<div class="col">${children}</div>`;
  }
  if (["table", "mat-table"].includes(lowerTag)) {
    return `<div class="table-responsive my-3"><table class="table table-bordered table-striped align-middle mb-0">${children}</table></div>`;
  }
  if (["tablehead", "thead"].includes(lowerTag)) {
    return `<thead class="table-light">${children}</thead>`;
  }
  if (["tablebody", "tbody"].includes(lowerTag)) {
    return `<tbody>${children}</tbody>`;
  }
  if (["tablerow", "tr"].includes(lowerTag)) {
    return `<tr>${children}</tr>`;
  }
  if (["tablecell", "td", "th"].includes(lowerTag)) {
    const isHeader = /\bcomponent=["']th["']/i.test(attrs) || lowerTag === "th";
    return isHeader ? `<th class="fw-bold text-dark">${children}</th>` : `<td>${children}</td>`;
  }
  if (["tablecontainer"].includes(lowerTag)) {
    return `<div class="table-responsive my-3 shadow-sm rounded-3 bg-white p-2">${children}</div>`;
  }
  if (["typography"].includes(lowerTag)) {
    const variantMatch = attrs.match(/\bvariant=["'](h[1-6]|subtitle[12]|body[12])["']/i);
    const v = variantMatch ? variantMatch[1].toLowerCase() : "div";
    if (v.startsWith("h")) return `<${v} class="fw-bold text-dark my-2">${children}</${v}>`;
    return `<div class="typography-body my-1">${children}</div>`;
  }
  if (["button", "muibutton", "form.button", "submitbutton"].includes(lowerTag)) {
    const isSubmit = /\btype=["']submit["']/i.test(attrs);
    const btnType = isSubmit ? "submit" : "button";
    return `<button type="${btnType}" class="btn btn-primary px-4 py-2 fw-bold shadow-sm m-1">${children}</button>`;
  }
  if (["select", "mat-select"].includes(lowerTag)) {
    const labelMatch = attrs.match(/\blabel=["']([^"']+)["']/i);
    const labelText = labelMatch ? labelMatch[1] : "";
    const labelHtml = labelText ? `<label class="form-label fw-bold mb-1">${escapeHtml(labelText)}</label>` : "";
    return `<div class="form-group mb-3">${labelHtml}<select class="form-select">${children}</select></div>`;
  }
  if (["menuitem", "option", "mat-option"].includes(lowerTag)) {
    const valMatch = attrs.match(/\bvalue=["']([^"']+)["']/i);
    const val = valMatch ? ` value="${escapeHtml(valMatch[1])}"` : "";
    return `<option${val}>${children}</option>`;
  }
  if (["alert"].includes(lowerTag)) {
    const severityMatch = attrs.match(/\bseverity=["'](error|warning|info|success)["']/i);
    const sev = severityMatch ? severityMatch[1].toLowerCase() : "info";
    const alertClass = sev === "error" ? "danger" : sev;
    return `<div class="alert alert-${alertClass} shadow-sm my-2">${children}</div>`;
  }
  if (["dialog", "modal"].includes(lowerTag)) {
    return `<div class="modal d-block position-static my-3"><div class="modal-dialog modal-lg"><div class="modal-content shadow-lg">${children}</div></div></div>`;
  }
  if (["dialogtitle", "modalheader"].includes(lowerTag)) {
    return `<div class="modal-header bg-primary text-white"><h5 class="modal-title fw-bold">${children}</h5></div>`;
  }
  if (["dialogcontent", "modalbody"].includes(lowerTag)) {
    return `<div class="modal-body p-4">${children}</div>`;
  }
  if (["dialogactions", "modalfooter"].includes(lowerTag)) {
    return `<div class="modal-footer bg-light">${children}</div>`;
  }
  if (["chip", "badge"].includes(lowerTag)) {
    return `<span class="badge bg-primary px-2.5 py-1.5 rounded-pill">${children}</span>`;
  }
  if (["avatar"].includes(lowerTag)) {
    return `<div class="avatar bg-primary text-white rounded-circle d-inline-flex align-items-center justify-content-center fw-bold me-2" style="width: 38px; height: 38px;">${children || "U"}</div>`;
  }

  return null;
}

function convertUiLibrarySelfClosingTag(tag: string, attrs: string): string | null {
  const lowerTag = tag.toLowerCase();

  if (["textfield", "muitextfield", "custominput", "textinput", "input"].includes(lowerTag)) {
    const labelMatch = attrs.match(/\blabel=["']([^"']+)["']/i);
    const placeholderMatch = attrs.match(/\bplaceholder=["']([^"']+)["']/i);
    const typeMatch = attrs.match(/\btype=["']([^"']+)["']/i);
    const valueMatch = attrs.match(/\bvalue=["']([^"']+)["']/i);
    const nameMatch = attrs.match(/\bname=["']([^"']+)["']/i) || attrs.match(/\bid=["']([^"']+)["']/i);

    const labelText = labelMatch?.[1] || "";
    const inputType = typeMatch?.[1] || "text";
    const placeholder = placeholderMatch?.[1] || labelText || "Enter text";
    const nameAttr = nameMatch ? ` name="${escapeHtml(nameMatch[1])}"` : "";
    const val = valueMatch?.[1] ? ` value="${escapeHtml(valueMatch[1])}"` : "";

    const labelHtml = labelText ? `<label class="form-label fw-bold mb-1">${escapeHtml(labelText)}</label>` : "";
    return `<div class="form-group mb-3">${labelHtml}<input type="${escapeHtml(inputType)}" class="form-control"${nameAttr} placeholder="${escapeHtml(placeholder)}"${val} /></div>`;
  }

  if (["button", "muibutton", "iconbutton"].includes(lowerTag)) {
    return `<button type="button" class="btn btn-primary px-3 py-2 fw-bold shadow-sm m-1"><i class="fa ${getFaIconClass(tag)} me-1"></i> Submit</button>`;
  }

  if (
    lowerTag.includes("icon") ||
    lowerTag.startsWith("fa") ||
    lowerTag.startsWith("md") ||
    ["delete", "edit", "search", "user", "add", "plus", "check", "close", "lock"].some((k) => lowerTag.includes(k))
  ) {
    return `<i class="fa ${getFaIconClass(tag)}"></i>`;
  }

  return null;
}

function inlineChildComponents(markup: string, allFiles: SandboxFile[], depth = 0): string {
  if (!markup || depth > 3 || !allFiles || allFiles.length === 0) return markup;

  const htmlTags = new Set([
    "div", "span", "p", "a", "button", "input", "select", "option", "textarea",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6", "header", "footer", "nav", "main",
    "section", "article", "aside", "form", "label", "img", "i", "b", "strong",
    "em", "small", "code", "pre", "hr", "br", "iframe", "svg", "path", "circle"
  ]);

  // 1. Resolve React Router <Route path="..." element={<ChildComponent />} />
  let result = markup.replace(
    /<Route\b[^>]*\belement=\{\s*<([A-Z][A-Za-z0-9_]*)\b[^>]*\/>\s*\}[^>]*\/?>/gi,
    (_match, compName) => {
      const matchedFile = findFileForComponent(compName, allFiles);
      if (matchedFile) {
        const childCode = stripDiffMarkers(matchedFile.code.map((l) => l.text));
        const childHtml = jsxToHtml(childCode.join("\n"), matchedFile.fileName, allFiles, depth + 1);
        if (childHtml.trim()) return childHtml;
      }
      return `<div class="route-block my-3"><h5 class="fw-bold text-primary"><i class="fa fa-layer-group me-2"></i>Route View: ${compName}</h5></div>`;
    }
  );

  // 2. Resolve paired custom tags: <ComponentName>...</ComponentName>
  result = result.replace(
    /<([A-Z][A-Za-z0-9_.]*)\b([^>]*)>([\s\S]*?)<\/\1>/g,
    (fullMatch, tag, attrs, children) => {
      const cleanTag = tag.split(".").pop() || tag;
      if (htmlTags.has(cleanTag.toLowerCase())) return fullMatch;

      const uiLibConverted = convertUiLibraryTag(cleanTag, attrs, children);
      if (uiLibConverted !== null) return uiLibConverted;

      const matchedFile = findFileForComponent(cleanTag, allFiles);
      if (matchedFile) {
        const childCode = stripDiffMarkers(matchedFile.code.map((l) => l.text));
        const childHtml = jsxToHtml(childCode.join("\n"), matchedFile.fileName, allFiles, depth + 1);
        if (childHtml.trim()) return childHtml;
      }

      return `<div class="custom-component my-2">${children}</div>`;
    }
  );

  // 3. Resolve self-closing custom tags: <ComponentName />
  result = result.replace(
    /<([A-Z][A-Za-z0-9_.]*)\b([^>]*)\/>/g,
    (fullMatch, tag, attrs) => {
      const cleanTag = tag.split(".").pop() || tag;
      if (htmlTags.has(cleanTag.toLowerCase())) return fullMatch;

      const uiLibConverted = convertUiLibrarySelfClosingTag(cleanTag, attrs);
      if (uiLibConverted !== null) return uiLibConverted;

      const matchedFile = findFileForComponent(cleanTag, allFiles);
      if (matchedFile) {
        const childCode = stripDiffMarkers(matchedFile.code.map((l) => l.text));
        const childHtml = jsxToHtml(childCode.join("\n"), matchedFile.fileName, allFiles, depth + 1);
        if (childHtml.trim()) return childHtml;
      }

      return `<div class="custom-component-item my-1"></div>`;
    }
  );

  return result;
}

function populateEmptyTables(html: string): string {
  if (!html || !html.includes("<table")) return html;

  return html.replace(/<table\b([^>]*)>([\s\S]*?)<\/table>/gi, (fullTable, tableAttrs, tableInner) => {
    let tbodyMatch = tableInner.match(/<tbody\b([^>]*)>([\s\S]*?)<\/tbody>/i);
    let tbodyContent = tbodyMatch ? tbodyMatch[2].trim() : "";

    const hasRows = tbodyContent.includes("<tr") && (tbodyContent.includes("<td") || tbodyContent.includes("<th"));
    if (hasRows) return fullTable;

    // Extract <th> header texts from the <thead> or <tr>
    const thMatches = Array.from(tableInner.matchAll(/<th\b[^>]*>([\s\S]*?)<\/th>/gi));
    const headerTexts = thMatches.map((m) => m[1].replace(/<[^>]*>/g, "").trim());

    let sampleRows = "";

    if (headerTexts.length > 0) {
      const generateRow = (rowIdx: number) => {
        const cells = headerTexts.map((header) => {
          const h = header.toLowerCase();
          if (h.includes("id") || h === "#") {
            return `<td>10${rowIdx + 1}</td>`;
          }
          if (h.includes("name") || h.includes("user") || h.includes("customer") || h.includes("employee") || h.includes("author") || h.includes("student") || h.includes("patient") || h.includes("doctor")) {
            const names = ["Alexander Smith", "Emily Chen", "David Wilson", "Sarah Jenkins"];
            return `<td>${names[rowIdx % names.length]}</td>`;
          }
          if (h.includes("email")) {
            const emails = ["alexander@enterprise.org", "emily.chen@enterprise.org", "david.w@enterprise.org", "sarah.j@enterprise.org"];
            return `<td>${emails[rowIdx % emails.length]}</td>`;
          }
          if (h.includes("role") || h.includes("type") || h.includes("category") || h.includes("dept") || h.includes("department") || h.includes("specialist") || h.includes("specialization")) {
            const roles = ["Administrator", "Engineering Lead", "Senior Manager", "Operations Specialist"];
            return `<td><span class="badge bg-primary-subtle text-primary border border-primary-subtle px-2 py-1">${roles[rowIdx % roles.length]}</span></td>`;
          }
          if (h.includes("status") || h.includes("state")) {
            const statuses = [
              '<span class="badge bg-success px-2 py-1"><i class="fa fa-check-circle me-1"></i>Active</span>',
              '<span class="badge bg-warning text-dark px-2 py-1"><i class="fa fa-clock me-1"></i>Pending</span>',
              '<span class="badge bg-secondary px-2 py-1"><i class="fa fa-pause-circle me-1"></i>Completed</span>',
            ];
            return `<td>${statuses[rowIdx % statuses.length]}</td>`;
          }
          if (h.includes("date") || h.includes("time") || h.includes("created") || h.includes("updated") || h.includes("appointment")) {
            return `<td>2026-09-2${8 - rowIdx}</td>`;
          }
          if (h.includes("price") || h.includes("amount") || h.includes("cost") || h.includes("fee") || h.includes("total") || h.includes("salary") || h.includes("balance")) {
            const amounts = ["$250.00", "$1,450.00", "$89.99", "$3,200.00"];
            return `<td>${amounts[rowIdx % amounts.length]}</td>`;
          }
          if (h.includes("phone") || h.includes("contact") || h.includes("mobile")) {
            return `<td>+1-555-010${rowIdx + 1}</td>`;
          }
          if (h.includes("action") || h.includes("operation") || h.includes("manage") || h.includes("option")) {
            return `<td>
              <button type="button" class="btn btn-sm btn-outline-primary me-1 py-1 px-2 font-weight-bold"><i class="fa fa-edit me-1"></i>Edit</button>
              <button type="button" class="btn btn-sm btn-outline-danger py-1 px-2 font-weight-bold delete-action-btn"><i class="fa fa-trash me-1"></i>Delete</button>
            </td>`;
          }
          if (h.includes("title") || h.includes("desc") || h.includes("subject") || h.includes("item") || h.includes("product") || h.includes("task") || h.includes("todo")) {
            const titles = ["Enterprise Migration Pipeline", "System Security Enforcement", "Cloud Database Integration", "User Authorization Matrix"];
            return `<td>${titles[rowIdx % titles.length]}</td>`;
          }
          return `<td>Sample ${escapeHtml(header)} ${rowIdx + 1}</td>`;
        });
        return `<tr>${cells.join("")}</tr>`;
      };

      sampleRows = `${generateRow(0)}\n${generateRow(1)}\n${generateRow(2)}`;
    } else {
      sampleRows = `
        <tr><td>Item 101</td><td>Enterprise Module A</td><td><span class="badge bg-success px-2 py-1">Active</span></td><td><button type="button" class="btn btn-sm btn-outline-primary me-1"><i class="fa fa-edit"></i> Edit</button><button type="button" class="btn btn-sm btn-outline-danger delete-action-btn"><i class="fa fa-trash"></i> Delete</button></td></tr>
        <tr><td>Item 102</td><td>Security & Access Control</td><td><span class="badge bg-warning text-dark px-2 py-1">In Progress</span></td><td><button type="button" class="btn btn-sm btn-outline-primary me-1"><i class="fa fa-edit"></i> Edit</button><button type="button" class="btn btn-sm btn-outline-danger delete-action-btn"><i class="fa fa-trash"></i> Delete</button></td></tr>
        <tr><td>Item 103</td><td>Data Pipeline Integration</td><td><span class="badge bg-secondary px-2 py-1">Pending</span></td><td><button type="button" class="btn btn-sm btn-outline-primary me-1"><i class="fa fa-edit"></i> Edit</button><button type="button" class="btn btn-sm btn-outline-danger delete-action-btn"><i class="fa fa-trash"></i> Delete</button></td></tr>`;
    }

    if (tbodyMatch) {
      return fullTable.replace(/<tbody\b([^>]*)>([\s\S]*?)<\/tbody>/i, `<tbody$1>${sampleRows}\n</tbody>`);
    } else {
      return fullTable.replace(/<\/table>/i, `<tbody>${sampleRows}\n</tbody>\n</table>`);
    }
  });
}

function cleanJsxAttributes(markup: string): string {
  if (!markup) return "";

  let cleaned = stripJsxEventHandlers(markup)
    // Strip block comments, JSX comments, HTML comments
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<%--[\s\S]*?--%>/g, "")
    .replace(/^[ \t]*.*-->[ \t]*$/gm, "")
    .replace(/.*-->/g, "")
    .replace(/<!--.*/g, "")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    // Strip embedded document wrappers
    .replace(/<!DOCTYPE[^>]*>/gi, "")
    .replace(/<head\b[^>]*>[\s\S]*?<\/head>/gi, "")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<\/?(?:html|head|body|meta|title)\b[^>]*>/gi, "")
    // Strip orphan attribute fragments
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

  // Strip export statements & module wrappers early
  cleaned = cleaned
    .replace(/(?:\)\s*;\s*)?(?:};\s*)?\bexport\s+default\s+[A-Za-z0-9_$]+;?/gi, "")
    .replace(/(?:\)\s*;\s*)?(?:};\s*)?\bexport\s+\{[^}]*\};?/gi, "")
    .replace(/\bexport\s+(?:default|const|function|class)\b.*/gi, "");

  // Clean conditional message expressions & state variable blocks BEFORE converting braces
  cleaned = cleaned
    .replace(/\{?\s*(?:errorMsg|successMsg|infoMsg|errorMessage|successMessage|msg|error|message)\s*&&\s*\([\s\S]*?\)\s*\}?/gi, "")
    .replace(/\{?\s*(?:errorMsg|successMsg|infoMsg|errorMessage|successMessage|msg|error|message)\s*&&\s*<[\s\S]*?>[\s\S]*?<\/[a-zA-Z0-9_-]+>\s*\}?/gi, "")
    .replace(/\b(?:errorMsg|successMsg|infoMsg|errorMessage|successMessage|msg|error|message)\s*&&\s*\(?/gi, "")
    .replace(/\{\s*(?:errorMsg|successMsg|infoMsg|errorMessage|successMessage|msg|error|message|csrf|getCsrfToken\(\))\s*\}/gi, "")
    .replace(/\{\s*\(\s*not\s+empty\s+[^)]*\)\s*&&\s*\([\s\S]*?\)\s*\}/gi, "")
    .replace(/\{\s*\(?\s*Boolean\s*\(\s*(?:userObj|user|currentUser|isLoggedIn)\b[^)]*\)\s*\)?\s*&&\s*\([\s\S]*?\)\s*\}/gi, "")
    .replace(/\{\s*\(?\s*(?:userObj|user|currentUser|isLoggedIn)\b[^&]*\)?\s*&&\s*\([\s\S]*?\)\s*\}/gi, "")
    .replace(/\{\s*\(\s*empty\s+[^)]*\)\s*&&\s*\(([\s\S]*?)\)\s*\}/gi, '$1')
    .replace(/\{\s*\(?\s*!\s*(?:userObj|user|currentUser|isLoggedIn)\b[^)]*\)?\s*&&\s*\(([\s\S]*?)\)\s*\}/gi, '$1')
    .replace(/\{[^{}]*?&&\s*(?:\(\s*)?(<[\s\S]*?>)(?:\s*\))?\s*\}/g, '$1');

  // Strip empty alert boxes or standalone orphan badges created by conditional messages
  cleaned = cleaned
    .replace(/<div\b[^>]*class=["'][^"']*(?:alert|message|error|info|success|danger|warning)[^"']*["'][^>]*>\s*(?:Success|Error|Info|Warning|successMsg|errorMsg|errorMessage|infoMsg|msg)?\s*<\/div>/gi, "")
    .replace(/<p\b[^>]*class=["'][^"']*(?:alert|message|error|info|success|danger|warning)[^"']*["'][^>]*>\s*(?:Success|Error|Info|Warning|successMsg|errorMsg|errorMessage|infoMsg|msg)?\s*<\/p>/gi, "")
    .replace(/<span\b[^>]*class=["'][^"']*(?:badge|label)[^"']*(?:bg-danger|bg-success|btn-danger|btn-success)[^"']*["'][^>]*>\s*(?:Error|Success)\s*<\/span>\s*(?:successMsg|errorMsg|errorMessage)?/gi, "");

  // Upgrade UI Library TextField / CustomInput components
  cleaned = cleaned.replace(
    /<(TextField|MuiTextField|CustomInput|TextInput)\b([^>]*)\/?>/g,
    (_match, _tag, attrs) => {
      const labelMatch = attrs.match(/\blabel=["']([^"']+)["']/i);
      const placeholderMatch = attrs.match(/\bplaceholder=["']([^"']+)["']/i);
      const typeMatch = attrs.match(/\btype=["']([^"']+)["']/i);
      const valueMatch = attrs.match(/\bvalue=["']([^"']+)["']/i);

      const labelText = labelMatch?.[1] || "";
      const inputType = typeMatch?.[1] || "text";
      const placeholder = placeholderMatch?.[1] || labelText || "Enter text";
      const val = valueMatch?.[1] ? ` value="${escapeHtml(valueMatch[1])}"` : "";

      const labelHtml = labelText ? `<label class="form-label font-weight-bold mb-1">${escapeHtml(labelText)}</label>` : "";
      return `<div class="form-group mb-3">${labelHtml}<input type="${escapeHtml(inputType)}" class="form-control" placeholder="${escapeHtml(placeholder)}"${val} /></div>`;
    }
  );

  // Upgrade standard unstyled HTML input fields to Bootstrap form-control with smart placeholders
  cleaned = cleaned.replace(/<input\b([^>]*?)(?:\s*\/)?>/gi, (_match, attrs: string) => {
    const nameMatch = attrs.match(/\bname=["']([^"']+)["']/i) || attrs.match(/\bid=["']([^"']+)["']/i);
    const typeMatch = attrs.match(/\btype=["']([^"']+)["']/i);
    const placeholderMatch = attrs.match(/\bplaceholder=["']([^"']+)["']/i);

    const type = typeMatch ? typeMatch[1].toLowerCase() : "text";
    const name = nameMatch ? nameMatch[1].toLowerCase() : "";

    let placeholder = placeholderMatch ? placeholderMatch[1] : "";
    let disclaimer = "";

    if (!placeholder) {
      if (name.includes("full") || name.includes("name") || name.includes("uname")) {
        placeholder = "Enter full name";
      } else if (name.includes("email") || type === "email") {
        placeholder = "Enter Email";
      } else if (name.includes("pass") || type === "password") {
        placeholder = "Enter password";
      } else if (name.includes("phone") || name.includes("mob") || name.includes("contact")) {
        placeholder = "Enter mobile number";
      }
    }

    if ((name.includes("email") || type === "email") && !cleaned.includes("never share your email")) {
      disclaimer = '<small class="text-muted mt-1 d-block" style="font-size: 0.8rem;">We\'ll never share your email with anyone else.</small>';
    }

    const placeholderAttr = placeholder ? ` placeholder="${escapeHtml(placeholder)}"` : "";
    const hasClass = /\bclass(Name)?=/i.test(attrs);

    let inputHtml = "";
    if (hasClass) {
      const upgradedAttrs = attrs.replace(/\bclass(Name)?=["']([^"']*)["']/i, (_m, _cn, cls) => {
        const hasFormControl = /\bform-control\b/.test(cls) || /\bbtn\b/.test(cls) || /\bform-check-input\b/.test(cls);
        return hasFormControl ? `class="${cls}"` : `class="form-control ${cls}"`;
      });
      inputHtml = `<input ${upgradedAttrs}${placeholderAttr} />`;
    } else {
      if (type === "checkbox" || type === "radio") {
        inputHtml = `<input class="form-check-input" ${attrs} />`;
      } else if (type === "submit" || type === "button") {
        inputHtml = `<button type="${type}" class="btn btn-primary w-100 py-2.5 fw-bold shadow-sm">${attrs}</button>`;
      } else {
        inputHtml = `<input class="form-control py-2" ${attrs}${placeholderAttr} />`;
      }
    }

    return inputHtml + disclaimer;
  });

  // Button components
  cleaned = cleaned
    .replace(/<(?:Button|MuiButton|IconButton|Form\.Button|CustomButton|SubmitButton)\b[^>]*>([\s\S]*?)<\/(?:Button|MuiButton|IconButton|Form\.Button|CustomButton|SubmitButton)>/gi, '<button type="button" class="btn btn-primary w-100 py-2.5 fw-bold shadow-sm m-1">$1</button>')
    .replace(/<(?:Button|MuiButton|IconButton)\b[^>]*\/>/gi, '<button type="button" class="btn btn-primary w-100 py-2.5 fw-bold shadow-sm m-1">Submit</button>');

  // Select / MenuItem components
  cleaned = cleaned
    .replace(/<Select\b([^>]*)\blabel=["']([^"']+)["'][^>]*>([\s\S]*?)<\/Select>/gi, '<div class="form-group mb-3"><label class="form-label font-weight-bold">$2</label><select class="form-select">$3</select></div>')
    .replace(/<Select\b[^>]*>([\s\S]*?)<\/Select>/gi, '<select class="form-select">$1</select>')
    .replace(/<MenuItem\b[^>]*\bvalue=["']([^"']+)["'][^>]*>([\s\S]*?)<\/MenuItem>/gi, '<option value="$1">$2</option>')
    .replace(/<MenuItem\b[^>]*>([\s\S]*?)<\/MenuItem>/gi, '<option>$1</option>');

  // Typography components
  cleaned = cleaned
    .replace(/<Typography\b[^>]*\bvariant=["'](h[1-6])["'][^>]*>([\s\S]*?)<\/Typography>/gi, '<$1 class="typography-$1">$2</$1>')
    .replace(/<Typography\b[^>]*>([\s\S]*?)<\/Typography>/gi, '<div class="typography-body my-1">$1</div>');

  // Card / Paper components
  cleaned = cleaned
    .replace(/<CardHeader\b[^>]*\btitle=["']([^"']+)["'][^>]*\/>/gi, (_match, title) => {
      return `<div class="card-header bg-primary text-white text-center py-3 fw-bold fs-5 border-0"><i class="fa fa-clipboard-list me-2"></i>${escapeHtml(title)}</div>`;
    })
    .replace(/<(?:Card|Paper|MuiPaper)\b[^>]*>([\s\S]*?)<\/(?:Card|Paper|MuiPaper)>/gi, '<div class="card shadow-sm mb-3"><div class="card-body p-4">$1</div></div>')
    .replace(/<CardContent\b[^>]*>([\s\S]*?)<\/CardContent>/gi, '<div class="card-body p-4">$1</div>')
    .replace(/<CardActions\b[^>]*>([\s\S]*?)<\/CardActions>/gi, '<div class="card-footer bg-transparent border-0">$1</div>');

  // Layout components: Container, Grid, Box, Stack
  cleaned = cleaned
    .replace(/<(?:Container|Box|Stack|MuiBox|MuiContainer)\b[^>]*>([\s\S]*?)<\/(?:Container|Box|Stack|MuiBox|MuiContainer)>/gi, '<div class="container my-2">$1</div>')
    .replace(/<Grid\b[^>]*\bcontainer[^>]*>([\s\S]*?)<\/Grid>/gi, '<div class="row g-3">$1</div>')
    .replace(/<Grid\b[^>]*\bitem[^>]*>([\s\S]*?)<\/Grid>/gi, '<div class="col">$1</div>')
    .replace(/<Grid\b[^>]*>([\s\S]*?)<\/Grid>/gi, '<div class="col">$1</div>');

  // Table components
  cleaned = cleaned
    .replace(/<Table\b[^>]*>([\s\S]*?)<\/Table>/gi, '<div class="table-responsive my-3"><table class="table table-bordered table-striped align-middle mb-0">$1</table></div>')
    .replace(/<TableHead\b[^>]*>([\s\S]*?)<\/TableHead>/gi, '<thead class="table-light">$1</thead>')
    .replace(/<TableBody\b[^>]*>([\s\S]*?)<\/TableBody>/gi, '<tbody>$1</tbody>')
    .replace(/<TableRow\b[^>]*>([\s\S]*?)<\/TableRow>/gi, '<tr>$1</tr>')
    .replace(/<TableCell\b[^>]*>([\s\S]*?)<\/TableCell>/gi, '<td>$1</td>');

  if (cleaned.includes("<table") && !cleaned.includes("table-responsive")) {
    cleaned = cleaned.replace(/<table\b([^>]*)>([\s\S]*?)<\/table>/gi, '<div class="table-responsive my-3"><table $1>$2</table></div>');
  }

  // Alert / Link / NavLink components
  cleaned = cleaned
    .replace(/<Alert\b[^>]*>([\s\S]*?)<\/Alert>/gi, '<div class="alert alert-info shadow-sm">$1</div>')
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

  // Handle JSX Expressions safely & strip raw JS IIFEs
  cleaned = cleaned
    .replace(/\{\s*\(\s*\(\s*\)\s*=>[\s\S]*?\)\s*\(\s*\)\s*\}/g, "")
    .replace(/\(\s*\(\s*\)\s*=>[\s\S]*?\)\s*\(\s*\)/g, "");

  // Expanded `.map(...)` list iteration converter
  cleaned = cleaned.replace(
    /\{?\s*(?:\([a-zA-Z0-9_$.&| ]+\)|[a-zA-Z0-9_$.&| ]+)?\.map\s*\(\s*(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>\s*(?:\{(?:\s*return)?|\()?([\s\S]*?)(?:\)?\}|\))?\s*\)\s*\}?/gi,
    (_match, rawBody) => {
      const body = rawBody.replace(/^\s*\(\s*/, "").replace(/\s*\)\s*$/, "").trim();

      if (/<option\b/i.test(body)) {
        return `<option value="1">Option 1 (Primary)</option>
<option value="2">Option 2 (Secondary)</option>
<option value="3">Option 3 (Tertiary)</option>`;
      }

      if (/<tr\b/i.test(body) || body.includes("<td")) {
        const renderRow = (
          idx: number,
          name: string,
          email: string,
          role: string,
          status: string,
          amount: string,
          date: string
        ) => {
          let row = body
            .replace(/\{\s*[a-zA-Z0-9_$]+\.(?:fullName|name|username|title|label)\s*\}/gi, name)
            .replace(/\{\s*[a-zA-Z0-9_$]+\.email\s*\}/gi, email)
            .replace(/\{\s*[a-zA-Z0-9_$]+\.(?:role|type|category|department|dept|specialist|specialization)\s*\}/gi, role)
            .replace(/\{\s*[a-zA-Z0-9_$]+\.status\s*\}/gi, status)
            .replace(/\{\s*[a-zA-Z0-9_$]+\.(?:price|amount|cost|total|fee|salary|balance)\s*\}/gi, amount)
            .replace(/\{\s*[a-zA-Z0-9_$]+\.(?:date|created|updated|appointmentDate|targetDate)\s*\}/gi, date)
            .replace(/\{\s*[a-zA-Z0-9_$]+\.id\s*\}/gi, String(100 + idx))
            .replace(/\{\s*[a-zA-Z0-9_$]+\.(?:phone|contact|mobile)\s*\}/gi, `+1-555-010${idx + 1}`)
            .replace(/\{\s*getStatusBadge\([^)]*\)\}/gi, `<span class="badge bg-success px-2 py-1">${status}</span>`)
            .replace(/key=\{[^}]+\}/gi, "");

          if (!row.startsWith("<tr")) {
            row = `<tr>${row}</tr>`;
          }
          return row;
        };

        const r1 = renderRow(1, "Alexander Smith", "alexander@enterprise.org", "Administrator", "Active", "$250.00", "2026-09-28");
        const r2 = renderRow(2, "Emily Chen", "emily.chen@enterprise.org", "Engineering Lead", "In Progress", "$1,450.00", "2026-09-27");
        const r3 = renderRow(3, "David Wilson", "david.w@enterprise.org", "Operations Specialist", "Pending", "$89.99", "2026-09-26");

        return `${r1}\n${r2}\n${r3}`;
      }

      return body;
    }
  );

  // Replace single item / object property expressions across all domain models
  cleaned = cleaned
    .replace(/\{\s*[a-zA-Z0-9_$]+\.(?:fullName|name|username|title|label)\s*(?:\|\|[^}]+)?\}/gi, "Alexander Smith")
    .replace(/\{\s*[a-zA-Z0-9_$]+\.email\s*(?:\|\|[^}]+)?\}/gi, "alexander@enterprise.org")
    .replace(/\{\s*[a-zA-Z0-9_$]+\.(?:role|type|category|department|specialist)\s*(?:\|\|[^}]+)?\}/gi, "Administrator")
    .replace(/\{\s*[a-zA-Z0-9_$]+\.status\s*(?:\|\|[^}]+)?\}/gi, "Active")
    .replace(/\{\s*[a-zA-Z0-9_$]+\.(?:price|amount|cost|total|fee|salary)\s*(?:\|\|[^}]+)?\}/gi, "$250.00")
    .replace(/\{\s*[a-zA-Z0-9_$]+\.(?:date|created|updated)\s*(?:\|\|[^}]+)?\}/gi, "2026-09-28")
    .replace(/\{\s*[a-zA-Z0-9_$]+\.id\s*\}/gi, "101");

  // Convert simple {variable} or {data.field} to empty string if state/code
  cleaned = cleaned.replace(/\{\s*(?:[a-zA-Z0-9_$.]+)\s*\}/g, "");

  // Clean remaining lone curly braces, export statements, and leftover JS code fragments
  cleaned = cleaned
    .replace(/(?:\)\s*;\s*)?(?:};\s*)?\bexport\s+default\s+[A-Za-z0-9_$]+;?/gi, "")
    .replace(/(?:\)\s*;\s*)?(?:};\s*)?\bexport\s+\{[^}]*\};?/gi, "")
    .replace(/\{|\}/g, "")
    .replace(/const\s+\w+\s*=\s*[^;]+;/g, "")
    .replace(/\bgetCsrfToken\(\);?/gi, "")
    .replace(/\)\s*;\s*$/g, "")
    .replace(/;\s*$/g, "");

  // Strip text after the last HTML closing tag if it is leftover JS code
  const lastCloseTagIndex = cleaned.lastIndexOf(">");
  if (lastCloseTagIndex >= 0 && lastCloseTagIndex < cleaned.length - 1) {
    const trailingText = cleaned.slice(lastCloseTagIndex + 1).trim();
    if (/^[);\s\w_$]+$/i.test(trailingText) || trailingText.includes("export default")) {
      cleaned = cleaned.slice(0, lastCloseTagIndex + 1);
    }
  }

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

  const compRegex = /(?:function|const|class)\s+([A-Za-z0-9_]+)/g;
  let compMatch;
  const compIndices: { name: string; index: number }[] = [];
  while ((compMatch = compRegex.exec(code)) !== null) {
    if (/^[A-Z]/.test(compMatch[1])) {
      compIndices.push({ name: compMatch[1], index: compMatch.index });
    }
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
        } else if (sub.startsWith("<>") || sub.startsWith("<React.Fragment")) {
          const closeIdx = sub.lastIndexOf("</>");
          if (closeIdx >= 0) {
            return code.slice(firstTag, firstTag + closeIdx + 3);
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
  const tagMatch = cleanCode.match(/<(div|form|main|section|article|header|nav|table|ul|ol|Container|Box|Card)\b[^>]*>/i);
  if (!tagMatch) return "";

  const rootTagName = tagMatch[1];
  const startIndex = cleanCode.indexOf(tagMatch[0]);
  if (startIndex < 0) return "";

  const closeTag = `</${rootTagName}>`;
  const lastCloseIndex = cleanCode.lastIndexOf(closeTag);

  if (lastCloseIndex > startIndex) {
    const extracted = cleanCode.slice(startIndex, lastCloseIndex + closeTag.length);
    return cleanJsxAttributes(extracted);
  }

  const lastAnyClose = cleanCode.lastIndexOf("</");
  if (lastAnyClose > startIndex) {
    const endTagClose = cleanCode.indexOf(">", lastAnyClose);
    if (endTagClose > lastAnyClose) {
      return cleanJsxAttributes(cleanCode.slice(startIndex, endTagClose + 1));
    }
  }

  return cleanJsxAttributes(cleanCode.slice(startIndex));
}

function extractAllHtmlTags(source: string): string {
  const cleanCode = stripLeadingHeaderComments(source);
  const tagPattern = /(<\/?(?:div|form|input|button|label|select|option|textarea|table|tr|td|th|thead|tbody|span|p|h[1-6]|a|img|nav|header|footer|main|section|ul|li|ol)\b[^>]*\/?>)/gi;
  const parts: string[] = [];
  let m;
  while ((m = tagPattern.exec(cleanCode)) !== null) parts.push(m[1]);
  return parts.length ? cleanJsxAttributes(parts.join("\n")) : "";
}

function jsxToHtml(
  source: string,
  fileName: string = "",
  allFiles: SandboxFile[] = [],
  depth = 0
): string {
  const cleanCode = stripLeadingHeaderComments(source);
  if (!cleanCode.trim()) return "";

  let result = "";

  const jsxBlocks = extractAllJsxBlocks(cleanCode, fileName);
  if (jsxBlocks.length > 0) {
    const combinedJsx = jsxBlocks.join("\n");
    const cleaned = cleanJsxAttributes(combinedJsx);
    if (cleaned.trim()) result = cleaned.trim();
  }

  if (!result) {
    const rootBlock = extractRootTagBlock(cleanCode);
    if (rootBlock.trim()) result = rootBlock.trim();
  }

  if (!result) {
    const allTags = extractAllHtmlTags(cleanCode);
    if (allTags.trim()) result = allTags.trim();
  }

  // Inline child subcomponents from allFiles
  if (result && allFiles && allFiles.length > 0 && depth < 3) {
    result = inlineChildComponents(result, allFiles, depth);
  }

  return populateEmptyTables(result);
}

function angularToHtml(source: string): string {
  const cleanCode = stripLeadingHeaderComments(source);
  const templateMatch =
    cleanCode.match(/template\s*:\s*`([\s\S]*?)`/m) ||
    cleanCode.match(/template\s*:\s*'([\s\S]*?)'/m);
  let markup = templateMatch?.[1] ?? cleanCode;

  // 1. Repair action buttons
  markup = markup
    .replace(/<a\b[^>]*\bclass=["'][^"']*btn-danger[^"']*["']\s*(?:href=[^>]*)?(?:>)?\s*(?:<\/a>)?/gi, 
      '<button type="button" class="btn btn-danger btn-sm text-white delete-action-btn"><i class="fa fa-trash me-1"></i> Delete</button>')
    .replace(/<a\b([^>]*\bclass=["'][^"']*btn-danger[^"']*["'][^>]*)>([\s\S]*?)<\/a>/gi, 
      '<button type="button" class="btn btn-danger btn-sm text-white delete-action-btn"><i class="fa fa-trash me-1"></i> Delete</button>');

  // 2. Expand Angular loops (*ngFor)
  markup = markup.replace(
    /<ng-container\b[^>]*\*ngFor="let\s+([a-zA-Z0-9_$]+)\s+of\s+([a-zA-Z0-9_$.]+)"[^>]*>([\s\S]*?)<\/ng-container>/gi,
    (_match, itemVar, _listVar, innerTemplate) => {
      const resolveGenericProp = (prop: string, idx: number) => {
        const p = prop.toLowerCase();
        if (p === "id") return String(idx + 101);
        if (p.includes("name") || p.includes("title") || p.includes("label") || p.includes("user")) {
          const names = ["Alexander Smith", "Emily Chen", "David Wilson"];
          return names[idx % names.length];
        }
        if (p.includes("category") || p.includes("type") || p.includes("dept") || p.includes("role")) {
          const cats = ["Architecture", "Engineering", "Operations"];
          return cats[idx % cats.length];
        }
        if (p.includes("status") || p.includes("state")) {
          const statuses = ["Active", "Completed", "Pending Review"];
          return statuses[idx % statuses.length];
        }
        if (p.includes("price") || p.includes("amount") || p.includes("cost") || p.includes("total")) {
          const amounts = ["$250.00", "$1,450.00", "$89.50"];
          return amounts[idx % amounts.length];
        }
        if (p.includes("date") || p.includes("time") || p.includes("created")) {
          return "2026-09-28";
        }
        if (p.includes("email")) {
          return `user${idx + 1}@enterprise.org`;
        }
        return `Item ${idx + 1} (${prop})`;
      };

      const expandRow = (idx: number) => {
        return innerTemplate
          .replace(new RegExp(`\\{\\\{\\s*${itemVar}\\.([a-zA-Z0-9_$]+)\\s*\\}\\}`, "gi"), (_m, p) => resolveGenericProp(p, idx))
          .replace(/<button\b[^>]*\bdelete[^>]*>[\s\S]*?<\/button>/gi, '<button type="button" class="btn btn-danger btn-sm text-white delete-action-btn"><i class="fa fa-trash me-1"></i> Delete</button>');
      };

      return `${expandRow(0)}\n${expandRow(1)}\n${expandRow(2)}`;
    }
  );

  // 3. Resolve dynamic Angular Interpolations {{ ... }}
  markup = markup
    .replace(/\{\{\s*(?:name|user|userName|currentUser|username)\s*\}\}/gi, "Enterprise Admin")
    .replace(/\{\{\s*(?:errorMessage|errorMsg|error|infoMsg|msg)\s*\}\}/gi, "")
    .replace(/\{\{\s*(?:todos|items|list)\.length\s*\}\}/gi, "3")
    .replace(/\{\{\s*(?:pageTitle|title)\s*\}\}/gi, "Enterprise Portal")
    .replace(/\{\{\s*([^}]*)\s*\}\}/g, "$1");

  return populateEmptyTables(cleanJsxAttributes(markup));
}

function inferPortalTitle(fileName: string, allFiles: SandboxFile[], codeSource: string): string {
  const combinedText = (
    fileName +
    " " +
    codeSource +
    " " +
    allFiles.map((f) => f.fileName).join(" ")
  ).toLowerCase();

  if (combinedText.includes("doctor") || combinedText.includes("patient") || combinedText.includes("hospital") || combinedText.includes("appointment")) {
    return "Doctor Patient Portal";
  }
  if (combinedText.includes("todo") || combinedText.includes("task")) {
    return "Todo & Task Management System";
  }
  if (combinedText.includes("document") || combinedText.includes("file") || combinedText.includes("archive")) {
    return "Enterprise Document Portal";
  }
  if (combinedText.includes("employee") || combinedText.includes("hr") || combinedText.includes("payroll")) {
    return "HR & Employee Portal";
  }
  if (combinedText.includes("order") || combinedText.includes("product") || combinedText.includes("cart") || combinedText.includes("inventory")) {
    return "E-Commerce Operations Center";
  }
  if (combinedText.includes("bank") || combinedText.includes("account") || combinedText.includes("transaction")) {
    return "Enterprise Banking Portal";
  }
  if (combinedText.includes("student") || combinedText.includes("course") || combinedText.includes("academic")) {
    return "Student Information System";
  }
  return "Enterprise Application Portal";
}

function generateDynamicNavbar(portalTitle: string, allFiles: SandboxFile[], activeFileName: string): string {
  const pageFiles = allFiles.filter((f) => !/css|scss|test|spec|layout|header|footer|navbar|navigation/i.test(f.fileName));

  const navLinks = pageFiles.slice(0, 6).map((f) => {
    const rawName = f.fileName.split("/").pop()?.replace(/\.[^.]+$/, "") || f.fileName;
    const cleanName = rawName
      .replace(/(?:Component|Page|View|Screen|Controller)$/i, "")
      .replace(/([A-Z])/g, " $1")
      .trim();
    const isActive = f.fileName === activeFileName || rawName.toLowerCase() === activeFileName.toLowerCase();
    const activeClass = isActive ? "active bg-white bg-opacity-25 fw-bold" : "fw-semibold";
    return `<li class="nav-item">
      <a class="nav-link text-white ${activeClass} px-3 py-1.5 rounded-2 text-decoration-none" href="#" data-nav="${escapeHtml(f.fileName)}">
        <i class="fa fa-layer-group me-1"></i>${escapeHtml(cleanName || rawName)}
      </a>
    </li>`;
  }).join("\n");

  return `
  <nav class="navbar navbar-expand-lg navbar-dark bg-primary shadow-sm px-4 py-2.5 mb-4 rounded-bottom-3 d-flex align-items-center justify-content-between">
    <div class="container-fluid d-flex flex-wrap align-items-center justify-content-between p-0">
      <div class="d-flex align-items-center gap-3">
        <a class="navbar-brand d-flex align-items-center text-white fw-bold mb-0 text-decoration-none" href="/" data-nav="index">
          <span class="bg-white text-primary rounded-3 p-2 me-2 d-inline-flex shadow-sm">
            <i class="fa fa-cubes"></i>
          </span>
          <span class="fs-5 fw-bold text-white">${escapeHtml(portalTitle)}</span>
        </a>
        <span class="badge bg-white text-primary px-2 py-1 small rounded-pill fw-bold shadow-sm">
          v2.4 Modernized
        </span>
      </div>

      <ul class="navbar-nav d-flex flex-row align-items-center my-2 my-lg-0 list-unstyled gap-2 flex-wrap">
        ${navLinks || `<li class="nav-item"><a class="nav-link text-white active px-3 py-1.5" href="#">Home</a></li>`}
      </ul>

      <div class="d-flex align-items-center gap-2">
        <a class="btn btn-sm btn-light text-primary fw-bold px-3 py-1.5 rounded-2 shadow-sm" href="/logout" data-nav="login">
          <i class="fa fa-sign-out-alt me-1"></i>Logout
        </a>
      </div>
    </div>
  </nav>`;
}

function generatePreviewHtml(rawLines: GeneratedLine[], fileName: string, allFiles: SandboxFile[] = []): string {
  const primaryFileName = fileName.split(",")[0].trim();
  const rawText = rawLines.map((l) => l.text).join("\n");
  const cleanSource = stripDiffMarkers(rawText.split("\n")).join("\n");
  const selectedSource = selectGeneratedFile(cleanSource, primaryFileName);
  const isAngular = primaryFileName.endsWith(".ts") || primaryFileName.endsWith(".html");

  let markup = isAngular
    ? angularToHtml(selectedSource)
    : jsxToHtml(selectedSource, primaryFileName, allFiles, 0);

  const portalTitle = inferPortalTitle(primaryFileName, allFiles, selectedSource);

  // If component does not have top navigation bar, inject dynamic header navbar
  if (!markup.includes("<nav") && !markup.includes("<header")) {
    const topNavbar = generateDynamicNavbar(portalTitle, allFiles, primaryFileName);
    markup = `${topNavbar}\n<div class="container my-3" style="max-width: 1140px;">${markup}</div>`;
  }

  // Clean duplicate classes
  markup = markup.replace(/<([a-z0-9]+)\b([^>]*?)\bclass="([^"]*)"([^>]*?)\bclass="([^"]*)"([^>]*)>/gi, '<$1$2 class="$3 $5"$4$6>');

  const visibleText = markup.replace(/<[^>]*>/g, "").replace(/\s+/g, "").trim();

  // If the markup is completely empty or just an empty wrapper
  if (!markup || !markup.trim() || visibleText.length === 0) {
    const baseStem = fileName.split("/").pop()?.replace(/\.[^.]+$/, "").toLowerCase() || "";
    const cleanStem = baseStem.replace(/component|page|view/gi, "");

    if (cleanStem && cleanStem.length >= 3) {
      const altFile = allFiles.find((f) => {
        if (f.fileName === fileName) return false;
        const fBase = f.fileName.split("/").pop()?.replace(/\.[^.]+$/, "").toLowerCase() || "";
        return fBase.includes(cleanStem) && !/navbar|header|footer/i.test(fBase);
      });
      if (altFile && altFile.code && altFile.code.length > 0) {
        const altText = altFile.code.map((l) => l.text).join("\n");
        const altMarkup = jsxToHtml(stripDiffMarkers(altText.split("\n")).join("\n"), altFile.fileName, allFiles, 1);
        if (altMarkup && altMarkup.replace(/<[^>]*>/g, "").trim().length > 0) {
          return altMarkup;
        }
      }
    }

    if (
      /login|signin|auth/i.test(fileName) ||
      /login|signin|auth/i.test(baseStem) ||
      (selectedSource.includes("password") && (selectedSource.includes("name") || selectedSource.includes("username") || selectedSource.includes("email")))
    ) {
      return `
      ${generateDynamicNavbar(portalTitle, allFiles, primaryFileName)}
      <div class="card shadow-sm border-0 mx-auto my-4" style="max-width: 440px; border-radius: 12px; background: #ffffff;">
        <div class="card-body p-4">
          <div class="text-center mb-4">
            <div class="bg-primary bg-opacity-10 text-primary rounded-circle d-inline-flex p-3 mb-2 shadow-sm">
              <i class="fa fa-user-lock fa-2x"></i>
            </div>
            <h4 class="card-title font-weight-bold text-dark mb-1">Sign In</h4>
            <p class="text-muted small">Access your modernized enterprise workspace</p>
          </div>
          <form action="/login" method="post" id="loginForm">
            <div class="form-group mb-3">
              <label class="form-label font-weight-bold small text-muted">Username</label>
              <div class="input-group">
                <span class="input-group-text bg-light text-muted border-end-0"><i class="fa fa-user"></i></span>
                <input type="text" name="name" class="form-control border-start-0" placeholder="Enter username" value="admin" required />
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
      .replace(/\\/g, "/")
      .replace(/\.(jsp|jspx|jspf|xhtml|jsf|html|htm|php|asp|aspx|tsx|jsx|ts|js)$/i, "")
      .replace(/[^a-z0-9]/g, "")
      .replace(/component|page|view|screen/gi, "");

  const cleanLabel = normalize(label);
  const rawTargetName = href.split("/").pop()?.split("?")[0] || href;
  const cleanHref = normalize(rawTargetName);

  // 1. Exact or normalized filename match
  for (const f of files) {
    const normFile = normalize(f.fileName);
    if (normFile === cleanHref || normFile === cleanLabel) {
      return f;
    }
  }

  // 2. Base filename match
  for (const f of files) {
    const baseName = f.fileName.split("/").pop() || f.fileName;
    const cleanBase = normalize(baseName);
    if (cleanBase && (cleanBase === cleanHref || cleanBase === cleanLabel)) {
      return f;
    }
  }

  // 3. Substring match for href
  if (cleanHref && cleanHref.length >= 3) {
    for (const f of files) {
      const normFile = normalize(f.fileName);
      if (normFile.includes(cleanHref) || cleanHref.includes(normFile)) {
        return f;
      }
    }
  }

  // 4. Substring match for label
  if (cleanLabel && cleanLabel.length >= 3) {
    for (const f of files) {
      const normFile = normalize(f.fileName);
      if (normFile.includes(cleanLabel) || cleanLabel.includes(normFile)) {
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

  useEffect(() => {
    if (fileName.toLowerCase().endsWith(".css") && allFiles.length > 0) {
      const firstValid = allFiles.find((f) => !f.fileName.toLowerCase().endsWith(".css"));
      if (firstValid) {
        setActiveFileName(firstValid.fileName);
        setActiveCode(firstValid.code);
        setNavHistory([]);
        return;
      }
    }
    setActiveFileName(fileName);
    setActiveCode(code);
    setNavHistory([]);
  }, [fileName, code, allFiles]);

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

    *, *::before, *::after { box-sizing: border-box !important; }
    .row { display: flex !important; flex-wrap: wrap !important; margin-right: -0.75rem !important; margin-left: -0.75rem !important; }
    [class*="col-"] { box-sizing: border-box !important; padding-right: 0.75rem !important; padding-left: 0.75rem !important; position: relative !important; min-width: 0 !important; }

    img, .img-fluid { max-width: 100% !important; height: auto !important; object-fit: cover !important; border-radius: 8px !important; display: block !important; }
    .card img, [class*="col-"] img { max-width: 100% !important; max-height: 280px !important; width: 100% !important; height: auto !important; object-fit: cover !important; }

    .form-group { margin-bottom: 1.25rem !important; width: 100% !important; }
    .form-label { font-weight: 600 !important; font-size: 0.875rem !important; color: #334155 !important; margin-bottom: 0.35rem !important; display: block !important; }
    .form-control, .form-select { width: 100% !important; padding: 0.65rem 0.95rem !important; border: 1px solid #cbd5e1 !important; border-radius: 8px !important; font-size: 0.95rem !important; background-color: #ffffff !important; color: #0f172a !important; }
    .form-control:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15); outline: none; }

    .table-responsive { overflow-x: auto; border-radius: 8px; border: 1px solid #e2e8f0; width: 100%; background: #ffffff; margin-top: 1rem; margin-bottom: 1rem; }
    .table { width: 100% !important; margin-bottom: 0; border-collapse: collapse; }
    .table th, .table td { padding: 0.75rem 1rem; vertical-align: middle; white-space: nowrap; }

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
      // 1. Dynamic Dropdown Toggling
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

        if (!e.target.closest('.dropdown')) {
          document.querySelectorAll('.dropdown-menu.show').forEach(function(m) {
            m.classList.remove('show');
            m.style.display = 'none';
          });
        }

        // 2. Navigation Hyperlinks
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
                toast.innerHTML = '<i class="fa fa-trash me-2 text-danger"></i><strong>Live Action:</strong> Item removed reactively.';
                document.body.appendChild(toast);
                setTimeout(function() { if (toast.parentNode) toast.remove(); }, 3200);
              }, 250);
            }
            return false;
          }
          e.preventDefault();
          e.stopPropagation();
          window.parent.postMessage({
            type: 'SANDBOX_NAVIGATE',
            href: aHref,
            label: aLabel
          }, '*');
          return false;
        }

        // 3. Action Buttons
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
                toast.innerHTML = '<i class="fa fa-trash me-2 text-danger"></i><strong>Live Action:</strong> Item removed reactively.';
                document.body.appendChild(toast);
                setTimeout(function() { if (toast.parentNode) toast.remove(); }, 3200);
              }, 250);
            }
            return false;
          }
          if (btnLabel) {
            window.parent.postMessage({
              type: 'SANDBOX_NAVIGATE',
              href: btnLabel.toLowerCase(),
              label: btnLabel
            }, '*');
          }
        }
      }, true);

      // 4. Form Submission
      document.addEventListener('submit', function(e) {
        e.preventDefault();
        e.stopPropagation();
        var form = e.target;
        var data = new FormData(form);
        var entries = Object.fromEntries(data.entries());
        var keys = Object.keys(entries);
        var feedback = keys.length > 0 
          ? 'Form data submitted successfully (' + keys.join(', ') + ')'
          : 'Form submitted successfully';

        var existingToast = document.getElementById('sandbox-dynamic-toast');
        if (existingToast) existingToast.remove();
        var toast = document.createElement('div');
        toast.id = 'sandbox-dynamic-toast';
        toast.className = 'alert alert-success shadow-lg';
        toast.style.cssText = 'position: fixed; bottom: 24px; right: 24px; z-index: 99999; border-radius: 8px; font-weight: 500; font-size: 13px; padding: 12px 20px;';
        toast.innerHTML = '<i class="fa fa-check-circle me-2"></i><strong>Live State:</strong> ' + feedback;
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
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="react-sandbox-kicker">{frameworkName} sandbox</span>
              <span style={{
                background: "rgba(16, 185, 129, 0.12)",
                color: "#059669",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                fontSize: 11,
                fontWeight: 800,
                padding: "2px 8px",
                borderRadius: 12,
                display: "inline-flex",
                alignItems: "center",
                gap: 4
              }}>
                🎯 UI Fidelity Engine
              </span>
            </div>
            <h2>{activeFileName}</h2>
            <p>
              Migrated React/Angular code rendered directly from repository source files.
              Interactive controls and sandbox routing enabled.
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
          Dynamic Migration Preview Engine. Renders migrated repository components, subcomponents, data tables, and forms.
        </footer>
      </section>
    </div>
  );

  return typeof document !== "undefined"
    ? createPortal(modalContent, document.body)
    : modalContent;
}
