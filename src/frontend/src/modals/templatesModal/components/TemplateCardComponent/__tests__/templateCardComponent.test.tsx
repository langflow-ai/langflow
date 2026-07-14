import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import type { TemplateExample } from "@/types/templates/types";

jest.mock("@/components/common/genericIconComponent", () => {
  const Icon = () => <span data-testid="template-icon" />;
  return {
    __esModule: true,
    default: Icon,
    ForwardedIconComponent: Icon,
  };
});

jest.mock("@/modals/deleteConfirmationModal", () => ({
  __esModule: true,
  default: ({
    children,
    onConfirm,
  }: {
    children: ReactElement;
    onConfirm: (event: React.MouseEvent<HTMLButtonElement>) => void;
  }) => (
    <span
      role="button"
      tabIndex={0}
      data-testid="confirm-delete-template"
      onClick={(event) =>
        onConfirm(event as unknown as React.MouseEvent<HTMLButtonElement>)
      }
      onKeyDown={() => {}}
    >
      {children}
    </span>
  ),
}));

import TemplateCardComponent from "../index";

const teamTemplate = {
  id: "template-1",
  name: "Team template",
  description: "Description",
  data: null,
  source: "team",
} as TemplateExample;

describe("TemplateCardComponent", () => {
  it("allows an authorized team template to be deleted without opening it", async () => {
    const user = userEvent.setup();
    const onClick = jest.fn();
    const onDelete = jest.fn();
    render(
      <TemplateCardComponent
        example={teamTemplate}
        onClick={onClick}
        onDelete={onDelete}
      />,
    );

    await user.click(screen.getByTestId("confirm-delete-template"));

    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("does not show delete for system templates", () => {
    render(
      <TemplateCardComponent
        example={{ ...teamTemplate, source: "system" }}
        onClick={jest.fn()}
      />,
    );

    expect(screen.queryByLabelText("Delete template")).not.toBeInTheDocument();
  });
});
