import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { AddFolderButton } from "../add-folder-button";
import { UploadFolderButton } from "../upload-folder-button";

jest.mock("react-i18next", () => ({
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

describe("folder action buttons", () => {
  it("names the create project button", () => {
    render(
      <AddFolderButton onClick={jest.fn()} disabled={false} loading={false} />,
    );

    expect(
      screen.getByRole("button", { name: "folder.createNewProject" }),
    ).toBeInTheDocument();
  });

  it("names the upload flow button", () => {
    render(<UploadFolderButton onClick={jest.fn()} disabled={false} />);

    expect(
      screen.getByRole("button", { name: "folder.uploadFlow" }),
    ).toBeInTheDocument();
  });
});
