import { screen } from "@testing-library/react";
import type userEvent from "@testing-library/user-event";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= jest.fn(() => false);
  Element.prototype.releasePointerCapture ??= jest.fn();
  Element.prototype.scrollIntoView ??= jest.fn();
});

export async function selectProvider(
  user: ReturnType<typeof userEvent.setup>,
  displayName: string,
) {
  await user.click(screen.getByTestId("connection-provider"));
  await user.click(
    screen.getByRole("option", { name: displayName, exact: true }),
  );
}
