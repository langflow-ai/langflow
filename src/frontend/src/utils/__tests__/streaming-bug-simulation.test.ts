/**
 * This test simulates the bug reported by Rodrigo:
 * - During streaming, code blocks appeared duplicated/split into 2 blocks
 * - When leaving and returning to playground, it rendered correctly
 *
 * Root cause: The old isCodeBlock() used `hasNewlines` as a criterion,
 * which caused content with newlines to be treated as code blocks
 * even without proper language markers.
 */

// Simulate the OLD buggy implementation
function isCodeBlockOLD(
  className: string | undefined,
  props: Record<string, unknown> | undefined,
  content: string,
): boolean {
  const languageMatch = /language-(\w+)/.exec(className ?? "");
  const hasLanguageClass = !!languageMatch;
  const hasDataLanguage = "data-language" in (props ?? {});
  const hasNewlines = content.includes("\n"); // BUG: This caused the issue!

  return hasLanguageClass || hasDataLanguage || hasNewlines;
}

// Import the NEW fixed implementation
import { isCodeBlock as isCodeBlockNEW } from "../codeBlockUtils";

describe("Streaming Bug Simulation - Rodrigo's Report", () => {
  describe("Scenario: Code being streamed in chunks", () => {
    /**
     * During streaming, react-markdown processes content progressively.
     * The markdown parser may create multiple <code> elements when
     * the code block is incomplete or being updated.
     *
     * Example markdown being streamed:
     * ```python
     * output_data = {
     *     "total_iterations": iteration_count,
     *     "termination_reason": termination_reason,
     * }
     * ```
     *
     * During streaming, this might be split into fragments by the parser.
     */

    const streamingFragment1 = `output_data = {
    "total_iterations": iteration_count,`;

    const streamingFragment2 = `
    "termination_reason": termination_reason,
    "results": results,
}`;

    const completeCode = `output_data = {
    "total_iterations": iteration_count,
    "termination_reason": termination_reason,
    "results": results,
}`;

    describe("OLD buggy behavior (before fix)", () => {
      it("should_incorrectly_treat_streaming_fragments_as_code_blocks", () => {
        // Without language class or data-language, but WITH newlines
        // OLD implementation would return TRUE (BUG!)

        const fragment1IsBlock = isCodeBlockOLD(
          undefined,
          {},
          streamingFragment1,
        );
        const fragment2IsBlock = isCodeBlockOLD(
          undefined,
          {},
          streamingFragment2,
        );

        // BUG: Both fragments are treated as separate code blocks!
        expect(fragment1IsBlock).toBe(true); // Wrong! Should be false
        expect(fragment2IsBlock).toBe(true); // Wrong! Should be false

        // This caused the visual bug: 2 separate code blocks rendered
        console.log("OLD BEHAVIOR (BUGGY):");
        console.log(
          `Fragment 1 is block: ${fragment1IsBlock} (should be false)`,
        );
        console.log(
          `Fragment 2 is block: ${fragment2IsBlock} (should be false)`,
        );
      });

      it("should_show_why_duplicate_blocks_appeared", () => {
        // Simulating what happens during streaming:
        // 1. First chunk arrives with newlines -> treated as block
        // 2. Second chunk arrives with newlines -> treated as ANOTHER block
        // Result: 2 code blocks instead of 1!

        const chunks = [
          "def hello():\n    print('world')",
          "\n\nself.status = f'Completed'",
          "\n\nreturn Data(data=output_data)",
        ];

        const blocksCreated = chunks.filter((chunk) =>
          isCodeBlockOLD(undefined, {}, chunk),
        );

        // BUG: All 3 chunks become separate blocks!
        expect(blocksCreated.length).toBe(3);
        console.log(
          `OLD: ${blocksCreated.length} blocks created from ${chunks.length} chunks`,
        );
      });
    });

    describe("NEW fixed behavior (after fix)", () => {
      it("should_not_treat_streaming_fragments_as_code_blocks_without_language_marker", () => {
        // Without language class or data-language
        // NEW implementation correctly returns FALSE

        const fragment1IsBlock = isCodeBlockNEW(
          undefined,
          {},
          streamingFragment1,
        );
        const fragment2IsBlock = isCodeBlockNEW(
          undefined,
          {},
          streamingFragment2,
        );

        // FIXED: Neither fragment is treated as a code block
        expect(fragment1IsBlock).toBe(false);
        expect(fragment2IsBlock).toBe(false);

        console.log("NEW BEHAVIOR (FIXED):");
        console.log(`Fragment 1 is block: ${fragment1IsBlock} (correct!)`);
        console.log(`Fragment 2 is block: ${fragment2IsBlock} (correct!)`);
      });

      it("should_only_create_one_block_when_properly_marked", () => {
        // When react-markdown properly identifies the code block,
        // it adds the language class. Only then should it be a block.

        const chunks = [
          "def hello():\n    print('world')",
          "\n\nself.status = f'Completed'",
          "\n\nreturn Data(data=output_data)",
        ];

        // Without language markers: no blocks
        const blocksWithoutMarker = chunks.filter((chunk) =>
          isCodeBlockNEW(undefined, {}, chunk),
        );
        expect(blocksWithoutMarker.length).toBe(0);

        // With language marker: all become blocks (as expected when properly parsed)
        const blocksWithMarker = chunks.filter((chunk) =>
          isCodeBlockNEW("language-python", {}, chunk),
        );
        expect(blocksWithMarker.length).toBe(3);

        console.log(
          `NEW: ${blocksWithoutMarker.length} blocks without marker (correct: 0)`,
        );
        console.log(
          `NEW: ${blocksWithMarker.length} blocks with marker (correct: all)`,
        );
      });

      it("should_handle_complete_code_correctly_when_streaming_ends", () => {
        // When streaming completes and markdown is re-parsed,
        // the code block gets proper language class

        // During streaming (no marker yet)
        const duringStreaming = isCodeBlockNEW(undefined, {}, completeCode);
        expect(duringStreaming).toBe(false);

        // After streaming (parser adds language class)
        const afterStreaming = isCodeBlockNEW(
          "language-python",
          {},
          completeCode,
        );
        expect(afterStreaming).toBe(true);

        console.log("Complete code handling:");
        console.log(`During streaming (no marker): ${duringStreaming}`);
        console.log(`After streaming (with marker): ${afterStreaming}`);
      });
    });

    describe("Visual comparison of the bug", () => {
      it("should_demonstrate_the_difference", () => {
        const testContent = `"Condition threshold reached"
if iteration_count >= condition_threshold
else "Max iterations reached"`;

        const oldResult = isCodeBlockOLD(undefined, {}, testContent);
        const newResult = isCodeBlockNEW(undefined, {}, testContent);

        console.log("\n=== BUG DEMONSTRATION ===");
        console.log("Content with newlines but NO language marker:");
        console.log(
          `OLD isCodeBlock(): ${oldResult} -> Would render as code block (BUG)`,
        );
        console.log(
          `NEW isCodeBlock(): ${newResult} -> Correctly NOT a code block (FIXED)`,
        );

        expect(oldResult).toBe(true); // Bug
        expect(newResult).toBe(false); // Fixed
      });
    });
  });
});
