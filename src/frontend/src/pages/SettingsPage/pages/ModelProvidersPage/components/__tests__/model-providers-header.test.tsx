import { render, screen } from "@testing-library/react";
import ModelProvidersHeader from "../model-providers-header";

// Mock the icon component
jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({
    name,
    className,
  }: {
    name: string;
    className?: string;
  }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

describe("ModelProvidersHeader", () => {
  it("renders without crashing", () => {
    render(<ModelProvidersHeader />);
    expect(screen.getByText("Model Providers")).toBeInTheDocument();
  });

  it("renders the title", () => {
    render(<ModelProvidersHeader />);
    expect(screen.getByText("Model Providers")).toBeInTheDocument();
  });

  it("renders the description", () => {
    render(<ModelProvidersHeader />);
    expect(
      screen.getByText(
        "Configure access to Language, Embedding, and Multimodal models.",
      ),
    ).toBeInTheDocument();
  });

  it("renders the BrainCircuit icon", () => {
    render(<ModelProvidersHeader />);
    expect(screen.getByTestId("icon-BrainCircuit")).toBeInTheDocument();
  });

  it("has correct structure with title and description", () => {
    const { container } = render(<ModelProvidersHeader />);
    const mainDiv = container.firstChild as HTMLElement;

    expect(mainDiv).toHaveClass("flex");
    expect(mainDiv).toHaveClass("w-full");
    expect(mainDiv).toHaveClass("items-center");
    expect(mainDiv).toHaveClass("justify-between");
  });

  it("renders icon with correct classes", () => {
    render(<ModelProvidersHeader />);
    const icon = screen.getByTestId("icon-BrainCircuit");

    expect(icon).toHaveClass("ml-2");
    expect(icon).toHaveClass("h-5");
    expect(icon).toHaveClass("w-5");
    expect(icon).toHaveClass("text-primary");
  });
});
