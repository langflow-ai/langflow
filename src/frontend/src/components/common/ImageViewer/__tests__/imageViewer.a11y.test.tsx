import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import ImageViewer from "../index";

jest.mock("openseadragon", () =>
  jest.fn(() => ({
    viewport: { zoomBy: jest.fn(), goHome: jest.fn() },
    setFullScreen: jest.fn(),
    destroy: jest.fn(),
  })),
);

jest.mock("file-saver", () => ({ saveAs: jest.fn() }));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} aria-hidden="true" />
  ),
}));

describe("ImageViewer toolbar accessibility", () => {
  it.each([
    ["Zoom in"],
    ["Zoom out"],
    ["Reset view"],
    ["Full screen"],
    ["Download image"],
  ])("should_name_the_%s_control", (name) => {
    render(<ImageViewer image="http://localhost/test.png" />);

    expect(screen.getByRole("button", { name })).toBeInTheDocument();
  });

  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <ImageViewer image="http://localhost/test.png" />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });
});
