import type { IVarHighlightType } from "../../../types/components";

export default function varHighlightHTML({
  name,
  addCurlyBraces,
}: IVarHighlightType): string {
  if (addCurlyBraces) {
    return `<span class="font-semibold chat-message-highlight">{${name}}</span>`;
  }
  return `<span class="font-semibold chat-message-highlight">${name}</span>`;
}
