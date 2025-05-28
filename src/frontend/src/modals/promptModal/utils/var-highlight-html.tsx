import { IVarHighlightType } from "../../../types/components";

export default function varHighlightHTML({ name }: IVarHighlightType): string {
  const html = `<span class="chat-message-highlight">{${name}}</span>`;
  return html;
}
