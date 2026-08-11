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
});
