import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import { axe } from "@/utils/a11y-test";
import FilePreviewDisplay from "../file-preview-display";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: () => null,
}));

// The real tooltip, which the global setup replaces with its children.
jest.mock("@/components/common/shadTooltipComponent", () =>
  jest.requireActual("@/components/common/shadTooltipComponent"),
);

jest.mock("@/customization/utils/urls", () => ({
  getBaseUrl: () => "http://localhost:3000/api/v1/",
}));

const renderPreview = (ui: React.ReactElement) =>
  render(<TooltipProvider delayDuration={0}>{ui}</TooltipProvider>);

const attached = (name: string) => new File(["content"], name);

describe("FilePreviewDisplay", () => {
  it("names each attachment in the chat input", () => {
    renderPreview(
      <>
        <FilePreviewDisplay file={attached("notes.txt")} variant="compact" />
        <FilePreviewDisplay
          file={attached("customer_list_export.csv")}
          variant="compact"
        />
      </>,
    );

    expect(screen.getByText("notes.txt")).toBeInTheDocument();
    expect(screen.getByText("custom...csv")).toBeInTheDocument();
  });

  it("names the attachment each delete button removes", () => {
    renderPreview(
      <>
        <FilePreviewDisplay
          file={attached("notes.txt")}
          variant="compact"
          showDelete
          onDelete={jest.fn()}
        />
        <FilePreviewDisplay
          file={attached("customer_list_export.csv")}
          variant="compact"
          showDelete
          onDelete={jest.fn()}
        />
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Delete notes.txt" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete customer_list_export.csv" }),
    ).toBeInTheDocument();
  });

  it("shows the full name when hovering an attachment in the chat input", async () => {
    const user = userEvent.setup();
    renderPreview(
      <FilePreviewDisplay
        file={attached("customer_list_export.csv")}
        variant="compact"
        showDelete
        onDelete={jest.fn()}
      />,
    );

    await user.hover(screen.getByText("custom...csv"));

    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "customer_list_export.csv",
    );
    expect(
      await axe(document.body, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });

  it("shows the uploaded name of a sent file, in full on hover", async () => {
    const user = userEvent.setup();
    renderPreview(
      <FilePreviewDisplay
        file="flow-1/2026-11-09_10-02-11_meeting-notes-final-v2.txt"
        variant="expanded"
      />,
    );

    const label = screen.getByText("meeting-no...txt");
    await user.hover(label);

    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "meeting-notes-final-v2.txt",
    );
  });
});
