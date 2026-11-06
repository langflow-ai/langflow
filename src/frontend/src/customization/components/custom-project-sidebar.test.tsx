import { render, screen } from "@testing-library/react";
import type { FolderType } from "@/pages/MainPage/entities";
import {
  CustomProjectSidebarProjectLabel,
  getCustomProjectSidebarProjectTitle,
  useCustomProjectSidebar,
} from "./custom-project-sidebar";

const project: FolderType = {
  id: "project",
  name: "Project",
  description: "",
  parent_id: "",
  flows: [],
  components: [],
  owner_username: "owner",
  is_owner: false,
};

function Harness() {
  const customization = useCustomProjectSidebar([project]);
  return (
    <>
      <span data-testid="count">{customization.projects.length}</span>
      <span data-testid="tools">{customization.tools}</span>
      <span data-testid="footer">{customization.footer}</span>
      <CustomProjectSidebarProjectLabel
        project={project}
        defaultLabel="Existing project label"
      />
    </>
  );
}

describe("custom project sidebar OSS seam", () => {
  it("leaves the project sidebar unchanged", () => {
    render(<Harness />);

    expect(screen.getByTestId("count")).toHaveTextContent("1");
    expect(screen.getByTestId("tools")).toBeEmptyDOMElement();
    expect(screen.getByTestId("footer")).toBeEmptyDOMElement();
    expect(screen.getByText("Existing project label")).toBeInTheDocument();
    expect(
      getCustomProjectSidebarProjectTitle(project, "Existing project label"),
    ).toBe("Existing project label");
  });
});
