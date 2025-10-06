import { act, renderHook } from "@testing-library/react";
import { EventDeliveryType } from "@/constants/enums";
import type { Pagination, Tag } from "@/types/utils/types";
import { useUtilityStore } from "../utilityStore";
import { mockDataFactory, resetStoreState } from "./testUtils";

const mockTag: Tag = mockDataFactory.createTag({
  id: "tag-1",
  name: "Test Tag",
  description: "A test tag",
  color: "#FF0000",
});

const mockTag2: Tag = mockDataFactory.createTag({
  id: "tag-2",
  name: "Another Tag",
  description: "Another test tag",
  color: "#00FF00",
});

const mockPagination: Pagination = mockDataFactory.createPagination({
  page: 2,
  size: 20,
});

describe("useUtilityStore", () => {
  beforeEach(() => {
    resetStoreState(useUtilityStore, {
      clientId: "",
      chatValueStore: "",
      selectedItems: [],
      healthCheckTimeout: null,
      playgroundScrollBehaves: "instant",
      maxFileSizeUpload: 100 * 1024 * 1024, // 100MB
      serializationMaxItemsLength: 100,
      flowsPagination: { page: 1, size: 10 },
      tags: [],
      featureFlags: {},
      webhookPollingInterval: 5000,
      currentSessionId: "",
      eventDelivery: EventDeliveryType.POLLING,
      webhookAuthEnable: true,
      defaultFolderName: "Starter Project",
      hideGettingStartedProgress: false,
    });
  });

  describe("initial state", () => {
    it("should have correct initial state", () => {
      const { result } = renderHook(() => useUtilityStore());

      expect(result.current.clientId).toBe("");
      expect(result.current.chatValueStore).toBe("");
      expect(result.current.selectedItems).toEqual([]);
      expect(result.current.healthCheckTimeout).toBeNull();
      expect(result.current.playgroundScrollBehaves).toBe("instant");
      expect(result.current.maxFileSizeUpload).toBe(100 * 1024 * 1024);
      expect(result.current.serializationMaxItemsLength).toBe(100);
      expect(result.current.flowsPagination).toEqual({ page: 1, size: 10 });
      expect(result.current.tags).toEqual([]);
      expect(result.current.featureFlags).toEqual({});
      expect(result.current.webhookPollingInterval).toBe(5000);
      expect(result.current.currentSessionId).toBe("");
      expect(result.current.eventDelivery).toBe(EventDeliveryType.POLLING);
      expect(result.current.webhookAuthEnable).toBe(true);
      expect(result.current.defaultFolderName).toBe("Starter Project");
      expect(result.current.hideGettingStartedProgress).toBe(false);
    });
  });

  describe("setClientId", () => {
    it("should set client ID", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setClientId("client-123");
      });

      expect(result.current.clientId).toBe("client-123");
    });

    it("should update client ID when called multiple times", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setClientId("client-1");
      });
      expect(result.current.clientId).toBe("client-1");

      act(() => {
        result.current.setClientId("client-2");
      });
      expect(result.current.clientId).toBe("client-2");
    });

    it("should handle empty string client ID", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setClientId("");
      });

      expect(result.current.clientId).toBe("");
    });
  });

  describe("setChatValueStore", () => {
    it("should set chat value", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setChatValueStore("Hello world");
      });

      expect(result.current.chatValueStore).toBe("Hello world");
    });

    it("should handle empty chat value", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setChatValueStore("");
      });

      expect(result.current.chatValueStore).toBe("");
    });

    it("should handle multiline chat value", () => {
      const { result } = renderHook(() => useUtilityStore());
      const multilineValue = "Line 1\nLine 2\nLine 3";

      act(() => {
        result.current.setChatValueStore(multilineValue);
      });

      expect(result.current.chatValueStore).toBe(multilineValue);
    });
  });

  describe("setSelectedItems", () => {
    it("should add item to empty selection", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setSelectedItems("item-1");
      });

      expect(result.current.selectedItems).toEqual(["item-1"]);
    });

    it("should add multiple items", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setSelectedItems("item-1");
      });
      expect(result.current.selectedItems).toEqual(["item-1"]);

      act(() => {
        result.current.setSelectedItems("item-2");
      });
      expect(result.current.selectedItems).toEqual(["item-1", "item-2"]);
    });

    it("should remove item if already selected (toggle behavior)", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setSelectedItems("item-1");
        result.current.setSelectedItems("item-2");
      });
      expect(result.current.selectedItems).toEqual(["item-1", "item-2"]);

      act(() => {
        result.current.setSelectedItems("item-1");
      });
      expect(result.current.selectedItems).toEqual(["item-2"]);
    });

    it("should handle various item types", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setSelectedItems("string-item");
        result.current.setSelectedItems(123);
        result.current.setSelectedItems({ id: "object-item" });
      });

      expect(result.current.selectedItems).toEqual([
        "string-item",
        123,
        { id: "object-item" },
      ]);
    });

    it("should toggle same item multiple times", () => {
      const { result } = renderHook(() => useUtilityStore());

      // Add item
      act(() => {
        result.current.setSelectedItems("toggle-item");
      });
      expect(result.current.selectedItems).toEqual(["toggle-item"]);

      // Remove item
      act(() => {
        result.current.setSelectedItems("toggle-item");
      });
      expect(result.current.selectedItems).toEqual([]);

      // Add item again
      act(() => {
        result.current.setSelectedItems("toggle-item");
      });
      expect(result.current.selectedItems).toEqual(["toggle-item"]);
    });
  });

  describe("setHealthCheckTimeout", () => {
    it("should set health check timeout", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setHealthCheckTimeout("30000");
      });

      expect(result.current.healthCheckTimeout).toBe("30000");
    });

    it("should set timeout to null", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setHealthCheckTimeout("10000");
      });
      expect(result.current.healthCheckTimeout).toBe("10000");

      act(() => {
        result.current.setHealthCheckTimeout(null);
      });
      expect(result.current.healthCheckTimeout).toBeNull();
    });
  });

  describe("setPlaygroundScrollBehaves", () => {
    it("should set scroll behavior to smooth", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setPlaygroundScrollBehaves("smooth");
      });

      expect(result.current.playgroundScrollBehaves).toBe("smooth");
    });

    it("should set scroll behavior to auto", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setPlaygroundScrollBehaves("auto");
      });

      expect(result.current.playgroundScrollBehaves).toBe("auto");
    });

    it("should change scroll behavior multiple times", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setPlaygroundScrollBehaves("smooth");
      });
      expect(result.current.playgroundScrollBehaves).toBe("smooth");

      act(() => {
        result.current.setPlaygroundScrollBehaves("instant");
      });
      expect(result.current.playgroundScrollBehaves).toBe("instant");
    });
  });

  describe("setMaxFileSizeUpload", () => {
    it("should set max file size in MB and convert to bytes", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setMaxFileSizeUpload(50); // 50MB
      });

      expect(result.current.maxFileSizeUpload).toBe(50 * 1024 * 1024);
    });

    it("should handle different file size limits", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setMaxFileSizeUpload(10); // 10MB
      });
      expect(result.current.maxFileSizeUpload).toBe(10 * 1024 * 1024);

      act(() => {
        result.current.setMaxFileSizeUpload(500); // 500MB
      });
      expect(result.current.maxFileSizeUpload).toBe(500 * 1024 * 1024);
    });

    it("should handle zero file size", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setMaxFileSizeUpload(0);
      });

      expect(result.current.maxFileSizeUpload).toBe(0);
    });
  });

  describe("setSerializationMaxItemsLength", () => {
    it("should set serialization max items length", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setSerializationMaxItemsLength(200);
      });

      expect(result.current.serializationMaxItemsLength).toBe(200);
    });

    it("should handle different item length limits", () => {
      const { result } = renderHook(() => useUtilityStore());

      const limits = [50, 150, 500, 1000];
      limits.forEach((limit) => {
        act(() => {
          result.current.setSerializationMaxItemsLength(limit);
        });
        expect(result.current.serializationMaxItemsLength).toBe(limit);
      });
    });
  });

  describe("setFlowsPagination", () => {
    it("should set flows pagination", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setFlowsPagination(mockPagination);
      });

      expect(result.current.flowsPagination).toEqual(mockPagination);
    });

    it("should update pagination properties", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setFlowsPagination({ page: 3, size: 25 });
      });
      expect(result.current.flowsPagination).toEqual({ page: 3, size: 25 });

      act(() => {
        result.current.setFlowsPagination({ page: 1, size: 50 });
      });
      expect(result.current.flowsPagination).toEqual({ page: 1, size: 50 });
    });

    it("should handle edge case pagination values", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setFlowsPagination({ page: 0, size: 1 });
      });

      expect(result.current.flowsPagination).toEqual({ page: 0, size: 1 });
    });
  });

  describe("setTags", () => {
    it("should set tags array", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setTags([mockTag, mockTag2]);
      });

      expect(result.current.tags).toEqual([mockTag, mockTag2]);
    });

    it("should replace existing tags", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setTags([mockTag]);
      });
      expect(result.current.tags).toEqual([mockTag]);

      act(() => {
        result.current.setTags([mockTag2]);
      });
      expect(result.current.tags).toEqual([mockTag2]);
    });

    it("should handle empty tags array", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setTags([]);
      });

      expect(result.current.tags).toEqual([]);
    });
  });

  describe("setFeatureFlags", () => {
    it("should set feature flags", () => {
      const { result } = renderHook(() => useUtilityStore());
      const featureFlags = {
        enableNewFeature: true,
        betaMode: false,
        debugMode: true,
      };

      act(() => {
        result.current.setFeatureFlags(featureFlags);
      });

      expect(result.current.featureFlags).toEqual(featureFlags);
    });

    it("should handle complex feature flag structures", () => {
      const { result } = renderHook(() => useUtilityStore());
      const complexFlags = {
        ui: {
          darkMode: true,
          sidebar: { collapsed: false, width: 300 },
        },
        api: {
          version: "v2",
          timeout: 5000,
        },
        experiments: ["experiment1", "experiment2"],
      };

      act(() => {
        result.current.setFeatureFlags(complexFlags);
      });

      expect(result.current.featureFlags).toEqual(complexFlags);
    });

    it("should handle empty feature flags", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setFeatureFlags({});
      });

      expect(result.current.featureFlags).toEqual({});
    });
  });

  describe("setWebhookPollingInterval", () => {
    it("should set webhook polling interval", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setWebhookPollingInterval(10000);
      });

      expect(result.current.webhookPollingInterval).toBe(10000);
    });

    it("should handle different polling intervals", () => {
      const { result } = renderHook(() => useUtilityStore());

      const intervals = [1000, 5000, 30000, 60000];
      intervals.forEach((interval) => {
        act(() => {
          result.current.setWebhookPollingInterval(interval);
        });
        expect(result.current.webhookPollingInterval).toBe(interval);
      });
    });
  });

  describe("setCurrentSessionId", () => {
    it("should set current session ID", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setCurrentSessionId("session-123");
      });

      expect(result.current.currentSessionId).toBe("session-123");
    });

    it("should update session ID multiple times", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setCurrentSessionId("session-1");
      });
      expect(result.current.currentSessionId).toBe("session-1");

      act(() => {
        result.current.setCurrentSessionId("session-2");
      });
      expect(result.current.currentSessionId).toBe("session-2");
    });
  });

  describe("setEventDelivery", () => {
    it("should set event delivery to webhook", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setEventDelivery(EventDeliveryType.WEBHOOK);
      });

      expect(result.current.eventDelivery).toBe(EventDeliveryType.WEBHOOK);
    });

    it("should switch between event delivery types", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setEventDelivery(EventDeliveryType.WEBHOOK);
      });
      expect(result.current.eventDelivery).toBe(EventDeliveryType.WEBHOOK);

      act(() => {
        result.current.setEventDelivery(EventDeliveryType.POLLING);
      });
      expect(result.current.eventDelivery).toBe(EventDeliveryType.POLLING);
    });
  });

  describe("setWebhookAuthEnable", () => {
    it("should set webhook auth enable to false", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setWebhookAuthEnable(false);
      });

      expect(result.current.webhookAuthEnable).toBe(false);
    });

    it("should toggle webhook auth enable", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setWebhookAuthEnable(false);
      });
      expect(result.current.webhookAuthEnable).toBe(false);

      act(() => {
        result.current.setWebhookAuthEnable(true);
      });
      expect(result.current.webhookAuthEnable).toBe(true);
    });
  });

  describe("setDefaultFolderName", () => {
    it("should set defaultFolderName", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setDefaultFolderName("OpenRAG");
      });

      expect(result.current.defaultFolderName).toBe("OpenRAG");
    });

    it("should change defaultFolderName", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setDefaultFolderName("OpenRAG");
      });
      expect(result.current.defaultFolderName).toBe("OpenRAG");

      act(() => {
        result.current.setDefaultFolderName("My Custom Folder");
      });
      expect(result.current.defaultFolderName).toBe("My Custom Folder");
    });

    it("should handle various folder names", () => {
      const { result } = renderHook(() => useUtilityStore());

      const folderNames = [
        "Starter Project",
        "OpenRAG",
        "My Collection",
        "Custom Folder",
      ];
      folderNames.forEach((folderName) => {
        act(() => {
          result.current.setDefaultFolderName(folderName);
        });
        expect(result.current.defaultFolderName).toBe(folderName);
      });
    });
  });

  describe("setHideGettingStartedProgress", () => {
    it("should set hideGettingStartedProgress to true", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setHideGettingStartedProgress(true);
      });

      expect(result.current.hideGettingStartedProgress).toBe(true);
    });

    it("should toggle hideGettingStartedProgress", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setHideGettingStartedProgress(true);
      });
      expect(result.current.hideGettingStartedProgress).toBe(true);

      act(() => {
        result.current.setHideGettingStartedProgress(false);
      });
      expect(result.current.hideGettingStartedProgress).toBe(false);
    });
  });

  describe("state interactions", () => {
    it("should handle multiple state updates", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setClientId("test-client");
        result.current.setChatValueStore("test-chat");
        result.current.setSelectedItems("item-1");
        result.current.setSelectedItems("item-2");
        result.current.setCurrentSessionId("test-session");
      });

      expect(result.current.clientId).toBe("test-client");
      expect(result.current.chatValueStore).toBe("test-chat");
      expect(result.current.selectedItems).toEqual(["item-1", "item-2"]);
      expect(result.current.currentSessionId).toBe("test-session");
    });

    it("should maintain state consistency across multiple hook instances", () => {
      const { result: result1 } = renderHook(() => useUtilityStore());
      const { result: result2 } = renderHook(() => useUtilityStore());

      act(() => {
        result1.current.setClientId("shared-client");
      });

      expect(result1.current.clientId).toBe("shared-client");
      expect(result2.current.clientId).toBe("shared-client");
    });
  });

  describe("edge cases", () => {
    it("should handle rapid selected items toggles", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        for (let i = 0; i < 10; i++) {
          result.current.setSelectedItems("rapid-item");
        }
      });

      // Should be empty since we toggled even number of times
      expect(result.current.selectedItems).toEqual([]);
    });

    it("should handle large selected items array", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        for (let i = 0; i < 1000; i++) {
          result.current.setSelectedItems(`item-${i}`);
        }
      });

      expect(result.current.selectedItems).toHaveLength(1000);
    });

    it("should handle complex object selection", () => {
      const { result } = renderHook(() => useUtilityStore());
      const complexObject = {
        id: "complex",
        nested: { prop: "value" },
        array: [1, 2, 3],
      };

      act(() => {
        result.current.setSelectedItems(complexObject);
      });

      expect(result.current.selectedItems).toEqual([complexObject]);
    });

    it("should handle extreme pagination values", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setFlowsPagination({ page: 999999, size: 1 });
      });

      expect(result.current.flowsPagination).toEqual({ page: 999999, size: 1 });
    });

    it("should handle very large file size limits", () => {
      const { result } = renderHook(() => useUtilityStore());

      act(() => {
        result.current.setMaxFileSizeUpload(10000); // 10GB
      });

      expect(result.current.maxFileSizeUpload).toBe(10000 * 1024 * 1024);
    });
  });
});
