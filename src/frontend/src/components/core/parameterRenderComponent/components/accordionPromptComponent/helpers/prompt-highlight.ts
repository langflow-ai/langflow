import { regexHighlight } from "@/constants/constants";

/** Apply variable highlighting to the prompt text. */
export const getHighlightedHTML = (text: string, isDoubleBrackets: boolean) => {
  if (isDoubleBrackets) {
    return text
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}/g, (match) => {
        return `<span class="chat-message-highlight">${match}</span>`;
      });
  }
  return text
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(regexHighlight, (match, codeFence, openRun, varName, closeRun) => {
      if (codeFence) return match;

      const lenOpen = openRun?.length ?? 0;
      const lenClose = closeRun?.length ?? 0;
      const isVariable = lenOpen === lenClose && lenOpen % 2 === 1;

      if (!isVariable) return match;

      const outerCount = Math.floor(lenOpen / 2);
      const outerLeft = "{".repeat(outerCount);
      const outerRight = "}".repeat(outerCount);

      return (
        `${outerLeft}` +
        `<span class="chat-message-highlight">{${varName}}</span>` +
        `${outerRight}`
      );
    });
};
