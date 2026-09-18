import { render } from "@testing-library/react";
import CustomConnectionRefComponent from "../custom-connectionRefComponent";

const mockConnectionRefComponent = jest.fn(
  (_props: Record<string, unknown>) => <div data-testid="picker" />,
);

jest.mock(
  "@/components/core/parameterRenderComponent/components/connectionRefComponent",
  () => ({
    __esModule: true,
    default: (props: Record<string, unknown>) =>
      mockConnectionRefComponent(props),
  }),
);

describe("custom-connectionRefComponent seam", () => {
  beforeEach(() => jest.clearAllMocks());

  it("forwards the field's connection metadata to the OSS picker", () => {
    const handleOnNewValue = jest.fn();
    render(
      <CustomConnectionRefComponent
        id="connectionref_connection"
        value="google/work"
        editNode={false}
        disabled={false}
        handleOnNewValue={handleOnNewValue}
        provider="google"
        requiredScopes={["https://www.googleapis.com/auth/gmail.send"]}
        capabilities={["google.gmail.send"]}
        identityKind="user"
      />,
    );

    expect(mockConnectionRefComponent).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "connectionref_connection",
        value: "google/work",
        handleOnNewValue,
        provider: "google",
        requiredScopes: ["https://www.googleapis.com/auth/gmail.send"],
        capabilities: ["google.gmail.send"],
        identityKind: "user",
      }),
    );
  });

  it("defaults the list props so a field without them still renders", () => {
    render(
      <CustomConnectionRefComponent
        id="connectionref_connection"
        value=""
        editNode={false}
        disabled={false}
        handleOnNewValue={jest.fn()}
      />,
    );

    expect(mockConnectionRefComponent).toHaveBeenCalledWith(
      expect.objectContaining({ requiredScopes: [], capabilities: [] }),
    );
  });
});
