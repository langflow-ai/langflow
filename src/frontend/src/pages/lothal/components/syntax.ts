// Lightweight, dependency-free syntax tokenizer for the lothal Code view.
//
// The generated files in Lothal are short scaffolds, not a full IDE buffer, so
// the design calls for "lightweight syntax highlight" — enough to make code
// readable without pulling in Prism / highlight.js / CodeMirror. This is a small
// single-pass tokenizer: at each position it tries comment / string / number /
// identifier rules (in that order, so strings and comments win over keywords),
// emitting `plain` for anything else. CodeView maps the token types onto theme
// colors. It is deliberately approximate — correctness of the *render*, not of a
// real parser.
//
// Reviewed 2026-06-09 (code-review finding 7) and kept as a conscious
// won't-fix: react-syntax-highlighter is already a dependency (four upstream
// components use it), but the dockyard palette maps exactly onto these five
// token types, CodeView's hand-built gutter/tab layout doesn't fit the
// library's renderer, and these regexes were verified free of catastrophic
// backtracking. Revisit only if the Code view ever needs real language
// coverage beyond a readable scaffold.

export type TokenType = "comment" | "string" | "keyword" | "number" | "plain";

export interface Token {
  text: string;
  type: TokenType;
}

/** Canonical language id used by the tokenizer. */
export type Language =
  | "ts"
  | "js"
  | "py"
  | "json"
  | "md"
  | "css"
  | "html"
  | "sh"
  | "yaml"
  | "toml"
  | "text";

// Extension → canonical language. Unknown extensions fall back to plain text.
const EXT_LANG: Record<string, Language> = {
  ts: "ts",
  tsx: "ts",
  mts: "ts",
  cts: "ts",
  js: "js",
  jsx: "js",
  mjs: "js",
  cjs: "js",
  py: "py",
  pyi: "py",
  json: "json",
  jsonc: "json",
  md: "md",
  markdown: "md",
  css: "css",
  scss: "css",
  less: "css",
  html: "html",
  htm: "html",
  sh: "sh",
  bash: "sh",
  zsh: "sh",
  yaml: "yaml",
  yml: "yaml",
  toml: "toml",
};

/** Coarse language id from a file path, by extension. */
export function languageFromPath(path: string): Language {
  const base = path.split("/").pop() ?? path;
  const dot = base.lastIndexOf(".");
  if (dot < 0) return "text";
  return EXT_LANG[base.slice(dot + 1).toLowerCase()] ?? "text";
}

interface LangSpec {
  /** Line-comment markers (to end of line). */
  line?: string[];
  /** Block-comment delimiter pairs. */
  block?: Array<[string, string]>;
  /** Single-char string quotes that stay on one line. */
  quotes?: string[];
  /** Multi-line string quotes (template literals, python triple-quotes). */
  multiline?: string[];
  keywords?: Set<string>;
}

const kw = (words: string[]) => new Set(words);

const JS_WORDS = [
  "const",
  "let",
  "var",
  "function",
  "return",
  "if",
  "else",
  "for",
  "while",
  "do",
  "switch",
  "case",
  "break",
  "continue",
  "new",
  "class",
  "extends",
  "super",
  "this",
  "import",
  "export",
  "from",
  "default",
  "async",
  "await",
  "yield",
  "try",
  "catch",
  "finally",
  "throw",
  "typeof",
  "instanceof",
  "in",
  "of",
  "void",
  "delete",
  "null",
  "undefined",
  "true",
  "false",
];

const TS_WORDS = [
  ...JS_WORDS,
  "interface",
  "type",
  "enum",
  "implements",
  "as",
  "readonly",
  "public",
  "private",
  "protected",
  "static",
  "get",
  "set",
  "namespace",
  "declare",
  "keyof",
  "infer",
  "satisfies",
];

const PY_WORDS = [
  "def",
  "class",
  "return",
  "if",
  "elif",
  "else",
  "for",
  "while",
  "import",
  "from",
  "as",
  "with",
  "try",
  "except",
  "finally",
  "raise",
  "pass",
  "break",
  "continue",
  "lambda",
  "yield",
  "async",
  "await",
  "global",
  "nonlocal",
  "in",
  "is",
  "not",
  "and",
  "or",
  "None",
  "True",
  "False",
  "self",
  "del",
  "assert",
];

const SH_WORDS = [
  "if",
  "then",
  "fi",
  "else",
  "elif",
  "for",
  "do",
  "done",
  "while",
  "case",
  "esac",
  "in",
  "function",
  "echo",
  "export",
  "return",
  "local",
  "set",
  "source",
];

const JS_KEYWORDS = kw(JS_WORDS);
const TS_KEYWORDS = kw(TS_WORDS);
const PY_KEYWORDS = kw(PY_WORDS);
const SH_KEYWORDS = kw(SH_WORDS);

const SPECS: Record<Language, LangSpec> = {
  ts: {
    line: ["//"],
    block: [["/*", "*/"]],
    quotes: ["'", '"'],
    multiline: ["`"],
    keywords: TS_KEYWORDS,
  },
  js: {
    line: ["//"],
    block: [["/*", "*/"]],
    quotes: ["'", '"'],
    multiline: ["`"],
    keywords: JS_KEYWORDS,
  },
  py: {
    line: ["#"],
    quotes: ["'", '"'],
    multiline: ['"""', "'''"],
    keywords: PY_KEYWORDS,
  },
  json: { quotes: ['"'], keywords: kw(["true", "false", "null"]) },
  css: { block: [["/*", "*/"]], quotes: ["'", '"'] },
  html: { block: [["<!--", "-->"]], quotes: ["'", '"'] },
  sh: { line: ["#"], quotes: ["'", '"'], keywords: SH_KEYWORDS },
  yaml: {
    line: ["#"],
    quotes: ["'", '"'],
    keywords: kw(["true", "false", "null"]),
  },
  toml: { line: ["#"], quotes: ["'", '"'], keywords: kw(["true", "false"]) },
  md: {},
  text: {},
};

// `g` (not `y`): the sticky flag needs an es6 target. With `g` plus the
// `m.index === i` guard below the behavior is identical — we only accept a match
// that begins exactly at the cursor — and it stays O(n) via `lastIndex`.
const IDENT = /[A-Za-z_$][A-Za-z0-9_$]*/g;
const NUMBER =
  /0[xX][0-9a-fA-F]+|(?:\d[\d_]*)(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?|\.\d[\d_]*/g;

/**
 * Tokenize `code` for `lang` into a flat list of typed tokens. Adjacent `plain`
 * runs are coalesced so the renderer emits the fewest possible spans.
 */
export function highlightTokens(code: string, lang: Language): Token[] {
  const spec = SPECS[lang] ?? SPECS.text;
  const out: Token[] = [];
  let plain = "";

  const flush = () => {
    if (plain) {
      out.push({ text: plain, type: "plain" });
      plain = "";
    }
  };
  const push = (text: string, type: TokenType) => {
    if (!text) return;
    flush();
    out.push({ text, type });
  };

  const n = code.length;
  let i = 0;
  while (i < n) {
    // Block comments.
    const block = spec.block?.find((b) => code.startsWith(b[0], i));
    if (block) {
      const close = code.indexOf(block[1], i + block[0].length);
      const end = close < 0 ? n : close + block[1].length;
      push(code.slice(i, end), "comment");
      i = end;
      continue;
    }

    // Line comments.
    const line = spec.line?.find((m) => code.startsWith(m, i));
    if (line) {
      const nl = code.indexOf("\n", i);
      const end = nl < 0 ? n : nl;
      push(code.slice(i, end), "comment");
      i = end;
      continue;
    }

    // Multi-line strings (templates, python triple-quotes).
    const multi = spec.multiline?.find((q) => code.startsWith(q, i));
    if (multi) {
      const end = consumeString(code, i + multi.length, multi, true);
      push(code.slice(i, end), "string");
      i = end;
      continue;
    }

    // Single-line strings.
    const quote = spec.quotes?.find((q) => code.startsWith(q, i));
    if (quote) {
      const end = consumeString(code, i + quote.length, quote, false);
      push(code.slice(i, end), "string");
      i = end;
      continue;
    }

    const ch = code[i];

    // Numbers.
    if (ch >= "0" && ch <= "9") {
      NUMBER.lastIndex = i;
      const m = NUMBER.exec(code);
      if (m && m.index === i) {
        push(m[0], "number");
        i += m[0].length;
        continue;
      }
    }

    // Identifiers / keywords. Keywords become their own token; any other word
    // merges into the surrounding plain run so contiguous prose stays one span.
    if (/[A-Za-z_$]/.test(ch)) {
      IDENT.lastIndex = i;
      const m = IDENT.exec(code);
      if (m && m.index === i) {
        if (spec.keywords?.has(m[0])) {
          push(m[0], "keyword");
        } else {
          plain += m[0];
        }
        i += m[0].length;
        continue;
      }
    }

    plain += ch;
    i += 1;
  }

  flush();
  return out;
}

/**
 * Return the index just past a string literal opened at `start`. Honors `\`
 * escapes; single-line strings also stop at a newline so an unterminated quote
 * can't swallow the rest of the file.
 */
function consumeString(
  code: string,
  start: number,
  close: string,
  multiline: boolean,
): number {
  let i = start;
  const n = code.length;
  while (i < n) {
    const ch = code[i];
    if (ch === "\\") {
      i += 2;
      continue;
    }
    if (!multiline && ch === "\n") return i;
    if (code.startsWith(close, i)) return i + close.length;
    i += 1;
  }
  return n;
}
