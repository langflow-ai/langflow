import { fstringStrategy, mustacheStrategy } from "../strategies";

// The modal owns `t`; the strategies only receive a resolver. A marker keeps the
// assertions about *which* message is requested — the real bundle, and the attribute
// escaping it needs, are covered in var-highlight-html.test.ts.
const RESERVED_PREFIX_KEY = "modal.prompt.invalidVariable.reservedPrefix";
const translate = (key: string): string => `msg:${key}`;

describe("fstringStrategy.renderColoredContent", () => {
  it("highlights an accepted variable and keeps its braces inside the span", () => {
    expect(
      fstringStrategy.renderColoredContent("hello {name}", translate),
    ).toBe(
      'hello <span class="font-semibold chat-message-highlight">{name}</span>',
    );
  });

  it("marks a reserved-prefix variable and attaches the reason as a tooltip", () => {
    const html = fstringStrategy.renderColoredContent("{_type}", translate);

    expect(html).toContain("chat-message-highlight-invalid");
    expect(html).toContain(`title="msg:${RESERVED_PREFIX_KEY}"`);
  });

  it("leaves a fenced code block untouched while still highlighting real variables", () => {
    // Regression guard: regexHighlight captures the fence as group 1, so a callback
    // that forgets it reads the fence as the opening brace run — and then nothing in
    // the template is highlighted at all.
    const html = fstringStrategy.renderColoredContent(
      "```{not_a_var}``` and {name}",
      translate,
    );

    expect(html).toContain("```{not_a_var}```");
    expect(html).toContain(
      '<span class="font-semibold chat-message-highlight">{name}</span>',
    );
  });

  it("leaves a double-brace escape unhighlighted", () => {
    expect(fstringStrategy.renderColoredContent("{{escaped}}", translate)).toBe(
      "{{escaped}}",
    );
  });

  it("reads the field name, so a format spec stays valid", () => {
    // `{x:>10}` is the variable `x` — the backend's Formatter cuts at the colon.
    expect(
      fstringStrategy.renderColoredContent("{x:>10}", translate),
    ).toContain(
      '<span class="font-semibold chat-message-highlight">{x:&gt;10}</span>',
    );
  });

  it("asks for no message when every name is accepted", () => {
    const spy = jest.fn(translate);
    fstringStrategy.renderColoredContent("{name} and {other}", spy);
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("mustacheStrategy.renderColoredContent", () => {
  it("highlights an accepted variable keeping the rendered double braces", () => {
    expect(
      mustacheStrategy.renderColoredContent("hi {{name}}", translate),
    ).toBe(
      'hi <span class="font-semibold chat-message-highlight">{{name}}</span>',
    );
  });

  it("marks a reserved-prefix variable and attaches the reason as a tooltip", () => {
    const html = mustacheStrategy.renderColoredContent("{{_type}}", translate);

    expect(html).toContain("chat-message-highlight-invalid");
    expect(html).toContain(`title="msg:${RESERVED_PREFIX_KEY}"`);
  });

  it("reads the rule from the bare name, not from the braced text", () => {
    // The rendered text is `{{_x}}`; the rule has to run on `_x`, or the leading brace
    // would make every mustache variable look accepted.
    expect(
      mustacheStrategy.renderColoredContent("{{_x}}", translate),
    ).toContain("chat-message-highlight-invalid");
  });
});
