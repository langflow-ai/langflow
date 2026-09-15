import { render, screen } from "@testing-library/react";
import { AccessHintBadge } from "../AccessHintBadge";

describe("AccessHintBadge", () => {
  it("should label a read-only tool", () => {
    render(<AccessHintBadge hint="read_only" />);
    expect(screen.getByTestId("access-hint-read_only")).toBeInTheDocument();
  });

  it("should label a writing tool", () => {
    render(<AccessHintBadge hint="write" />);
    expect(screen.getByTestId("access-hint-write")).toBeInTheDocument();
  });

  it("should label a destructive tool", () => {
    render(<AccessHintBadge hint="destructive" />);
    expect(screen.getByTestId("access-hint-destructive")).toBeInTheDocument();
  });

  it("should render nothing when the server declared no hint", () => {
    const { container } = render(<AccessHintBadge hint={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("should render nothing when the field is absent", () => {
    const { container } = render(<AccessHintBadge />);
    expect(container).toBeEmptyDOMElement();
  });

  it("should render nothing for a value it does not recognize", () => {
    const { container } = render(<AccessHintBadge hint="idempotent" />);
    expect(container).toBeEmptyDOMElement();
  });
});
