import DOMPurify from "dompurify";

/**
 * XSS Security Tests for Chat Message Sanitization
 *
 * These tests verify that DOMPurify correctly sanitizes malicious content
 * before it's rendered in chat messages. The sanitization happens in the
 * MarkdownField component via useMemo to prevent XSS attacks.
 */

describe("Chat Message XSS Security", () => {
  describe("DOMPurify Sanitization", () => {
    // Test cases with malicious input and expected safe output
    const xssTestCases = [
      {
        name: "script tag injection",
        input: '<script>alert("XSS")</script>Hello',
        shouldNotContain: ["<script>", "alert"],
        shouldContain: ["Hello"],
      },
      {
        name: "img onerror handler",
        input: '<img src="x" onerror="alert(\'XSS\')">',
        shouldNotContain: ["onerror", "alert"],
      },
      {
        name: "javascript: protocol in link",
        input: "<a href=\"javascript:alert('XSS')\">Click</a>",
        shouldNotContain: ["javascript:"],
        shouldContain: ["Click"],
      },
      {
        name: "onclick event handler",
        input: "<div onclick=\"alert('XSS')\">Click me</div>",
        shouldNotContain: ["onclick", "alert"],
        shouldContain: ["Click me"],
      },
      {
        name: "iframe injection",
        input: "<iframe src=\"javascript:alert('XSS')\"></iframe>",
        shouldNotContain: ["<iframe", "javascript:"],
      },
      {
        name: "SVG with script",
        input: '<svg><script>alert("XSS")</script></svg>',
        shouldNotContain: ["<script>", "alert"],
      },
      {
        name: "data URI with script",
        input: "<img src=\"data:text/html,<script>alert('XSS')</script>\">",
        shouldNotContain: ["data:text/html", "<script>"],
      },
      {
        name: "style tag with expression",
        input:
          "<style>body{background:url(\"javascript:alert('XSS')\")}</style>",
        shouldNotContain: ["<style>", "javascript:"],
      },
      {
        name: "object tag",
        input: "<object data=\"javascript:alert('XSS')\"></object>",
        shouldNotContain: ["<object", "javascript:"],
      },
      {
        name: "embed tag",
        input: "<embed src=\"javascript:alert('XSS')\">",
        shouldNotContain: ["<embed", "javascript:"],
      },
      {
        name: "meta refresh redirect",
        input:
          '<meta http-equiv="refresh" content="0;url=javascript:alert(\'XSS\')">',
        shouldNotContain: ["<meta", "javascript:"],
      },
      {
        name: "link stylesheet with javascript",
        input: '<link rel="stylesheet" href="javascript:alert(\'XSS\')">',
        shouldNotContain: ["javascript:"],
      },
      {
        name: "base tag hijacking",
        input: "<base href=\"javascript:alert('XSS')//\">",
        shouldNotContain: ["<base", "javascript:"],
      },
      {
        name: "form action javascript",
        input:
          '<form action="javascript:alert(\'XSS\')"><input type="submit"></form>',
        shouldNotContain: ["javascript:"],
      },
      {
        name: "input with autofocus and onfocus",
        input: "<input autofocus onfocus=\"alert('XSS')\">",
        shouldNotContain: ["onfocus", "alert"],
      },
      {
        name: "marquee with onstart",
        input: "<marquee onstart=\"alert('XSS')\">Text</marquee>",
        shouldNotContain: ["onstart", "alert"],
      },
      {
        name: "body with onload",
        input: "<body onload=\"alert('XSS')\">",
        shouldNotContain: ["onload", "alert"],
      },
      {
        name: "video with onerror",
        input: '<video src="x" onerror="alert(\'XSS\')"></video>',
        shouldNotContain: ["onerror", "alert"],
      },
      {
        name: "audio with onerror",
        input: '<audio src="x" onerror="alert(\'XSS\')"></audio>',
        shouldNotContain: ["onerror", "alert"],
      },
      {
        name: "details with ontoggle",
        input:
          "<details ontoggle=\"alert('XSS')\"><summary>Click</summary></details>",
        shouldNotContain: ["ontoggle", "alert"],
      },
      {
        name: "svg with onload",
        input: "<svg onload=\"alert('XSS')\"></svg>",
        shouldNotContain: ["onload", "alert"],
      },
    ];

    test.each(xssTestCases)(
      "should sanitize $name",
      ({ input, shouldNotContain, shouldContain }) => {
        const sanitized = DOMPurify.sanitize(input);
        const lowerSanitized = sanitized.toLowerCase();

        // Verify dangerous content is removed
        if (shouldNotContain) {
          shouldNotContain.forEach((dangerous) => {
            expect(lowerSanitized).not.toContain(dangerous.toLowerCase());
          });
        }

        // Verify safe content is preserved
        if (shouldContain) {
          shouldContain.forEach((safe) => {
            expect(sanitized).toContain(safe);
          });
        }
      },
    );
  });

  describe("Safe Content Preservation", () => {
    it("should preserve safe HTML elements", () => {
      const safeInput = "<p>Hello <strong>world</strong></p>";
      const sanitized = DOMPurify.sanitize(safeInput);

      expect(sanitized).toContain("<p>");
      expect(sanitized).toContain("<strong>");
      expect(sanitized).toContain("Hello");
      expect(sanitized).toContain("world");
    });

    it("should preserve safe links", () => {
      const safeLink = '<a href="https://example.com">Safe Link</a>';
      const sanitized = DOMPurify.sanitize(safeLink);

      expect(sanitized).toContain("https://example.com");
      expect(sanitized).toContain("Safe Link");
    });

    it("should preserve markdown-like content", () => {
      const markdown = "**Bold** and *italic* text";
      const sanitized = DOMPurify.sanitize(markdown);

      expect(sanitized).toBe(markdown);
    });
  });

  describe("Think Tag Handling", () => {
    it("should preserve backticked think tags after sanitization", () => {
      // Simulate the marker replacement pattern used in the component
      const THINK_OPEN_MARKER = "___THINK_OPEN___";
      const THINK_CLOSE_MARKER = "___THINK_CLOSE___";

      const input = "Some text `<think>` more text `</think>` end";

      // Replace with markers before sanitization
      const withMarkers = input
        .replace(/`<think>`/g, THINK_OPEN_MARKER)
        .replace(/`<\/think>`/g, THINK_CLOSE_MARKER);

      // Sanitize
      const sanitized = DOMPurify.sanitize(withMarkers);

      // Restore markers
      const restored = sanitized
        .replace(new RegExp(THINK_OPEN_MARKER, "g"), "`<think>`")
        .replace(new RegExp(THINK_CLOSE_MARKER, "g"), "`</think>`");

      expect(restored).toContain("`<think>`");
      expect(restored).toContain("`</think>`");
    });

    it("should handle multiple think tags", () => {
      const THINK_OPEN_MARKER = "___THINK_OPEN___";
      const THINK_CLOSE_MARKER = "___THINK_CLOSE___";

      const input =
        "`<think>` first `</think>` middle `<think>` second `</think>`";

      const withMarkers = input
        .replace(/`<think>`/g, THINK_OPEN_MARKER)
        .replace(/`<\/think>`/g, THINK_CLOSE_MARKER);

      const sanitized = DOMPurify.sanitize(withMarkers);

      const restored = sanitized
        .replace(new RegExp(THINK_OPEN_MARKER, "g"), "`<think>`")
        .replace(new RegExp(THINK_CLOSE_MARKER, "g"), "`</think>`");

      // Count occurrences
      const openCount = (restored.match(/`<think>`/g) || []).length;
      const closeCount = (restored.match(/`<\/think>`/g) || []).length;

      expect(openCount).toBe(2);
      expect(closeCount).toBe(2);
    });
  });

  describe("Edge Cases", () => {
    it("should handle empty strings", () => {
      expect(DOMPurify.sanitize("")).toBe("");
    });

    it("should handle whitespace-only strings", () => {
      const whitespace = "   \n  \t  ";
      expect(DOMPurify.sanitize(whitespace)).toBe(whitespace);
    });

    it("should handle mixed safe and malicious content", () => {
      const mixed = 'Hello <script>alert("XSS")</script> **world**';
      const sanitized = DOMPurify.sanitize(mixed);

      expect(sanitized).toContain("Hello");
      expect(sanitized).toContain("world");
      expect(sanitized.toLowerCase()).not.toContain("<script>");
      expect(sanitized.toLowerCase()).not.toContain("alert");
    });

    it("should handle deeply nested malicious content", () => {
      const nested =
        '<div><div><div><script>alert("XSS")</script></div></div></div>';
      const sanitized = DOMPurify.sanitize(nested);

      expect(sanitized.toLowerCase()).not.toContain("<script>");
      expect(sanitized.toLowerCase()).not.toContain("alert");
    });

    it("should handle HTML entities", () => {
      const encoded = '<script>alert("XSS")</script>';
      const sanitized = DOMPurify.sanitize(encoded);

      // DOMPurify decodes entities and then sanitizes, so malicious script tags are removed
      // The result should not contain executable script tags
      expect(sanitized.toLowerCase()).not.toContain("<script>");
      expect(sanitized.toLowerCase()).not.toContain("alert");
    });
  });

  describe("Performance Considerations", () => {
    it("should handle large inputs efficiently", () => {
      const largeInput = "Safe text ".repeat(1000);
      const start = performance.now();
      const sanitized = DOMPurify.sanitize(largeInput);
      const duration = performance.now() - start;

      expect(sanitized).toContain("Safe text");
      expect(duration).toBeLessThan(100); // Should complete in < 100ms
    });

    it("should handle repeated sanitization calls", () => {
      const input = '<script>alert("XSS")</script>Hello';

      // Simulate multiple renders
      for (let i = 0; i < 10; i++) {
        const sanitized = DOMPurify.sanitize(input);
        expect(sanitized.toLowerCase()).not.toContain("<script>");
      }
    });
  });
});

// Made with Bob
