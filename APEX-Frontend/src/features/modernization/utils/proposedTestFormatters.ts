/**
 * Formatting utilities for Proposed Functional Test Cases display names.
 */

export interface ProposedTestLike {
  id?: string;
  title?: string;
  name?: string;
  test_name?: string;
  type?: string;
  api_spec?: {
    method?: string;
    endpoint?: string;
  } | null;
  apiSpec?: {
    method?: string;
    endpoint?: string;
  } | null;
  description?: string;
  reason?: string;
}

const HTTP_METHODS = new Set(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]);

/**
 * Formats the user-facing display name of a Proposed Test Case for tables and modals.
 *
 * Requirements:
 * 1. Standard API tests display ONLY: `${HTTP_METHOD} ${ENDPOINT}` (e.g., `GET /api/attendance/fetch`).
 * 2. Scenario-specific API tests display: `${HTTP_METHOD} ${ENDPOINT} – ${SCENARIO}` (e.g., `POST /api/attendance/send-email – Invalid Payload`).
 * 3. UI tests and non-API tests preserve their meaningful human-readable names (e.g., `Validate form submission and feedback on Add Todo`).
 * 4. Path parameters are preserved (e.g., `GET /api/employees/{id}`).
 * 5. Generic boilerplate phrases ("Verify", "returns success response", "should return success") are eliminated.
 */
export function formatProposedTestDisplayName(test?: ProposedTestLike | null): string {
  if (!test) return "Test Case";

  const rawTitle = (test.title || test.name || test.test_name || "").trim();
  const testType = (test.type || "").toUpperCase();

  // 1. Structured API Spec check
  let method = (test.api_spec?.method || test.apiSpec?.method || "").trim().toUpperCase();
  let endpoint = (test.api_spec?.endpoint || test.apiSpec?.endpoint || "").trim();

  // 2. If no structured api_spec method/endpoint, attempt extraction from title if it matches HTTP pattern
  if (!method || !endpoint) {
    const titleMatch = rawTitle.match(/(?:^|\b)(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\/[^\s–—\-]*)/i);
    if (titleMatch) {
      if (!method) method = titleMatch[1].toUpperCase();
      if (!endpoint) endpoint = titleMatch[2].trim();
    }
  }

  // 3. If this is not an API test or lacks method/endpoint, preserve original human-readable title (for UI, Unit, etc.)
  const isApi = testType === "API" || (method && HTTP_METHODS.has(method) && endpoint.startsWith("/"));
  if (!isApi || !method || !endpoint) {
    return rawTitle || "Test Case";
  }

  // Ensure method is uppercase and endpoint starts with '/'
  const formattedMethod = method.toUpperCase();
  const formattedEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;

  // 4. Check if rawTitle contains a specific functional scenario distinction beyond standard endpoint success
  const scenario = extractApiScenario(rawTitle, formattedMethod, formattedEndpoint);

  if (scenario) {
    return `${formattedMethod} ${formattedEndpoint} – ${scenario}`;
  }

  return `${formattedMethod} ${formattedEndpoint}`;
}

/**
 * Extracts distinct scenario information from test title, stripping generic LLM boilerplate phrases.
 */
function extractApiScenario(title: string, method: string, endpoint: string): string | null {
  if (!title) return null;

  // Remove leading action verbs: Verify, Validate, Check, Test, Ensure, Should verify/validate/check
  let cleaned = title
    .replace(/^(?:should\s+)?(?:verify|validate|check|test|ensure|assert)\s+/i, "")
    .trim();

  // Remove HTTP method and endpoint from the string (accounting for case & possible params)
  const escapedMethod = escapeRegex(method);
  const escapedEndpoint = escapeRegex(endpoint);
  cleaned = cleaned
    .replace(new RegExp(`^${escapedMethod}\\s+${escapedEndpoint}`, "i"), "")
    .replace(new RegExp(`^${escapedMethod}\\s+[^\\s–—]+`, "i"), "")
    .trim();

  // Remove leading separator if present
  cleaned = cleaned.replace(/^[–—\-\:\.]\s*/, "").trim();

  // Remove common generic success / happy-path boilerplate
  const genericSuccessPatterns = [
    /^(?:returns?|should\s+return)?\s*(?:successful?|success|200\s*(?:ok)?|201\s*(?:created)?)\s*(?:response|status|result|code)?$/i,
    /^(?:happy\s*path|basic\s*(?:validation|check|flow)|endpoint\s*contract\s*verification|success\s*case)$/i,
    /^returns?\s+(?:success|successful\s+response)$/i,
    /^returns?\s+success\s+response$/i,
    /^returns?\s+successful\s+response$/i,
    /^should\s+return\s+success$/i,
    /^success\s+response$/i,
    /^successful\s+response$/i,
    /^success$/i,
  ];

  for (const pattern of genericSuccessPatterns) {
    if (pattern.test(cleaned)) {
      return null;
    }
  }

  // If nothing remains or remaining text is purely boilerplate
  if (!cleaned) {
    return null;
  }

  // Strip leading scenario glue words: "rejection on", "failure on", "error on", "rejection with", "with", "on", "when", "for"
  let scenarioText = cleaned
    .replace(/^(?:rejection|rejections|failure|failures|error|errors|handles|handling|rejects|fails)\s+(?:on|with|for|when|of)\s+/i, "")
    .replace(/^(?:rejection|failure|error)\s+/i, "")
    .replace(/^(?:on|with|when|for)\s+/i, "")
    .trim();

  // Clean trailing boilerplate like "response", "status", "returns 400", etc.
  scenarioText = scenarioText
    .replace(/\s+(?:returns?\s+(?:error|failure|4\d\d|5\d\d)(?:\s+response)?)$/i, "")
    .trim();

  if (!scenarioText) {
    return null;
  }

  // Format into Title Case
  return toTitleCase(scenarioText);
}

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function toTitleCase(str: string): string {
  // Known acronyms to preserve or uppercase
  const acronyms: Record<string, string> = {
    id: "ID",
    ids: "IDs",
    api: "API",
    ui: "UI",
    json: "JSON",
    xml: "XML",
    http: "HTTP",
    url: "URL",
    brd: "BRD",
  };

  return str
    .split(/\s+/)
    .map((word, index) => {
      const lower = word.toLowerCase();
      if (acronyms[lower]) {
        return acronyms[lower];
      }
      // Minor words if not first
      if (index > 0 && ["and", "or", "of", "in", "for", "on", "with", "a", "an", "the", "to"].includes(lower)) {
        return lower;
      }
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(" ");
}
