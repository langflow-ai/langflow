import { getHighlightedHTML } from "../prompt-highlight";

// This helper drives the prompt preview the user actually sees on the node whenever the
// inspection panel is enabled, so the reserved-name marking has to reach it too.
describe("getHighlightedHTML", () => {
  describe("f-string", () => {
    it("marks a name starting with an underscore as invalid", () => {
      expect(getHighlightedHTML("Hello {_x}!", false)).toContain(
        '<span class="chat-message-highlight-invalid">{_x}</span>',
      );
    });

    it("keeps a regular name highlighted normally", () => {
      expect(getHighlightedHTML("Hello {var}!", false)).toContain(
        '<span class="chat-message-highlight">{var}</span>',
      );
    });

    it("marks only the offending variable in a mixed template", () => {
      const html = getHighlightedHTML("Hello {_x}, meet {var}.", false);
      expect(html).toContain(
        '<span class="chat-message-highlight-invalid">{_x}</span>',
      );
      expect(html).toContain(
        '<span class="chat-message-highlight">{var}</span>',
      );
    });

    it("leaves an underscore that is not the first character valid", () => {
      expect(getHighlightedHTML("Hi {user_name}!", false)).toContain(
        '<span class="chat-message-highlight">{user_name}</span>',
      );
    });

    it.each(["1var", "my var", "code"])(
      "marks %s as invalid, the way Check & Save does",
      (name) => {
        expect(getHighlightedHTML(`Hello {${name}}!`, false)).toContain(
          `<span class="chat-message-highlight-invalid">{${name}}</span>`,
        );
      },
    );

    it("leaves a JSON literal highlighted normally", () => {
      // The backend reads the field name up to the `:`, so `{"a": 1}` is accepted.
      expect(getHighlightedHTML('Payload {"a": 1}', false)).toContain(
        '<span class="chat-message-highlight">',
      );
      expect(getHighlightedHTML('Payload {"a": 1}', false)).not.toContain(
        "chat-message-highlight-invalid",
      );
    });
  });

  describe("double brackets", () => {
    it("marks a name starting with an underscore as invalid", () => {
      expect(getHighlightedHTML("Hello {{_x}}!", true)).toContain(
        '<span class="chat-message-highlight-invalid">{{_x}}</span>',
      );
    });

    it("keeps a regular name highlighted normally", () => {
      expect(getHighlightedHTML("Hello {{var}}!", true)).toContain(
        '<span class="chat-message-highlight">{{var}}</span>',
      );
    });

    it("marks a reserved name as invalid", () => {
      expect(getHighlightedHTML("Hello {{code}}!", true)).toContain(
        '<span class="chat-message-highlight-invalid">{{code}}</span>',
      );
    });
  });
});
