import { readFileSync } from "node:fs";
import { join } from "node:path";

const readFrontendSource = (path: string) =>
  readFileSync(join(process.cwd(), "src", path), "utf8");

describe("non-flow share entry-point wiring", () => {
  it.each([
    [
      "pages/MainPage/pages/deploymentsPage/components/deployments-table.tsx",
      'resourceType="deployment"',
    ],
    [
      "components/core/folderSidebarComponent/components/sideBarFolderButtons/components/select-options.tsx",
      'resourceType="project"',
    ],
    [
      "pages/MainPage/pages/knowledgePage/config/knowledgeBaseColumns.tsx",
      'resourceType="knowledge_base"',
    ],
    [
      "pages/FlowPage/components/MemoriesMainContent/components/MemoryDetailsHeader.tsx",
      'resourceType="knowledge_base"',
    ],
    [
      "modals/fileManagerModal/components/filesContextMenuComponent/index.tsx",
      'resourceType="file"',
    ],
  ])("keeps the Enterprise seam mounted in %s", (path, resourceType) => {
    const source = readFrontendSource(path);

    expect(source).toContain(
      'import CustomResourceShareAction from "@/customization/components/custom-resource-share-action";',
    );
    expect(source).toContain("<CustomResourceShareAction");
    expect(source).toContain(resourceType);
    expect(source).toContain("resourceId=");
    expect(source).toContain("resourceName=");
  });

  it("identifies Memory Bases separately from knowledge bases", () => {
    const source = readFrontendSource(
      "pages/FlowPage/components/MemoriesMainContent/components/MemoryDetailsHeader.tsx",
    );

    expect(source).toContain('resourceSubtype="memory"');
  });

  it("reserves the complete two-action project row width", () => {
    const source = readFrontendSource(
      "components/core/folderSidebarComponent/components/sideBarFolderButtons/index.tsx",
    );

    expect(source).toContain('"flex-grow pr-16"');
    expect(source).not.toContain('"flex-grow pr-8"');
  });

  it("keeps resource subtype in the generic customization seam contract", () => {
    const source = readFrontendSource(
      "customization/components/custom-resource-share-action.tsx",
    );

    expect(source).toContain("resourceSubtype?:");
  });

  it("mounts the inert variable seam without trusting row share capability", () => {
    const pageSource = readFrontendSource(
      "pages/SettingsPage/pages/GlobalVariablesPage/index.tsx",
    );
    const seamSource = readFrontendSource(
      "customization/components/custom-variable-share-action.tsx",
    );

    expect(pageSource).toContain(
      'import CustomVariableShareAction from "@/customization/components/custom-variable-share-action";',
    );
    expect(pageSource).toContain("<CustomVariableShareAction");
    expect(pageSource).not.toContain("canShareVariable");
    expect(seamSource).toContain("return null;");
  });
});
