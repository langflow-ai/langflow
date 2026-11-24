import { regexHighlight } from "@/constants/constants";
import en from "@/locales/en.json";
import varHighlightHTML from "../var-highlight-html";

describe("varHighlightHTML", () => {
  it("uses the regular class for an accepted name", () => {
    expect(varHighlightHTML({ name: "var" })).toBe(
      '<span class="font-semibold chat-message-highlight">var</span>',
    );
  });

  it("uses the invalid class for a name starting with an underscore", () => {
    expect(varHighlightHTML({ name: "_x" })).toBe(
      '<span class="font-semibold chat-message-highlight-invalid">_x</span>',
    );
  });

  it.each(["1var", "my var", "code"])(
    "uses the invalid class for %s too, the way Check & Save does",
    (name) => {
      expect(varHighlightHTML({ name })).toContain(
        "chat-message-highlight-invalid",
      );
    },
  );

  it("leaves a format spec alone, since the backend reads only the field name", () => {
    // `{x:>10}` is the variable `x`, and `{"a": 1}` is a JSON literal the backend accepts.
    expect(varHighlightHTML({ name: "x:>10" })).toContain(
      '<span class="font-semibold chat-message-highlight">',
    );
    expect(varHighlightHTML({ name: '"a": 1' })).toContain(
      '<span class="font-semibold chat-message-highlight">',
    );
  });

  it("reads the rule from variableName when it differs from the rendered text", () => {
    // Mustache renders its own braces, so the bare identifier arrives separately.
    expect(
      varHighlightHTML({
        name: "{{_x}}",
        addCurlyBraces: false,
        variableName: "_x",
      }),
    ).toContain("chat-message-highlight-invalid");
  });

  it("adds the tooltip only when the name is reserved", () => {
    expect(
      varHighlightHTML({ name: "_x", invalidTitle: "reserved prefix" }),
    ).toContain('title="reserved prefix"');
    expect(
      varHighlightHTML({ name: "var", invalidTitle: "reserved prefix" }),
    ).not.toContain("title=");
  });

  it("keeps a quoted tooltip whole in the DOM", () => {
    // en/pt/es quote the prefix with a plain `"`. Unescaped, it closed the attribute and
    // the browser read only "Variable names can't start with ", scattering the rest of
    // the sentence into stray attributes.
    const title = en["modal.prompt.invalidVariable.reservedPrefix"];
    document.body.innerHTML = varHighlightHTML({
      name: "_x",
      addCurlyBraces: true,
      invalidTitle: title,
    });

    const span = document.querySelector("span")!;
    expect(span.getAttribute("title")).toBe(title);
    expect(Array.from(span.attributes).map((a) => a.name)).toEqual([
      "class",
      "title",
    ]);
  });
});

describe("regexHighlight group order", () => {
  // The prompt editor destructured this regex without its first group, which shifted
  // every capture by one and silently disabled highlighting in the modal. Pin the shape
  // so the callbacks that consume it cannot drift again.
  it("captures code fence, opening run, name and closing run in that order", () => {
    const [, codeFence, openRun, varName, closeRun] = new RegExp(
      regexHighlight.source,
    ).exec("Hello {_x}!")!;

    expect(codeFence).toBeUndefined();
    expect(openRun).toBe("{");
    expect(varName).toBe("_x");
    expect(closeRun).toBe("}");
  });
});
