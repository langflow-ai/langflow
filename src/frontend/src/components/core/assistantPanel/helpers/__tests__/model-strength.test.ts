/**
 * classifyModelStrength — pattern-heuristic detector for "weak" agent models.
 *
 * Drives a discreet hint in the assistant composer ("Smaller models may
 * underperform on agent tasks") when the user picks a small/lite model.
 * Pure, deterministic, no I/O. Adversarial coverage across every provider
 * the assistant integrates with — adding a new provider here is how we
 * keep the heuristic honest as the model catalog evolves.
 */

import { classifyModelStrength } from "../model-strength";

describe("classifyModelStrength", () => {
  describe("weak — suffix heuristics (cross-provider)", () => {
    it.each([
      // OpenAI nano/mini family
      "gpt-5.4-nano",
      "gpt-5-nano",
      "gpt-4.1-nano",
      "gpt-5.4-mini",
      "gpt-4o-mini",
      "gpt-4.1-mini",
      "o3-mini",
      "o4-mini",
      // Anthropic haiku
      "claude-haiku-4-5",
      "claude-3-5-haiku-latest",
      "claude-3-haiku-20240307",
      // Google flash
      "gemini-2.5-flash",
      "gemini-1.5-flash",
      "gemini-2.0-flash-lite",
      // generic
      "mistral-tiny",
      "qwen-2.5-7b-instruct-lite",
      "phi-3-mini-4k",
    ])("classifies %s as weak", (model) => {
      expect(classifyModelStrength(model)).toBe("weak");
    });
  });

  describe("weak — known weak families", () => {
    it.each([
      "gpt-3.5-turbo",
      "gpt-3.5-turbo-0125",
      "claude-instant-1.2",
      "gemini-1.0-pro",
      "phi-3-medium",
      "phi-2",
    ])("classifies %s as weak", (model) => {
      expect(classifyModelStrength(model)).toBe("weak");
    });
  });

  describe("weak — small parameter counts (open-source)", () => {
    it.each([
      // Llama
      "llama-3.2-1b",
      "llama-3.2-3b",
      "llama-3.1-8b-instruct",
      "meta-llama/llama-3-8b",
      // Gemma
      "gemma-2b",
      "gemma-7b-it",
      "gemma-2-9b",
      // IBM Granite (per the IBM WatsonX integration)
      "granite-3-2b-instruct",
      "granite-3-8b-instruct",
      // Qwen
      "qwen-2.5-7b",
      // Mistral
      "mistral-7b-instruct",
      "open-mistral-7b",
    ])("classifies %s as weak (param ≤ 13B)", (model) => {
      expect(classifyModelStrength(model)).toBe("weak");
    });
  });

  describe("strong — flagship / large models stay strong", () => {
    it.each([
      // OpenAI flagships
      "gpt-5.4",
      "gpt-5",
      "gpt-4o",
      "gpt-4.1",
      "gpt-4-turbo",
      "o1",
      "o3",
      // Anthropic flagships
      "claude-opus-4-7",
      "claude-sonnet-4-6",
      "claude-3-5-sonnet-20241022",
      "claude-3-opus-20240229",
      // Google flagships
      "gemini-2.5-pro",
      "gemini-1.5-pro",
      "gemini-ultra",
      // Open-source large
      "llama-3.1-70b-instruct",
      "llama-3.1-405b",
      "mistral-large-2411",
      "mistral-medium",
      "qwen-2.5-72b",
      // IBM larger Granite
      "granite-3-34b",
    ])("classifies %s as strong", (model) => {
      expect(classifyModelStrength(model)).toBe("strong");
    });
  });

  describe("strong — defensive defaults", () => {
    it("classifies an unknown/empty name as strong (don't pollute the UI)", () => {
      expect(classifyModelStrength("")).toBe("strong");
      expect(classifyModelStrength("acme-unknown-model-2030")).toBe("strong");
    });

    it("is case-insensitive on the canonical suffixes", () => {
      expect(classifyModelStrength("GPT-4O-MINI")).toBe("weak");
      expect(classifyModelStrength("Claude-Haiku-4-5")).toBe("weak");
    });

    it("does not false-positive on substrings that aren't word-bounded", () => {
      // "luminario" contains "min" but not "mini" as a token.
      expect(classifyModelStrength("luminario-pro")).toBe("strong");
      // "phisical-pro" contains "phi" but not "phi-N"
      expect(classifyModelStrength("phisical-pro")).toBe("strong");
    });

    it("does not flag a 70B as weak just because the name also has '7'", () => {
      // Regression guard: the param regex must require the trailing B and the
      // proper word boundary so 70b/405b do not match the small-param branch.
      expect(classifyModelStrength("llama-3.1-70b")).toBe("strong");
      expect(classifyModelStrength("llama-3.1-405b")).toBe("strong");
    });
  });
});
