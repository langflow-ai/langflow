import { render, screen } from "@testing-library/react";
import CustomProjectHome from "./custom-project-home";

describe("CustomProjectHome", () => {
  it("leaves the OSS project home unchanged", () => {
    render(
      <CustomProjectHome
        description=""
        flowType="flows"
        flows={[]}
        folderDisplayName="My Collection"
        folderName="My Collection"
        isLoading={false}
        onNewFlow={jest.fn()}
        onSearch={jest.fn()}
        setFlowType={jest.fn()}
      >
        <div>Existing project home</div>
      </CustomProjectHome>,
    );

    expect(screen.getByText("Existing project home")).toBeInTheDocument();
  });
});
