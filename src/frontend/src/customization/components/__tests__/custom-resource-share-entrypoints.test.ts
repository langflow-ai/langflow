import { readFileSync } from "node:fs";
import { join } from "node:path";
import ts from "typescript";

const readFrontendSource = (path: string) =>
  readFileSync(join(process.cwd(), "src", path), "utf8");

const jsxProps = (path: string, tagName: string) => {
  const source = readFrontendSource(path);
  const sourceFile = ts.createSourceFile(
    path,
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const matches: Array<Record<string, string | undefined>> = [];

  const visit = (node: ts.Node) => {
    const opening = ts.isJsxSelfClosingElement(node)
      ? node
      : ts.isJsxElement(node)
        ? node.openingElement
        : undefined;
    if (opening?.tagName.getText(sourceFile) === tagName) {
      matches.push(
        Object.fromEntries(
          opening.attributes.properties
            .filter(ts.isJsxAttribute)
            .map((attribute) => [
              attribute.name.getText(sourceFile),
              attribute.initializer?.getText(sourceFile),
            ]),
        ),
      );
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return matches;
};

describe("non-flow share entry-point wiring", () => {
  it.each([
    [
      "pages/MainPage/pages/deploymentsPage/components/deployments-table.tsx",
      '"deployment"',
      "{deployment.id}",
      "{resolvedDisplayName}",
    ],
    [
      "components/core/folderSidebarComponent/components/sideBarFolderButtons/components/select-options.tsx",
      '"project"',
      "{item.id!}",
      "{displayName}",
    ],
    [
      "pages/MainPage/pages/knowledgePage/config/knowledgeBaseColumns.tsx",
      '"knowledge_base"',
      "{knowledgeBase.id}",
      "{knowledgeBase.name}",
    ],
    [
      "pages/FlowPage/components/MemoriesMainContent/components/MemoryDetailsHeader.tsx",
      '"knowledge_base"',
      "{memory.id}",
      "{memory.name}",
    ],
    [
      "modals/fileManagerModal/components/filesContextMenuComponent/index.tsx",
      '"file"',
      "{file.id}",
      "{file.name}",
    ],
  ])(
    "keeps the Enterprise seam mounted in %s",
    (path, resourceType, resourceId, resourceName) => {
      expect(jsxProps(path, "CustomResourceShareAction")).toContainEqual(
        expect.objectContaining({ resourceType, resourceId, resourceName }),
      );
    },
  );

  it("identifies Memory Bases separately from knowledge bases", () => {
    const [shareAction] = jsxProps(
      "pages/FlowPage/components/MemoriesMainContent/components/MemoryDetailsHeader.tsx",
      "CustomResourceShareAction",
    );

    expect(shareAction).toEqual(
      expect.objectContaining({ resourceSubtype: '"memory"' }),
    );
  });

  it("reserves exactly the one-action project row width", () => {
    // Share moved into the three-dot menu, so the row is back to a single
    // control and the width reserved for two would only cost the project name
    // characters it does not need to give up -- the names are already
    // truncated (LE-1905).
    const source = readFrontendSource(
      "components/core/folderSidebarComponent/components/sideBarFolderButtons/index.tsx",
    );

    expect(source).toContain('"flex-grow pr-8"');
    expect(source).not.toContain('"flex-grow pr-16"');
  });

  it("keeps resource subtype in the generic customization seam contract", () => {
    const source = readFrontendSource(
      "customization/components/custom-resource-share-action.tsx",
    );

    expect(source).toContain("resourceSubtype?:");
  });
});
