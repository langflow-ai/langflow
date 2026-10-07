import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { CONNECTION_NAME_MAX_LENGTH, CONNECTION_NAME_PATTERN } from "../types";

const backendModels = readFileSync(
  resolve(__dirname, "../../../../../../../lfx/src/lfx/integrations/models.py"),
  "utf8",
);

describe("connection handle validation parity", () => {
  it("matches the backend name pattern", () => {
    const pattern = backendModels.match(
      /^CONNECTION_NAME_PATTERN\s*=\s*r["'](.+)["']$/m,
    );
    expect(pattern).not.toBeNull();
    expect(CONNECTION_NAME_PATTERN.source).toBe(pattern?.[1]);
  });

  it("matches the backend name length limit", () => {
    const nameField = backendModels.match(
      /name:\s*StrictStr\s*=\s*Field\(\s*pattern=CONNECTION_NAME_PATTERN,\s*max_length=(\d+)\s*\)/,
    );
    expect(nameField).not.toBeNull();
    expect(CONNECTION_NAME_MAX_LENGTH).toBe(Number(nameField?.[1]));
  });
});
