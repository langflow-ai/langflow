import {
  handlesMatch,
  scapedJSONStringfy,
  typeIsCompatibleWith,
  typesAreCompatible,
} from "../reactflowUtils";

// --- Named constants (no magic values) ---

// Migration pairs: old -> new
const OLD_TYPE_DATA = "Data";
const NEW_TYPE_JSON = "JSON";
const OLD_TYPE_DATAFRAME = "DataFrame";
const NEW_TYPE_TABLE = "Table";

// Unrelated types (not part of any migration)
const TYPE_MESSAGE = "Message";
const TYPE_STRING = "str";

// Handle identity fields
const SOURCE_DATA_TYPE = "AstraDB";
const SOURCE_ID = "AstraDB-abc123";
const SOURCE_NAME = "dataframe";

const TARGET_FIELD_NAME = "input_data";
const TARGET_ID = "Parser-abc123";
const TARGET_TYPE = "other";

// --- Helper to build encoded handle strings ---

function makeSourceHandle(overrides: Record<string, unknown> = {}): string {
  const base = {
    dataType: SOURCE_DATA_TYPE,
    id: SOURCE_ID,
    name: SOURCE_NAME,
    output_types: [OLD_TYPE_DATAFRAME],
  };
  return scapedJSONStringfy({ ...base, ...overrides });
}

function makeTargetHandle(overrides: Record<string, unknown> = {}): string {
  const base = {
    fieldName: TARGET_FIELD_NAME,
    id: TARGET_ID,
    inputTypes: [OLD_TYPE_DATAFRAME, OLD_TYPE_DATA],
    type: TARGET_TYPE,
  };
  return scapedJSONStringfy({ ...base, ...overrides });
}

// ============================================================
// typeIsCompatibleWith
// ============================================================

describe("typeIsCompatibleWith", () => {
  // --- SUCCESS cases ---

  it("should match identical types (Data -> [Data])", () => {
    expect(typeIsCompatibleWith(OLD_TYPE_DATA, [OLD_TYPE_DATA])).toBe(true);
  });

  it("should match old output to new input (Data -> [JSON])", () => {
    expect(typeIsCompatibleWith(OLD_TYPE_DATA, [NEW_TYPE_JSON])).toBe(true);
  });

  it("should match new output to old input (JSON -> [Data])", () => {
    expect(typeIsCompatibleWith(NEW_TYPE_JSON, [OLD_TYPE_DATA])).toBe(true);
  });

  it("should match new to new (JSON -> [JSON])", () => {
    expect(typeIsCompatibleWith(NEW_TYPE_JSON, [NEW_TYPE_JSON])).toBe(true);
  });

  it("should match DataFrame to Table (old -> new)", () => {
    expect(typeIsCompatibleWith(OLD_TYPE_DATAFRAME, [NEW_TYPE_TABLE])).toBe(
      true,
    );
  });

  it("should match Table to DataFrame (new -> old)", () => {
    expect(typeIsCompatibleWith(NEW_TYPE_TABLE, [OLD_TYPE_DATAFRAME])).toBe(
      true,
    );
  });

  it("should match when target has multiple types and one matches", () => {
    expect(
      typeIsCompatibleWith(OLD_TYPE_DATA, [TYPE_MESSAGE, NEW_TYPE_JSON]),
    ).toBe(true);
  });

  it("should match non-migrated types (Message -> [Message])", () => {
    expect(typeIsCompatibleWith(TYPE_MESSAGE, [TYPE_MESSAGE])).toBe(true);
  });

  // --- NEGATIVE cases ---

  it("should not match completely different types (Data -> [Message])", () => {
    expect(typeIsCompatibleWith(OLD_TYPE_DATA, [TYPE_MESSAGE])).toBe(false);
  });

  it("should not match cross-family (Data -> [Table])", () => {
    expect(typeIsCompatibleWith(OLD_TYPE_DATA, [NEW_TYPE_TABLE])).toBe(false);
  });

  it("should not match JSON to Table", () => {
    expect(typeIsCompatibleWith(NEW_TYPE_JSON, [NEW_TYPE_TABLE])).toBe(false);
  });

  it("should not match empty target array", () => {
    expect(typeIsCompatibleWith(OLD_TYPE_DATA, [])).toBe(false);
  });

  it("should not match case-sensitive ('data' vs [Data])", () => {
    const LOWERCASE_DATA = "data";
    expect(typeIsCompatibleWith(LOWERCASE_DATA, [OLD_TYPE_DATA])).toBe(false);
  });
});

// ============================================================
// typesAreCompatible
// ============================================================

describe("typesAreCompatible", () => {
  // --- SUCCESS cases ---

  it("should match when any source matches any target", () => {
    expect(
      typesAreCompatible([TYPE_MESSAGE, OLD_TYPE_DATA], [NEW_TYPE_JSON]),
    ).toBe(true);
  });

  it("should match with mixed old/new types in both lists", () => {
    expect(
      typesAreCompatible(
        [OLD_TYPE_DATAFRAME, TYPE_STRING],
        [TYPE_MESSAGE, NEW_TYPE_TABLE],
      ),
    ).toBe(true);
  });

  // --- NEGATIVE cases ---

  it("should not match when no types overlap", () => {
    expect(
      typesAreCompatible(
        [OLD_TYPE_DATA, OLD_TYPE_DATAFRAME],
        [TYPE_MESSAGE, TYPE_STRING],
      ),
    ).toBe(false);
  });

  it("should not match empty source list", () => {
    expect(typesAreCompatible([], [OLD_TYPE_DATA, TYPE_MESSAGE])).toBe(false);
  });

  it("should not match when both empty", () => {
    expect(typesAreCompatible([], [])).toBe(false);
  });
});

// ============================================================
// handlesMatch
// ============================================================

describe("handlesMatch", () => {
  // --- SUCCESS cases ---

  it("should match identical handles (same string)", () => {
    const handle = makeSourceHandle();
    expect(handlesMatch(handle, handle)).toBe(true);
  });

  it("should match source handles where output_types differ by migration (DataFrame vs Table)", () => {
    const expectedHandle = makeSourceHandle({
      output_types: [OLD_TYPE_DATAFRAME],
    });
    const actualHandle = makeSourceHandle({
      output_types: [NEW_TYPE_TABLE],
    });
    expect(handlesMatch(expectedHandle, actualHandle)).toBe(true);
  });

  it("should match target handles where inputTypes differ by migration (Data vs JSON)", () => {
    const expectedHandle = makeTargetHandle({
      inputTypes: [OLD_TYPE_DATA],
    });
    const actualHandle = makeTargetHandle({
      inputTypes: [NEW_TYPE_JSON],
    });
    expect(handlesMatch(expectedHandle, actualHandle)).toBe(true);
  });

  // --- NEGATIVE cases ---

  it("should not match handles with different ids", () => {
    const DIFFERENT_ID = "AstraDB-different";
    const expectedHandle = makeSourceHandle({ id: SOURCE_ID });
    const actualHandle = makeSourceHandle({ id: DIFFERENT_ID });
    expect(handlesMatch(expectedHandle, actualHandle)).toBe(false);
  });

  it("should not match handles with different names", () => {
    const DIFFERENT_NAME = "other_output";
    const expectedHandle = makeSourceHandle({ name: SOURCE_NAME });
    const actualHandle = makeSourceHandle({ name: DIFFERENT_NAME });
    expect(handlesMatch(expectedHandle, actualHandle)).toBe(false);
  });

  it("should not match handles with different dataTypes", () => {
    const DIFFERENT_DATA_TYPE = "OpenAI";
    const expectedHandle = makeSourceHandle({ dataType: SOURCE_DATA_TYPE });
    const actualHandle = makeSourceHandle({ dataType: DIFFERENT_DATA_TYPE });
    expect(handlesMatch(expectedHandle, actualHandle)).toBe(false);
  });

  it("should not match invalid/malformed handle strings", () => {
    const MALFORMED_HANDLE = "œœœ{not-valid-jsonœœœ";
    const validHandle = makeSourceHandle();
    expect(handlesMatch(validHandle, MALFORMED_HANDLE)).toBe(false);
  });

  it("should not match handles where types differ and are not migration-related", () => {
    const expectedHandle = makeSourceHandle({
      output_types: [TYPE_MESSAGE],
    });
    const actualHandle = makeSourceHandle({
      output_types: [TYPE_STRING],
    });
    expect(handlesMatch(expectedHandle, actualHandle)).toBe(false);
  });

  // --- EDGE CASES ---

  it("should return false when parsing fails (garbage strings)", () => {
    const GARBAGE_A = "completely-garbage-string-no-json";
    const GARBAGE_B = "another-garbage!!!";
    expect(handlesMatch(GARBAGE_A, GARBAGE_B)).toBe(false);
  });

  it("should handle handles with empty type arrays", () => {
    const expectedHandle = makeSourceHandle({ output_types: [] });
    const actualHandle = makeSourceHandle({ output_types: [] });
    expect(handlesMatch(expectedHandle, actualHandle)).toBe(true);
  });

  it("should not match target handles with different fieldNames", () => {
    const DIFFERENT_FIELD = "other_field";
    const expectedHandle = makeTargetHandle({ fieldName: TARGET_FIELD_NAME });
    const actualHandle = makeTargetHandle({ fieldName: DIFFERENT_FIELD });
    expect(handlesMatch(expectedHandle, actualHandle)).toBe(false);
  });

  it("should not match target handles with different type property", () => {
    const DIFFERENT_TYPE = "str";
    const expectedHandle = makeTargetHandle({ type: TARGET_TYPE });
    const actualHandle = makeTargetHandle({ type: DIFFERENT_TYPE });
    expect(handlesMatch(expectedHandle, actualHandle)).toBe(false);
  });
});
