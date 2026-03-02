import type { DragEvent } from "react";

// Minimal typings for WebKit drag-and-drop folder traversal.
// These are non-standard but widely supported (Chrome/Safari).
export type WebkitEntry = WebkitFileEntry | WebkitDirectoryEntry;

export interface WebkitBaseEntry {
  readonly isFile: boolean;
  readonly isDirectory: boolean;
  readonly name: string;
}

export interface WebkitFileEntry extends WebkitBaseEntry {
  readonly isFile: true;
  readonly isDirectory: false;
  file(
    successCallback: (file: File) => void,
    errorCallback?: (error: DOMException) => void,
  ): void;
}

export interface WebkitDirectoryReader {
  readEntries(
    successCallback: (entries: WebkitEntry[]) => void,
    errorCallback?: (error: DOMException) => void,
  ): void;
}

export interface WebkitDirectoryEntry extends WebkitBaseEntry {
  readonly isFile: false;
  readonly isDirectory: true;
  createReader(): WebkitDirectoryReader;
}

export type DataTransferItemWithWebkitEntry = DataTransferItem & {
  webkitGetAsEntry?: () => WebkitEntry | null;
};

function isWebkitFileEntry(entry: WebkitEntry): entry is WebkitFileEntry {
  return entry.isFile;
}

function isWebkitDirectoryEntry(
  entry: WebkitEntry,
): entry is WebkitDirectoryEntry {
  return entry.isDirectory;
}

export async function getDroppedFilesFromDragEvent(
  e: DragEvent,
): Promise<{ files: File[]; hasDirectories: boolean }> {
  const items = e.dataTransfer?.items;
  if (!items || items.length === 0) {
    return {
      files: Array.from(e.dataTransfer?.files ?? []),
      hasDirectories: false,
    };
  }

  const collected: Array<{ file: File; relativePath?: string }> = [];
  let hasDirectories = false;

  const wrapWithRelativePath = (file: File, relativePath?: string) => {
    if (!relativePath) return file;
    const wrapped = new File([file], file.name, {
      type: file.type,
      lastModified: file.lastModified,
    });
    try {
      Object.defineProperty(wrapped, "webkitRelativePath", {
        value: relativePath,
        enumerable: true,
      });
    } catch {}
    return wrapped;
  };

  const readAllDirectoryEntries = async (
    directoryEntry: WebkitDirectoryEntry,
  ) => {
    const reader = directoryEntry.createReader();
    const allEntries: WebkitEntry[] = [];
    while (true) {
      const batch = await new Promise<WebkitEntry[]>((resolve, reject) => {
        reader.readEntries(resolve, reject);
      });
      if (!batch || batch.length === 0) break;
      allEntries.push(...batch);
    }
    return allEntries;
  };

  const traverseEntry = async (entry: WebkitEntry, parentPath: string) => {
    if (!entry) return;

    if (isWebkitFileEntry(entry)) {
      const file: File = await new Promise((resolve, reject) => {
        entry.file(resolve, reject);
      });
      collected.push({ file, relativePath: `${parentPath}${entry.name}` });
      return;
    }

    if (isWebkitDirectoryEntry(entry)) {
      hasDirectories = true;
      const children = await readAllDirectoryEntries(entry);
      await Promise.all(
        children.map((child) =>
          traverseEntry(child, `${parentPath}${entry.name}/`),
        ),
      );
    }
  };

  // Prefer entry traversal (supports folders) when available.
  const traversalPromises: Promise<void>[] = [];
  for (const item of Array.from(items)) {
    const entryGetter = (item as DataTransferItemWithWebkitEntry)
      .webkitGetAsEntry;
    if (typeof entryGetter === "function") {
      const entry = entryGetter.call(item);
      if (entry) {
        traversalPromises.push(traverseEntry(entry, ""));
        continue;
      }
    }

    // Fallback: file-only
    const file = item.getAsFile?.();
    if (file) collected.push({ file });
  }

  if (traversalPromises.length > 0) {
    await Promise.all(traversalPromises);
  }

  const files = collected.map(({ file, relativePath }) =>
    wrapWithRelativePath(file, relativePath),
  );

  // If traversal yielded nothing (browser doesn't support it), fall back.
  if (files.length === 0) {
    return {
      files: Array.from(e.dataTransfer?.files ?? []),
      hasDirectories: false,
    };
  }

  return { files, hasDirectories };
}

export function filterHiddenAndIgnoredFolderFiles(files: File[]) {
  const ignoredDirectoryNames = new Set(["node_modules", "__pycache__"]);
  const ignoredPathFragments = [
    ".mypy_cache",
    ".DS_Store",
    ".git",
    ".vscode",
    ".idea",
    ".pytest_cache",
  ];

  let skipped = 0;
  const filtered = files.filter((file) => {
    const pathForFiltering = file.webkitRelativePath || file.name;
    const parts = pathForFiltering.split("/").filter(Boolean);

    if (ignoredPathFragments.some((frag) => pathForFiltering.includes(frag))) {
      skipped++;
      return false;
    }

    if (
      parts.some(
        (part) =>
          (part.startsWith(".") && part.length > 1) ||
          ignoredDirectoryNames.has(part),
      )
    ) {
      skipped++;
      return false;
    }

    return true;
  });

  return { filtered, skipped };
}

export function filterFilesByTypes(files: File[], types: string[]) {
  const allowed = new Set(types.map((t) => t.toLowerCase()));
  return files.filter((file) => {
    const fileExtension = file.name.split(".").pop()?.toLowerCase();
    return Boolean(fileExtension && allowed.has(fileExtension));
  });
}

export function getRootFolderFromRelativePath(
  relativePath?: string,
): string | undefined {
  if (!relativePath) return undefined;
  const parts = relativePath.split("/").filter(Boolean);
  return parts.length > 1 ? parts[0] : undefined;
}

function withWebkitRelativePath(file: File, webkitRelativePath: string): File {
  const wrapped = new File([file], file.name, {
    type: file.type,
    lastModified: file.lastModified,
  });
  try {
    Object.defineProperty(wrapped, "webkitRelativePath", {
      value: webkitRelativePath,
      enumerable: true,
    });
  } catch {}
  return wrapped;
}

export function dedupeFolderRootIfNeeded(args: {
  files: File[];
  existingRoots: Set<string>;
  /**
   * When true, a conflicting root folder name is renamed to "name (2)".
   * When false, uploads are merged into the existing root folder.
   */
  renameOnCollision?: boolean;
}): { files: File[]; rootName?: string; renamedRootName?: string } {
  const { files, existingRoots } = args;
  const firstRelativePath = files.find(
    (f) => f.webkitRelativePath,
  )?.webkitRelativePath;
  const rootName = getRootFolderFromRelativePath(firstRelativePath);
  if (!rootName)
    return { files, rootName: undefined, renamedRootName: undefined };

  if (!existingRoots.has(rootName)) {
    return { files, rootName, renamedRootName: undefined };
  }

  // Merge behavior: do not create a duplicate root folder.
  if (!args.renameOnCollision) {
    return { files, rootName, renamedRootName: undefined };
  }

  let counter = 2;
  let candidate = `${rootName} (${counter})`;
  while (existingRoots.has(candidate)) {
    counter++;
    candidate = `${rootName} (${counter})`;
  }

  const updated = files.map((file) => {
    const rel = file.webkitRelativePath;
    if (!rel || !rel.includes("/")) return file;
    const parts = rel.split("/");
    parts[0] = candidate;
    return withWebkitRelativePath(file, parts.join("/"));
  });

  return { files: updated, rootName, renamedRootName: candidate };
}
