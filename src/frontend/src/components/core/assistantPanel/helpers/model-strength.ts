/**
 * classifyModelStrength — pattern-heuristic detector for "weak" agent models.
 *
 * Drives a discreet UX hint in the composer ("Smaller models may underperform
 * on agent tasks") when the user picks a small/lite model from the dropdown.
 * Pure, deterministic, no I/O, no dependencies — safe to call at render time.
 *
 * Design (see also: PR-12575 review B1/B2 thread + the design note in the
 * AskUserQuestion exchange):
 *   1. **Suffix heuristic** — naming conventions are very consistent across
 *      providers for "small" SKUs: nano / mini / micro / tiny / small / lite /
 *      instant / flash / haiku. Word-bounded match avoids false positives on
 *      substrings (e.g. "lumin*ario*" not flagged).
 *   2. **Family denylist** — older generations or known-weak families that
 *      the suffix heuristic doesn't catch (`gpt-3.5`, `claude-instant`,
 *      `gemini-1.0`, `phi-1..3`).
 *   3. **Parameter count** — open-source models typically include their
 *      parameter count (`7b`, `8b`, `13b`). Anything ≤ 13B is too small for
 *      multi-step agent loops in our experience. Requires a digit boundary
 *      so `70b` / `405b` are NOT matched. A LARGE count (≥ 14B) anywhere in
 *      the name short-circuits to strong, so `qwen2.5-coder:32b` is never
 *      flagged by its family.
 *   4. **Bare local-server tags** — Ollama/LM Studio tags often omit the
 *      param count entirely (`llama3.2:latest` is the 3B default;
 *      `mistral` is 7B). The base name (before `:`) is matched against the
 *      known small-default families. Verified live 2026-06-12: llama3.2
 *      and qwen2.5-7b fail the assistant agent loop.
 *   5. **Default: strong** — unknown models are treated as strong so the
 *      hint never appears for a model we simply haven't catalogued.
 *
 * Not a security gate. The classification is advisory; the UI behavior is
 * identical regardless of the result.
 */

// Word-bounded suffixes/qualifiers that providers use to label smaller SKUs.
const WEAK_SUFFIX_PATTERN =
  /\b(nano|mini|micro|tiny|small|lite|instant|flash|haiku)\b/i;

// Whole-family deny patterns for older / known-weak generations.
const WEAK_FAMILY_PATTERNS: RegExp[] = [
  /\bgpt-3(\.5)?\b/i, // gpt-3, gpt-3.5(.x)
  /\bclaude-instant\b/i, // legacy Anthropic small SKU
  /\bgemini-1\.0\b/i, // first-gen Gemini
  /\bphi-?[1-3]\b/i, // Microsoft Phi 1/2/3 family (all small)
];

// Parameter count ≤ 13B (open-source models: llama, gemma, granite, qwen,
// mistral-7b, etc.). Requires the digit run to NOT be preceded by another
// digit, so `70b` / `405b` / `175b` are NOT captured.
const SMALL_PARAM_PATTERN = /(?<![\d])([1-9]|1[0-3])b\b/i;

// Parameter count ≥ 14B anywhere in the name (e.g. ":32b", "-70b") proves
// the SKU is large even when the base family defaults to a small size.
const LARGE_PARAM_PATTERN = /(?<![\d.])(1[4-9]|[2-9]\d|\d{3,})b\b/i;

// Families that are unreliable on agent tasks regardless of size — e.g.
// gpt-oss on local runtimes leaks harmony reasoning into the tool-call
// channel, emits malformed calls and churns to the recursion limit
// (verified live 2026-06-12). Checked BEFORE the size override.
const UNRELIABLE_AGENT_BASE_NAMES = new Set(["gpt-oss"]);

// Local-server base names (before the ":tag") whose DEFAULT size is ≤ 13B.
const SMALL_DEFAULT_BASE_NAMES = new Set([
  "llama2",
  "llama3",
  "llama3.1",
  "llama3.2",
  "llama3-groq-tool-use",
  "mistral",
  "mistral-nemo",
  "qwen",
  "qwen2",
  "qwen2.5",
  "qwen2.5-coder",
  "qwen3",
  "gemma",
  "gemma2",
  "gemma3",
  "smollm2",
  "hermes3",
  "granite3-dense",
  "granite3.1-dense",
  "granite3-moe",
  "aya-expanse",
  "cogito",
]);

export type ModelStrength = "weak" | "strong";

export function classifyModelStrength(modelName: string): ModelStrength {
  if (!modelName) return "strong";
  const name = modelName.toLowerCase();

  if (UNRELIABLE_AGENT_BASE_NAMES.has(name.split(":")[0])) return "weak";
  if (LARGE_PARAM_PATTERN.test(name)) return "strong";
  if (WEAK_SUFFIX_PATTERN.test(name)) return "weak";
  if (WEAK_FAMILY_PATTERNS.some((re) => re.test(name))) return "weak";
  if (SMALL_DEFAULT_BASE_NAMES.has(name.split(":")[0])) return "weak";
  if (SMALL_PARAM_PATTERN.test(name)) return "weak";

  return "strong";
}
