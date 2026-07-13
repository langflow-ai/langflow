import siteConfig from "@generated/docusaurus.config";

export default function prismIncludeLanguages(Prism) {
  const { additionalLanguages } = siteConfig.themeConfig.prism;

  const PrismBefore = globalThis.Prism;
  globalThis.Prism = Prism;

  additionalLanguages.forEach((lang) => {
    if (lang === "php") {
      require("prismjs/components/prism-markup-templating.js");
    }
    require(`prismjs/components/prism-${lang}`);
  });

  delete globalThis.Prism;
  if (typeof PrismBefore !== "undefined") {
    globalThis.Prism = PrismBefore;
  }

  // Give Python `import` and `from` their own token type so they can be
  // styled separately from other keywords (def, class, if, etc.).
  if (Prism.languages.python) {
    Prism.languages.insertBefore("python", "keyword", {
      "keyword-import": { pattern: /\b(?:import|from)\b/ },
    });
  }

  if (Prism.languages.batch) {
    Prism.languages.cmd = Prism.languages.batch;
  }

  // Add modern package managers, runtimes, and common CLI tools to bash/shell highlighting.
  if (Prism.languages.bash) {
    Prism.languages.insertBefore("bash", "function", {
      "bash-plain": {
        pattern: /(^|[\s;|&])(?:install|remove|update|build|init|exec|push|pull|clone|apply|deploy)(?=$|[\s;|&])/,
        lookbehind: true,
      },
      "function-modern": {
        pattern: /(^|[\s;|&]|[<>]\()(?:uv|uvx|pip|pip3|python|python3|node|npm|npx|pnpm|bun|bunx|deno|cargo|go|rustup|brew|docker|kubectl|helm|terraform|poetry|pdm|rye|make|curl|wget|git|cp|mv|rm|mkdir|touch|cat|grep|sed|awk|jq|xargs)(?=$|[)\s;|&])/,
        lookbehind: true,
        alias: "keyword",
      },
      "flag": {
        pattern: /(^|\s)--?[a-zA-Z][\w-]*/,
        lookbehind: true,
        alias: "keyword",
      },
    });
  }
}
