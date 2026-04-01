import { act, renderHook } from "@testing-library/react";
import type { FolderType } from "../../pages/MainPage/entities";
import { useFolderStore } from "../foldersStore";

const mockFolder: FolderType = {
  id: "folder-1",
  name: "Test Folder",
  description: "Test folder description",
  parent_id: "parent-1",
  flows: [],
  components: [],
};

const mockFolder2: FolderType = {
  id: "folder-2",
  name: "Another Folder",
  description: "Another test folder",
  parent_id: "parent-2",
  flows: [],
  components: ["component-1", "component-2"],
};

describe("useFolderStore", () => {
  beforeEach(() => {
    act(() => {
      useFolderStore.setState({
        loadingById: false,
        myCollectionId: "",
        folderToEdit: null,
        folderDragging: false,
        folderIdDragging: "",
        starterProjectId: "",
        folders: [],
      });
    });
  });

  describe("initial state", () => {
    it("should have correct initial state", () => {
      const { result } = renderHook(() => useFolderStore());

      expect(result.current.loadingById).toBe(false);
      expect(result.current.myCollectionId).toBe("");
      expect(result.current.folderToEdit).toBeNull();
      expect(result.current.folderDragging).toBe(false);
      expect(result.current.folderIdDragging).toBe("");
      expect(result.current.starterProjectId).toBe("");
      expect(result.current.folders).toEqual([]);
    });
  });

  describe("setMyCollectionId", () => {
    it("should set collection ID", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setMyCollectionId("collection-123");
      });

      expect(result.current.myCollectionId).toBe("collection-123");
    });

    it("should update collection ID when called multiple times", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setMyCollectionId("collection-1");
      });
      expect(result.current.myCollectionId).toBe("collection-1");

      act(() => {
        result.current.setMyCollectionId("collection-2");
      });
      expect(result.current.myCollectionId).toBe("collection-2");
    });

    it("should handle empty string collection ID", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setMyCollectionId("");
      });

      expect(result.current.myCollectionId).toBe("");
    });
  });

  describe("setFolderToEdit", () => {
    it("should set folder to edit", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setFolderToEdit(mockFolder);
      });

      expect(result.current.folderToEdit).toEqual(mockFolder);
    });

    it("should clear folder to edit when set to null", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setFolderToEdit(mockFolder);
      });
      expect(result.current.folderToEdit).toEqual(mockFolder);

      act(() => {
        result.current.setFolderToEdit(null);
      });
      expect(result.current.folderToEdit).toBeNull();
    });

    it("should replace folder to edit when called with different folder", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setFolderToEdit(mockFolder);
      });
      expect(result.current.folderToEdit).toEqual(mockFolder);

      act(() => {
        result.current.setFolderToEdit(mockFolder2);
      });
      expect(result.current.folderToEdit).toEqual(mockFolder2);
    });
  });

  describe("setFolderDragging", () => {
    it("should set folder dragging state to true", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setFolderDragging(true);
      });

      expect(result.current.folderDragging).toBe(true);
    });

    it("should set folder dragging state to false", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setFolderDragging(false);
      });

      expect(result.current.folderDragging).toBe(false);
    });

    it("should toggle folder dragging state", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setFolderDragging(true);
      });
      expect(result.current.folderDragging).toBe(true);

      act(() => {
        result.current.setFolderDragging(false);
      });
      expect(result.current.folderDragging).toBe(false);
    });
  });

  describe("setFolderIdDragging", () => {
    it("should set folder ID dragging", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setFolderIdDragging("folder-123");
      });

      expect(result.current.folderIdDragging).toBe("folder-123");
    });

    it("should update folder ID dragging", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setFolderIdDragging("folder-1");
      });
      expect(result.current.folderIdDragging).toBe("folder-1");

      act(() => {
        result.current.setFolderIdDragging("folder-2");
      });
      expect(result.current.folderIdDragging).toBe("folder-2");
    });

    it("should handle empty string folder ID", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setFolderIdDragging("");
      });

      expect(result.current.folderIdDragging).toBe("");
    });
  });

  describe("setStarterProjectId", () => {
    it("should set starter project ID", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setStarterProjectId("project-123");
      });

      expect(result.current.starterProjectId).toBe("project-123");
    });

    it("should update starter project ID", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setStarterProjectId("project-1");
      });
      expect(result.current.starterProjectId).toBe("project-1");

      act(() => {
        result.current.setStarterProjectId("project-2");
      });
      expect(result.current.starterProjectId).toBe("project-2");
    });

    it("should handle empty string starter project ID", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setStarterProjectId("");
      });

      expect(result.current.starterProjectId).toBe("");
    });
  });

  describe("setFolders", () => {
    it("should set empty folders array", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setFolders([]);
      });

      expect(result.current.folders).toEqual([]);
    });

    it("should set single folder", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setFolders([mockFolder]);
      });

      expect(result.current.folders).toEqual([mockFolder]);
    });

    it("should set multiple folders", () => {
      const { result } = renderHook(() => useFolderStore());
      const folders = [mockFolder, mockFolder2];

      act(() => {
        result.current.setFolders(folders);
      });

      expect(result.current.folders).toEqual(folders);
    });

    it("should replace existing folders", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setFolders([mockFolder]);
      });
      expect(result.current.folders).toEqual([mockFolder]);

      act(() => {
        result.current.setFolders([mockFolder2]);
      });
      expect(result.current.folders).toEqual([mockFolder2]);
    });

    it("should handle folders with different structures", () => {
      const { result } = renderHook(() => useFolderStore());
      const folderWithFlows: FolderType = {
        ...mockFolder,
        flows: [{ id: "flow-1" } as any],
      };

      act(() => {
        result.current.setFolders([folderWithFlows]);
      });

      expect(result.current.folders[0].flows).toEqual([{ id: "flow-1" }]);
    });
  });

  describe("resetStore", () => {
    it("should reset all store state to initial values", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        result.current.setMyCollectionId("collection-123");
        result.current.setFolderToEdit(mockFolder);
        result.current.setFolderDragging(true);
        result.current.setFolderIdDragging("folder-123");
        result.current.setFolders([mockFolder, mockFolder2]);
      });

      expect(result.current.myCollectionId).toBe("collection-123");
      expect(result.current.folderToEdit).toEqual(mockFolder);
      expect(result.current.folderDragging).toBe(true);
      expect(result.current.folderIdDragging).toBe("folder-123");
      expect(result.current.folders).toEqual([mockFolder, mockFolder2]);

      act(() => {
        result.current.resetStore();
      });

      expect(result.current.myCollectionId).toBe("");
      expect(result.current.folderToEdit).toBeNull();
      expect(result.current.folderDragging).toBe(false);
      expect(result.current.folderIdDragging).toBe("");
      expect(result.current.folders).toEqual([]);
    });

    it("should not affect loadingById field", () => {
      const { result } = renderHook(() => useFolderStore());

      act(() => {
        useFolderStore.setState({ loadingById: true });
        result.current.resetStore();
      });

      expect(result.current.loadingById).toBe(true);
    });
  });

  describe("state isolation", () => {
    it("should maintain separate state across multiple hook instances", () => {
      const { result: result1 } = renderHook(() => useFolderStore());
      const { result: result2 } = renderHook(() => useFolderStore());

      act(() => {
        result1.current.setMyCollectionId("collection-1");
      });

      expect(result1.current.myCollectionId).toBe("collection-1");
      expect(result2.current.myCollectionId).toBe("collection-1");
    });
  });

  describe("edge cases", () => {
    it("should handle folder with undefined id", () => {
      const { result } = renderHook(() => useFolderStore());
      const folderWithoutId: FolderType = {
        name: "No ID Folder",
        description: "Folder without ID",
        parent_id: "parent-1",
        flows: [],
        components: [],
      };

      act(() => {
        result.current.setFolderToEdit(folderWithoutId);
      });

      expect(result.current.folderToEdit?.id).toBeUndefined();
      expect(result.current.folderToEdit?.name).toBe("No ID Folder");
    });

    it("should handle folder with null id", () => {
      const { result } = renderHook(() => useFolderStore());
      const folderWithNullId: FolderType = {
        id: null,
        name: "Null ID Folder",
        description: "Folder with null ID",
        parent_id: "parent-1",
        flows: [],
        components: [],
      };

      act(() => {
        result.current.setFolderToEdit(folderWithNullId);
      });

      expect(result.current.folderToEdit?.id).toBeNull();
      expect(result.current.folderToEdit?.name).toBe("Null ID Folder");
    });
  });
});
