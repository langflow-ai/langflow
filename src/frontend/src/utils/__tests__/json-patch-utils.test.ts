import {
  createAddOperation,
  createCopyOperation,
  createMoveOperation,
  createRemoveOperation,
  createReplaceOperation,
  createTestOperation,
} from "../json-patch-utils";

describe("JSON Patch Utilities", () => {
  describe("createReplaceOperation", () => {
    it("should create a valid replace operation", () => {
      const operation = createReplaceOperation("/name", "New Name");

      expect(operation).toEqual({
        op: "replace",
        path: "/name",
        value: "New Name",
      });
    });

    it("should handle complex values", () => {
      const complexValue = { nodes: [{ id: "1" }], edges: [] };
      const operation = createReplaceOperation("/data", complexValue);

      expect(operation).toEqual({
        op: "replace",
        path: "/data",
        value: complexValue,
      });
    });

    it("should handle null values", () => {
      const operation = createReplaceOperation("/endpoint_name", null);

      expect(operation).toEqual({
        op: "replace",
        path: "/endpoint_name",
        value: null,
      });
    });
  });

  describe("createAddOperation", () => {
    it("should create a valid add operation", () => {
      const operation = createAddOperation("/tags", ["tag1", "tag2"]);

      expect(operation).toEqual({
        op: "add",
        path: "/tags",
        value: ["tag1", "tag2"],
      });
    });

    it("should handle adding to arrays with -", () => {
      const operation = createAddOperation("/tags/-", "new-tag");

      expect(operation).toEqual({
        op: "add",
        path: "/tags/-",
        value: "new-tag",
      });
    });

    it("should handle object values", () => {
      const newNode = { id: "node-1", type: "custom" };
      const operation = createAddOperation("/data/nodes/-", newNode);

      expect(operation).toEqual({
        op: "add",
        path: "/data/nodes/-",
        value: newNode,
      });
    });
  });

  describe("createRemoveOperation", () => {
    it("should create a valid remove operation", () => {
      const operation = createRemoveOperation("/endpoint_name");

      expect(operation).toEqual({
        op: "remove",
        path: "/endpoint_name",
      });
    });

    it("should handle array index removal", () => {
      const operation = createRemoveOperation("/tags/0");

      expect(operation).toEqual({
        op: "remove",
        path: "/tags/0",
      });
    });

    it("should handle nested path removal", () => {
      const operation = createRemoveOperation("/data/nodes/0/data/api_key");

      expect(operation).toEqual({
        op: "remove",
        path: "/data/nodes/0/data/api_key",
      });
    });
  });

  describe("createMoveOperation", () => {
    it("should create a valid move operation", () => {
      const operation = createMoveOperation("/tags/0", "/tags/1");

      expect(operation).toEqual({
        op: "move",
        from: "/tags/0",
        path: "/tags/1",
      });
    });

    it("should handle complex paths", () => {
      const operation = createMoveOperation("/data/nodes/0", "/data/nodes/1");

      expect(operation).toEqual({
        op: "move",
        from: "/data/nodes/0",
        path: "/data/nodes/1",
      });
    });
  });

  describe("createCopyOperation", () => {
    it("should create a valid copy operation", () => {
      const operation = createCopyOperation("/tags/0", "/tags/1");

      expect(operation).toEqual({
        op: "copy",
        from: "/tags/0",
        path: "/tags/1",
      });
    });

    it("should handle nested paths", () => {
      const operation = createCopyOperation("/data/nodes/0", "/data/nodes/1");

      expect(operation).toEqual({
        op: "copy",
        from: "/data/nodes/0",
        path: "/data/nodes/1",
      });
    });
  });

  describe("createTestOperation", () => {
    it("should create a valid test operation", () => {
      const operation = createTestOperation("/name", "Expected Name");

      expect(operation).toEqual({
        op: "test",
        path: "/name",
        value: "Expected Name",
      });
    });

    it("should handle boolean values", () => {
      const operation = createTestOperation("/is_component", true);

      expect(operation).toEqual({
        op: "test",
        path: "/is_component",
        value: true,
      });
    });

    it("should handle null values", () => {
      const operation = createTestOperation("/endpoint_name", null);

      expect(operation).toEqual({
        op: "test",
        path: "/endpoint_name",
        value: null,
      });
    });

    it("should handle object values", () => {
      const expectedData = { nodes: [], edges: [] };
      const operation = createTestOperation("/data", expectedData);

      expect(operation).toEqual({
        op: "test",
        path: "/data",
        value: expectedData,
      });
    });
  });

  describe("integration scenarios", () => {
    it("should create multiple operations for a complex update", () => {
      const operations = [
        createReplaceOperation("/name", "Updated Flow"),
        createReplaceOperation("/description", "New description"),
        createAddOperation("/tags", ["production", "verified"]),
        createRemoveOperation("/endpoint_name"),
      ];

      expect(operations).toHaveLength(4);
      expect(operations[0].op).toBe("replace");
      expect(operations[1].op).toBe("replace");
      expect(operations[2].op).toBe("add");
      expect(operations[3].op).toBe("remove");
    });

    it("should create operations with test-first pattern", () => {
      const operations = [
        createTestOperation("/name", "Old Name"),
        createReplaceOperation("/name", "New Name"),
      ];

      expect(operations).toHaveLength(2);
      expect(operations[0].op).toBe("test");
      expect(operations[0].value).toBe("Old Name");
      expect(operations[1].op).toBe("replace");
      expect(operations[1].value).toBe("New Name");
    });
  });
});
