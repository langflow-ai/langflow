import type { APIClassType } from "@/types/api";
import {
  applyCloudDefaultOverrides,
  filterCloudCompatibleOptions,
  getCloudFieldOverride,
  getCloudIncompatibleOptions,
  getCloudOptionName,
  getCloudUiMetadata,
  isCloudIncompatibleOption,
  sanitizeCloudIncompatibleDefaults,
  withCurrentCloudMetadata,
} from "../cloudMetadataUtils";

// ---------------------------------------------------------------------------
// getCloudUiMetadata
// ---------------------------------------------------------------------------
describe("getCloudUiMetadata", () => {
  it("returns a plain object as CloudUiMetadata", () => {
    const obj = { cloud_default_overrides: { url: { placeholder: "x" } } };
    expect(getCloudUiMetadata(obj)).toBe(obj);
  });

  it.each([null, undefined, 42, "string", true, [1, 2]])(
    "returns undefined for non-object value: %p",
    (val) => {
      expect(getCloudUiMetadata(val)).toBeUndefined();
    },
  );
});

// ---------------------------------------------------------------------------
// getCloudOptionName
// ---------------------------------------------------------------------------
describe("getCloudOptionName", () => {
  it("extracts name from an object with a name property", () => {
    expect(getCloudOptionName({ name: "Local" })).toBe("Local");
  });

  it("returns the object itself when name is missing", () => {
    const obj = { id: 1 };
    expect(getCloudOptionName(obj)).toBe(obj);
  });

  it("returns primitives unchanged", () => {
    expect(getCloudOptionName("AWS")).toBe("AWS");
    expect(getCloudOptionName(42)).toBe(42);
  });
});

// ---------------------------------------------------------------------------
// isCloudIncompatibleOption
// ---------------------------------------------------------------------------
describe("isCloudIncompatibleOption", () => {
  it("returns true when an option name matches the incompatible list", () => {
    expect(isCloudIncompatibleOption({ name: "Local" }, ["Local"])).toBe(true);
  });

  it("returns false when option is not in the incompatible list", () => {
    expect(isCloudIncompatibleOption({ name: "AWS" }, ["Local"])).toBe(false);
  });

  it("returns false when the incompatible list is empty", () => {
    expect(isCloudIncompatibleOption({ name: "Local" }, [])).toBe(false);
  });

  it("defaults to an empty list when incompatibleOptions is omitted", () => {
    expect(isCloudIncompatibleOption({ name: "Local" })).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// filterCloudCompatibleOptions
// ---------------------------------------------------------------------------
describe("filterCloudCompatibleOptions", () => {
  it("removes options whose name appears in the incompatible list", () => {
    const options = [{ name: "Local" }, { name: "AWS" }, { name: "GCP" }];
    expect(filterCloudCompatibleOptions(options, ["Local"])).toEqual([
      { name: "AWS" },
      { name: "GCP" },
    ]);
  });

  it("returns the original array reference when the incompatible list is empty", () => {
    const options = [{ name: "AWS" }];
    expect(filterCloudCompatibleOptions(options, [])).toBe(options);
  });

  it("returns undefined when options is undefined", () => {
    expect(filterCloudCompatibleOptions(undefined, ["Local"])).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// getCloudFieldOverride
// ---------------------------------------------------------------------------
describe("getCloudFieldOverride", () => {
  it("returns the override for a matching field", () => {
    const metadata = {
      cloud_default_overrides: { url: { placeholder: "Cloud URL" } },
    };
    expect(getCloudFieldOverride(metadata, "url")).toEqual({
      placeholder: "Cloud URL",
    });
  });

  it("returns undefined for a non-matching field", () => {
    const metadata = {
      cloud_default_overrides: { url: { placeholder: "Cloud URL" } },
    };
    expect(getCloudFieldOverride(metadata, "api_key")).toBeUndefined();
  });

  it("returns undefined when metadata is undefined", () => {
    expect(getCloudFieldOverride(undefined, "url")).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// getCloudIncompatibleOptions
// ---------------------------------------------------------------------------
describe("getCloudIncompatibleOptions", () => {
  it("returns the incompatible list for a matching field", () => {
    const metadata = {
      cloud_incompatible_options: { storage_location: ["Local", "NFS"] },
    };
    expect(getCloudIncompatibleOptions(metadata, "storage_location")).toEqual([
      "Local",
      "NFS",
    ]);
  });

  it("returns an empty array when the field has no entry", () => {
    const metadata = { cloud_incompatible_options: {} };
    expect(getCloudIncompatibleOptions(metadata, "storage_location")).toEqual(
      [],
    );
  });

  it("returns an empty array when metadata is undefined", () => {
    expect(getCloudIncompatibleOptions(undefined, "storage_location")).toEqual(
      [],
    );
  });

  it("returns an empty array when the entry is not an array", () => {
    const metadata = {
      cloud_incompatible_options: { storage_location: "Local" as unknown },
    };
    expect(
      getCloudIncompatibleOptions(
        metadata as { cloud_incompatible_options: Record<string, unknown[]> },
        "storage_location",
      ),
    ).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// applyCloudDefaultOverrides
// ---------------------------------------------------------------------------
describe("applyCloudDefaultOverrides", () => {
  function makeComponent(
    template: Record<string, Record<string, unknown>>,
  ): APIClassType {
    return {
      description: "test",
      display_name: "Test",
      documentation: "",
      template,
    } as APIClassType;
  }

  it("sets both value and placeholder on the matching template field", () => {
    const component = makeComponent({
      url: { value: "", placeholder: "Local" },
    });
    applyCloudDefaultOverrides(component, {
      url: { value: "https://cloud.example.com", placeholder: "Cloud URL" },
    });
    expect(component.template.url.value).toBe("https://cloud.example.com");
    expect(component.template.url.placeholder).toBe("Cloud URL");
  });

  it("sets placeholder without touching value when value is omitted", () => {
    const component = makeComponent({
      url: { value: "keep-me", placeholder: "Local" },
    });
    applyCloudDefaultOverrides(component, {
      url: { placeholder: "Cloud URL" },
    });
    expect(component.template.url.value).toBe("keep-me");
    expect(component.template.url.placeholder).toBe("Cloud URL");
  });

  it("skips fields that don't exist in the template", () => {
    const component = makeComponent({});
    // Should not throw
    applyCloudDefaultOverrides(component, {
      nonexistent: { value: "x" },
    });
    expect(component.template["nonexistent"]).toBeUndefined();
  });

  it("is a no-op when overrides is undefined", () => {
    const component = makeComponent({ url: { value: "original" } });
    applyCloudDefaultOverrides(component, undefined);
    expect(component.template.url.value).toBe("original");
  });
});

// ---------------------------------------------------------------------------
// sanitizeCloudIncompatibleDefaults
// ---------------------------------------------------------------------------
describe("sanitizeCloudIncompatibleDefaults", () => {
  function makeComponent(
    template: Record<string, Record<string, unknown>>,
  ): APIClassType {
    return {
      description: "test",
      display_name: "Test",
      documentation: "",
      template,
    } as APIClassType;
  }

  it("removes incompatible selections and keeps compatible ones", () => {
    const component = makeComponent({
      storage: {
        value: [{ name: "Local" }, { name: "AWS" }],
        options: [{ name: "Local" }, { name: "AWS" }, { name: "GCP" }],
        limit: 2,
      },
    });
    sanitizeCloudIncompatibleDefaults(component, {
      storage: ["Local"],
    });
    expect(component.template.storage.value).toEqual([{ name: "AWS" }]);
  });

  it("auto-selects the first compatible option when all selections are incompatible and limit=1", () => {
    const component = makeComponent({
      storage: {
        value: [{ name: "Local" }],
        options: [{ name: "Local" }, { name: "AWS" }, { name: "GCP" }],
        limit: 1,
      },
    });
    sanitizeCloudIncompatibleDefaults(component, {
      storage: ["Local"],
    });
    // Should auto-select first compatible option (AWS)
    expect(component.template.storage.value).toEqual([{ name: "AWS" }]);
  });

  it("leaves an empty array when all options are incompatible and limit!=1", () => {
    const component = makeComponent({
      storage: {
        value: [{ name: "Local" }],
        options: [{ name: "Local" }],
        limit: 2,
      },
    });
    sanitizeCloudIncompatibleDefaults(component, {
      storage: ["Local"],
    });
    expect(component.template.storage.value).toEqual([]);
  });

  it("is a no-op when incompatibleOptions is undefined", () => {
    const component = makeComponent({
      storage: { value: [{ name: "Local" }] },
    });
    sanitizeCloudIncompatibleDefaults(component, undefined);
    expect(component.template.storage.value).toEqual([{ name: "Local" }]);
  });

  it("skips fields that don't exist in the template", () => {
    const component = makeComponent({});
    sanitizeCloudIncompatibleDefaults(component, {
      nonexistent: ["Local"],
    });
    expect(component.template["nonexistent"]).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// withCurrentCloudMetadata
// ---------------------------------------------------------------------------
describe("withCurrentCloudMetadata", () => {
  function makeNode(overrides: Record<string, unknown> = {}): APIClassType {
    return {
      description: "test",
      display_name: "Test",
      documentation: "",
      template: {},
      ...overrides,
    } as APIClassType;
  }

  it("returns the saved node unchanged when catalog node is undefined", () => {
    const saved = makeNode();
    expect(withCurrentCloudMetadata(saved, undefined)).toBe(saved);
  });

  it("returns undefined when saved node is undefined", () => {
    expect(withCurrentCloudMetadata(undefined, makeNode())).toBeUndefined();
  });

  it("returns the saved node unchanged when no overlay is needed", () => {
    const saved = makeNode({
      cloud_compatible: true,
      metadata: {
        cloud_default_overrides: { url: { placeholder: "saved" } },
        cloud_incompatible_options: { storage: ["Local"] },
      },
    });
    const catalog = makeNode({
      cloud_compatible: false,
      metadata: {
        cloud_default_overrides: { url: { placeholder: "catalog" } },
        cloud_incompatible_options: { storage: ["NFS"] },
      },
    });
    // Saved already has all cloud fields, so it should be returned as-is
    expect(withCurrentCloudMetadata(saved, catalog)).toBe(saved);
  });

  it("overlays cloud_compatible from catalog when saved node is missing it", () => {
    const saved = makeNode(); // no cloud_compatible
    const catalog = makeNode({ cloud_compatible: false });

    const result = withCurrentCloudMetadata(saved, catalog);
    expect(result).not.toBe(saved);
    expect(result?.cloud_compatible).toBe(false);
  });

  it("overlays cloud_default_overrides from catalog when saved metadata lacks it", () => {
    const saved = makeNode({ metadata: {} });
    const catalog = makeNode({
      metadata: {
        cloud_default_overrides: { url: { placeholder: "Cloud URL" } },
      },
    });

    const result = withCurrentCloudMetadata(saved, catalog);
    expect(result).not.toBe(saved);
    expect(
      (result?.metadata as Record<string, unknown>)?.cloud_default_overrides,
    ).toEqual({ url: { placeholder: "Cloud URL" } });
  });

  it("overlays cloud_incompatible_options from catalog when saved metadata lacks it", () => {
    const saved = makeNode({ metadata: {} });
    const catalog = makeNode({
      metadata: {
        cloud_incompatible_options: { storage: ["Local"] },
      },
    });

    const result = withCurrentCloudMetadata(saved, catalog);
    expect(
      (result?.metadata as Record<string, unknown>)
        ?.cloud_incompatible_options,
    ).toEqual({ storage: ["Local"] });
  });

  it("does not overwrite existing cloud_compatible on saved node", () => {
    const saved = makeNode({ cloud_compatible: true });
    const catalog = makeNode({ cloud_compatible: false });

    const result = withCurrentCloudMetadata(saved, catalog);
    // Saved already has cloud_compatible, so it should not be overwritten
    expect(result?.cloud_compatible).toBe(true);
  });

  it("preserves non-cloud metadata keys from the saved node during overlay", () => {
    const saved = makeNode({
      metadata: { custom_key: "keep-me" },
    });
    const catalog = makeNode({
      metadata: {
        cloud_default_overrides: { url: { placeholder: "Cloud URL" } },
      },
    });

    const result = withCurrentCloudMetadata(saved, catalog);
    const meta = result?.metadata as Record<string, unknown>;
    expect(meta?.custom_key).toBe("keep-me");
    expect(meta?.cloud_default_overrides).toEqual({
      url: { placeholder: "Cloud URL" },
    });
  });

  it("overlays all three fields simultaneously", () => {
    const saved = makeNode(); // no cloud fields at all
    const catalog = makeNode({
      cloud_compatible: false,
      metadata: {
        cloud_default_overrides: { url: { placeholder: "Cloud" } },
        cloud_incompatible_options: { storage: ["Local"] },
      },
    });

    const result = withCurrentCloudMetadata(saved, catalog);
    expect(result?.cloud_compatible).toBe(false);
    const meta = result?.metadata as Record<string, unknown>;
    expect(meta?.cloud_default_overrides).toEqual({
      url: { placeholder: "Cloud" },
    });
    expect(meta?.cloud_incompatible_options).toEqual({
      storage: ["Local"],
    });
  });
});
