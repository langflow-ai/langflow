import { render, screen } from "@testing-library/react";
import type { FolderType } from "@/pages/MainPage/entities";
import { SelectOptions } from "../select-options";

let mockUseSidebarSeam = false;

jest.mock("react-i18next", () => ({
  initReactI18next: { type: "3rdParty", init: jest.fn() },
  useTranslation: () => ({
    t: (key: string, options?: Record<string, string>) => {
      if (key === "project.ownedBy")
        return `${options?.name} — ${options?.owner}`;
      if (key === "folder.optionsFor") return `Options for ${options?.name}`;
      return key;
    },
  }),
}));
jest.mock("@/contexts/permissionsContext", () => ({
  usePermissions: () => ({ can: () => true }),
}));
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock("@/customization/components/custom-resource-share-action", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/customization/components/custom-project-sidebar", () => {
  const actual = jest.requireActual(
    "@/customization/components/custom-project-sidebar",
  );
  return {
    ...actual,
    getCustomProjectSidebarProjectTitle: (
      project: FolderType,
      defaultTitle: string,
    ) =>
      mockUseSidebarSeam
        ? project.name
        : actual.getCustomProjectSidebarProjectTitle(project, defaultTitle),
  };
});

const sharedProject = {
  id: "p-1",
  name: "Knowledge Base",
  description: "",
  parent_id: "",
  flows: [],
  components: [],
  owner_username: "priya",
  is_owner: false,
} as FolderType;

const renderOptions = (project: FolderType) =>
  render(
    <SelectOptions
      item={project}
      handleDeleteFolder={jest.fn()}
      handleDownloadFolder={jest.fn()}
      handleSelectFolderToRename={jest.fn()}
      checkPathName={() => false}
    />,
  );

describe("SelectOptions accessible name", () => {
  beforeEach(() => {
    mockUseSidebarSeam = false;
  });

  it("should_keep_the_owner_suffix_in_the_options_name_when_the_seam_is_the_default", () => {
    renderOptions(sharedProject);

    expect(
      screen.getByRole("button", {
        name: "Options for Knowledge Base — priya",
      }),
    ).toBeInTheDocument();
  });

  it("should_use_the_seam_title_for_the_options_name_when_it_drops_the_suffix", () => {
    mockUseSidebarSeam = true;
    renderOptions(sharedProject);

    expect(
      screen.getByRole("button", { name: "Options for Knowledge Base" }),
    ).toBeInTheDocument();
  });

  it("should_name_an_owned_project_plainly_when_the_seam_is_the_default", () => {
    renderOptions({ ...sharedProject, is_owner: true });

    expect(
      screen.getByRole("button", { name: "Options for Knowledge Base" }),
    ).toBeInTheDocument();
  });
});
