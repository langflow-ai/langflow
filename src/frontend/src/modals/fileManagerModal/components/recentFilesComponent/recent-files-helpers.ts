import type { FileType } from "@/types/file_management";
import { getRelativePathForServerPath } from "@/utils/file-relative-path-map";

export type FileTreeNode =
  | {
      kind: "folder";
      name: string;
      pathKey: string;
      children: FileTreeNode[];
    }
  | {
      kind: "file";
      name: string;
      pathKey: string;
      file: FileType;
    };

export function getFileHierarchyPath(file: FileType): string | undefined {
  return (
    getRelativePathForServerPath(file.path) ??
    file.file?.webkitRelativePath ??
    undefined
  );
}

type InternalFolderNode = {
  kind: "folder";
  name: string;
  children: Map<string, InternalNode>;
};

type InternalFileNode = { kind: "file"; name: string; file: FileType };

type InternalNode = InternalFolderNode | InternalFileNode;

export function buildFileTree(files: FileType[]) {
  const root = new Map<string, InternalNode>();

  for (const file of files) {
    if (file.disabled) continue;

    const hierarchyPath = getFileHierarchyPath(file);
    if (!hierarchyPath || !hierarchyPath.includes("/")) {
      const leafName = `${file.name}.${file.path.split(".").pop() ?? ""}`;
      root.set(`${file.path}`, {
        kind: "file",
        name: leafName,
        file,
      });
      continue;
    }

    const parts = hierarchyPath.split("/").filter(Boolean);
    let current = root;
    for (let index = 0; index < parts.length; index++) {
      const part = parts[index];
      const isLeaf = index === parts.length - 1;

      if (isLeaf) {
        const leafKey = current.has(part) ? `${part}__${file.path}` : part;
        if (!current.has(leafKey)) {
          current.set(leafKey, { kind: "file", name: part, file });
        }
      } else if (!current.has(part)) {
        current.set(part, { kind: "folder", name: part, children: new Map() });
      }

      const node = current.get(part);
      if (!isLeaf && node?.kind === "folder") {
        current = node.children;
      }
    }
  }

  const toNodes = (
    map: Map<string, InternalNode>,
    parentKey: string,
  ): FileTreeNode[] => {
    const entries = Array.from(map.entries());
    entries.sort(([aName, aNode], [bName, bNode]) => {
      if (aNode.kind !== bNode.kind) return aNode.kind === "folder" ? -1 : 1;
      return aName.localeCompare(bName);
    });

    return entries
      .map(([name, node]) => {
        const pathKey = parentKey ? `${parentKey}/${name}` : name;
        if (node.kind === "folder") {
          const children = toNodes(node.children, pathKey);
          if (children.length === 0) return null;
          return {
            kind: "folder",
            name,
            pathKey,
            children,
          } as FileTreeNode;
        }

        return {
          kind: "file",
          name: node.name ?? name,
          pathKey,
          file: node.file,
        } as FileTreeNode;
      })
      .filter(Boolean) as FileTreeNode[];
  };

  const tree = toNodes(root, "");

  const leafFilesInOrder: FileType[] = [];
  const collectLeaves = (nodes: FileTreeNode[]) => {
    for (const node of nodes) {
      if (node.kind === "file") leafFilesInOrder.push(node.file);
      else collectLeaves(node.children);
    }
  };
  collectLeaves(tree);

  const hasHierarchy = files.some((f) => {
    const hp = getFileHierarchyPath(f);
    return Boolean(hp && hp.includes("/"));
  });

  return { tree, leafFilesInOrder, hasHierarchy };
}

export function collectLeafPaths(node: FileTreeNode): string[] {
  if (node.kind === "file") return [node.file.path];
  return node.children.flatMap(collectLeafPaths);
}

export function collectFolderKeys(nodes: FileTreeNode[]): string[] {
  const folderKeys: string[] = [];
  const walk = (currentNodes: FileTreeNode[]) => {
    for (const node of currentNodes) {
      if (node.kind === "folder") {
        folderKeys.push(node.pathKey);
        walk(node.children);
      }
    }
  };

  walk(nodes);
  return folderKeys;
}
