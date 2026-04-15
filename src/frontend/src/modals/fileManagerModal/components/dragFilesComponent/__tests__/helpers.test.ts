import type { DragEvent } from "react";
import {
  dedupeFolderRootIfNeeded,
  filterFilesByTypes,
  filterHiddenAndIgnoredFolderFiles,
  getDroppedFilesFromDragEvent,
  getRootFolderFromRelativePath,
  type WebkitDirectoryEntry,
  type WebkitDirectoryReader,
  type WebkitEntry,
  type WebkitFileEntry,
} from "../helpers";

type DragEventLike = {
  dataTransfer: {
    items?: Array<{
      getAsFile?: () => File | null;
      webkitGetAsEntry?: () => WebkitEntry | null;
    }>;
    files?: File[];
  };
};

function asDragEvent(event: DragEventLike): DragEvent {
  return event as unknown as DragEvent;
}

function withRelativePath(file: File, webkitRelativePath: string): File {
  Object.defineProperty(file, "webkitRelativePath", {
    value: webkitRelativePath,
    enumerable: true,
  });
  return file;
}

describe("dragFilesComponent/helpers", () => {
  describe("getRootFolderFromRelativePath", () => {
    it("returns undefined for empty/flat paths", () => {
      expect(getRootFolderFromRelativePath(undefined)).toBeUndefined();
      expect(getRootFolderFromRelativePath("")).toBeUndefined();
      expect(getRootFolderFromRelativePath("file.txt")).toBeUndefined();
      expect(getRootFolderFromRelativePath("/file.txt")).toBeUndefined();
    });

    it("returns first segment for nested paths", () => {
      expect(getRootFolderFromRelativePath("folder/file.txt")).toBe("folder");
      expect(getRootFolderFromRelativePath("folder/sub/file.txt")).toBe(
        "folder",
      );
      expect(getRootFolderFromRelativePath("/folder/sub/file.txt")).toBe(
        "folder",
      );
    });
  });

  describe("filterFilesByTypes", () => {
    it("filters by extension (case-insensitive)", () => {
      const a = new File(["a"], "a.PDF", { type: "application/pdf" });
      const b = new File(["b"], "b.txt", { type: "text/plain" });
      const c = new File(["c"], "c", { type: "application/octet-stream" });

      expect(filterFilesByTypes([a, b, c], ["pdf"]).map((f) => f.name)).toEqual(
        ["a.PDF"],
      );
      expect(
        filterFilesByTypes([a, b], ["PDF", "TxT"]).map((f) => f.name),
      ).toEqual(["a.PDF", "b.txt"]);
    });
  });

  describe("filterHiddenAndIgnoredFolderFiles", () => {
    it("filters hidden/ignored paths and returns skipped count", () => {
      const ok = withRelativePath(
        new File(["ok"], "ok.txt", { type: "text/plain" }),
        "my-folder/ok.txt",
      );
      const git = withRelativePath(
        new File(["git"], "config", { type: "text/plain" }),
        "my-folder/.git/config",
      );
      const nodeModules = withRelativePath(
        new File(["nm"], "index.js", { type: "text/javascript" }),
        "my-folder/node_modules/pkg/index.js",
      );
      const dsStore = withRelativePath(
        new File(["ds"], ".DS_Store", { type: "text/plain" }),
        "my-folder/.DS_Store",
      );

      const { filtered, skipped } = filterHiddenAndIgnoredFolderFiles([
        ok,
        git,
        nodeModules,
        dsStore,
      ]);

      expect(filtered.map((f) => f.name)).toEqual(["ok.txt"]);
      expect(skipped).toBe(3);
    });
  });

  describe("dedupeFolderRootIfNeeded", () => {
    it("returns as-is when there is no root folder", () => {
      const flat = new File(["x"], "x.txt", { type: "text/plain" });
      const res = dedupeFolderRootIfNeeded({
        files: [flat],
        existingRoots: new Set(["folder"]),
        renameOnCollision: true,
      });
      expect(res.rootName).toBeUndefined();
      expect(res.renamedRootName).toBeUndefined();
      expect(res.files[0]).toBe(flat);
    });

    it("merges into existing root when renameOnCollision is false", () => {
      const f1 = withRelativePath(
        new File(["a"], "a.txt", { type: "text/plain" }),
        "folder/a.txt",
      );
      const res = dedupeFolderRootIfNeeded({
        files: [f1],
        existingRoots: new Set(["folder"]),
        renameOnCollision: false,
      });

      expect(res.rootName).toBe("folder");
      expect(res.renamedRootName).toBeUndefined();
      expect(res.files[0].webkitRelativePath).toBe("folder/a.txt");
    });

    it("renames root when renameOnCollision is true", () => {
      const f1 = withRelativePath(
        new File(["a"], "a.txt", { type: "text/plain" }),
        "folder/a.txt",
      );
      const f2 = withRelativePath(
        new File(["b"], "b.txt", { type: "text/plain" }),
        "folder/sub/b.txt",
      );

      const res = dedupeFolderRootIfNeeded({
        files: [f1, f2],
        existingRoots: new Set(["folder", "folder (2)"]),
        renameOnCollision: true,
      });

      expect(res.rootName).toBe("folder");
      expect(res.renamedRootName).toBe("folder (3)");
      expect(res.files.map((f) => f.webkitRelativePath)).toEqual([
        "folder (3)/a.txt",
        "folder (3)/sub/b.txt",
      ]);
    });
  });

  describe("getDroppedFilesFromDragEvent", () => {
    it("falls back to dataTransfer.files when items are missing", async () => {
      const f = new File(["x"], "x.txt", { type: "text/plain" });
      const e: DragEventLike = {
        dataTransfer: {
          items: undefined,
          files: [f],
        },
      };

      await expect(
        getDroppedFilesFromDragEvent(asDragEvent(e)),
      ).resolves.toEqual({
        files: [f],
        hasDirectories: false,
      });
    });

    it("uses item.getAsFile when entry traversal is unavailable", async () => {
      const f = new File(["x"], "x.txt", { type: "text/plain" });
      const e: DragEventLike = {
        dataTransfer: {
          items: [
            {
              getAsFile: () => f,
            },
          ],
          files: [],
        },
      };

      const res = await getDroppedFilesFromDragEvent(asDragEvent(e));
      expect(res.hasDirectories).toBe(false);
      expect(res.files).toEqual([f]);
    });

    it("traverses directory entries and sets webkitRelativePath", async () => {
      const childFile = new File(["child"], "child.txt", {
        type: "text/plain",
      });

      const childFileEntry: WebkitFileEntry = {
        isFile: true,
        isDirectory: false,
        name: "child.txt",
        file: (resolve: (f: File) => void) => resolve(childFile),
      };

      const readEntries = jest
        .fn<void, Parameters<WebkitDirectoryReader["readEntries"]>>()
        .mockImplementationOnce((resolve) => resolve([childFileEntry]))
        .mockImplementationOnce((resolve) => resolve([]));

      const reader: WebkitDirectoryReader = {
        readEntries,
      };

      const dirEntry: WebkitDirectoryEntry = {
        isFile: false,
        isDirectory: true,
        name: "dir",
        createReader: () => reader,
      };

      const e: DragEventLike = {
        dataTransfer: {
          items: [
            {
              webkitGetAsEntry: () => dirEntry,
            },
          ],
          files: [],
        },
      };

      const res = await getDroppedFilesFromDragEvent(asDragEvent(e));
      expect(res.hasDirectories).toBe(true);
      expect(res.files).toHaveLength(1);
      expect(res.files[0].name).toBe("child.txt");
      expect(res.files[0].webkitRelativePath).toBe("dir/child.txt");

      expect(readEntries).toHaveBeenCalled();
    });
  });
});
