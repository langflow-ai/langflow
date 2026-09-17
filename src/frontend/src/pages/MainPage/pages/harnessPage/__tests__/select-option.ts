import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Use the real shared Select; JSDOM lacks these browser APIs.
export async function openSelect(trigger: HTMLElement) {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
  const user = userEvent.setup();
  await user.click(trigger);
  return user;
}

export async function selectOption(
  trigger: HTMLElement,
  name: string | RegExp,
) {
  const user = await openSelect(trigger);
  await user.click(await screen.findByRole("option", { name }));
}
