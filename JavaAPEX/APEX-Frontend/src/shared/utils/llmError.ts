/**
 * Utility helpers for consistent LLM-not-configured error handling.
 *
 * The backend returns the sentinel string "LLM_NOT_CONFIGURED" in the error
 * detail / message whenever the user or admin has not yet saved LLM credentials.
 * Every UI surface that can trigger an LLM call should use these helpers so that
 * the user always sees the same, actionable message.
 */

export const LLM_NOT_CONFIGURED_SENTINEL = "LLM_NOT_CONFIGURED";
export const LLM_NOT_CONFIGURED_UI_MESSAGE =
  "⚠️ LLM is not configured. Please set up your AI provider credentials in Settings → Intelligence.";

/**
 * Returns true if the error represents a missing LLM configuration.
 */
export function isLlmNotConfiguredError(err: unknown): boolean {
  if (err instanceof Error) {
    const msg = err.message;
    return (
      msg === LLM_NOT_CONFIGURED_SENTINEL ||
      msg.toLowerCase().includes("llm is not configured") ||
      msg.toLowerCase().includes("llm_not_configured")
    );
  }
  if (typeof err === "string") {
    return (
      err === LLM_NOT_CONFIGURED_SENTINEL ||
      err.toLowerCase().includes("llm is not configured") ||
      err.toLowerCase().includes("llm_not_configured")
    );
  }
  return false;
}

/**
 * Translates any error into a user-friendly string.
 * If the error indicates a missing LLM configuration, returns the standard
 * actionable message. Otherwise returns the error's own message or fallback.
 */
export function formatLlmAwareError(err: unknown, fallback = "An unexpected error occurred."): string {
  if (isLlmNotConfiguredError(err)) {
    return LLM_NOT_CONFIGURED_UI_MESSAGE;
  }
  if (err instanceof Error) {
    return err.message || fallback;
  }
  if (typeof err === "string" && err.trim()) {
    return err;
  }
  return fallback;
}

/**
 * Takes an already-resolved error string (e.g. one pulled from setError state)
 * and returns a display-safe, human-readable version.
 * Useful in render functions that just want to show `error` from state.
 */
export function displayError(error: string | null | undefined): string {
  if (!error) return "";
  return isLlmNotConfiguredError(error) ? LLM_NOT_CONFIGURED_UI_MESSAGE : error;
}
