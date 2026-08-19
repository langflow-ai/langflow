import { render, screen } from "@testing-library/react";
import CustomModelProvidersEmptyState from "../custom-model-providers-empty-state";

describe("CustomModelProvidersEmptyState OSS seam", () => {
  it.each([
    ["providers", true],
    ["providers", false],
    ["models", true],
    ["models", false],
  ] as const)("passes %s children through when show is %s", (kind, show) => {
    render(
      <CustomModelProvidersEmptyState kind={kind} show={show}>
        <p>OSS model provider content</p>
      </CustomModelProvidersEmptyState>,
    );

    expect(screen.getByText("OSS model provider content")).toBeInTheDocument();
  });
});
