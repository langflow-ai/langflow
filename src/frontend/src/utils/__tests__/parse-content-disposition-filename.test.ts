import { parseContentDispositionFilename } from "../parse-content-disposition-filename";

describe("parseContentDispositionFilename", () => {
  it("returns fallback when header is null", () => {
    expect(parseContentDispositionFilename(null, "default.txt")).toBe(
      "default.txt",
    );
  });

  it("returns fallback when header is empty string", () => {
    expect(parseContentDispositionFilename("", "default.txt")).toBe(
      "default.txt",
    );
  });

  it("parses plain filename= without quotes", () => {
    expect(
      parseContentDispositionFilename(
        "attachment; filename=simple.txt",
        "fallback.txt",
      ),
    ).toBe("simple.txt");
  });

  it("parses plain filename= with quotes", () => {
    expect(
      parseContentDispositionFilename(
        'attachment; filename="quoted.txt"',
        "fallback.txt",
      ),
    ).toBe("quoted.txt");
  });

  it("prefers filename*= over filename= when both present", () => {
    expect(
      parseContentDispositionFilename(
        "attachment; filename=\"ascii.txt\"; filename*=UTF-8''%E9%BE%99.txt",
        "fallback.txt",
      ),
    ).toBe("龙.txt");
  });

  it("decodes CJK characters from RFC 5987 value", () => {
    expect(
      parseContentDispositionFilename(
        "attachment; filename*=UTF-8''%E9%BE%99.txt",
        "fallback.txt",
      ),
    ).toBe("龙.txt");
  });

  it("decodes accented Latin characters from RFC 5987 value", () => {
    expect(
      parseContentDispositionFilename(
        "attachment; filename*=UTF-8''arquivo_com_acentua%C3%A7%C3%A3o.txt",
        "fallback.txt",
      ),
    ).toBe("arquivo_com_acentuação.txt");
  });

  it("falls back to filename= when RFC 5987 decoding throws", () => {
    expect(
      parseContentDispositionFilename(
        "attachment; filename=\"fallback.txt\"; filename*=UTF-8''%invalid%",
        "default.txt",
      ),
    ).toBe("fallback.txt");
  });

  it("returns fallback when neither param is present", () => {
    expect(parseContentDispositionFilename("attachment", "default.txt")).toBe(
      "default.txt",
    );
  });

  it("handles semicolons inside the RFC 5987 encoded value correctly", () => {
    // semicolon is percent-encoded in the value, so the regex stops at literal ;
    expect(
      parseContentDispositionFilename(
        "attachment; filename*=UTF-8''hello%3Bworld.txt",
        "fallback.txt",
      ),
    ).toBe("hello;world.txt");
  });
});
