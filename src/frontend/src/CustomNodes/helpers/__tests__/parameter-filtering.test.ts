import type { InputFieldType } from "@/types/api";

jest.mock("@/customization/feature-flags", () => ({
  ...jest.requireActual("@/customization/feature-flags"),
  ENABLE_INTEGRATIONS: false,
}));

// The code under test reads the flag at call time, so flipping the mocked
// export covers INT-8 turning ENABLE_INTEGRATIONS on.
const setEnableIntegrations = (value: boolean) => {
  const flags = jest.requireMock("@/customization/feature-flags") as {
    ENABLE_INTEGRATIONS: boolean;
  };
  flags.ENABLE_INTEGRATIONS = value;
};

import { findPrimaryInput } from "../../GenericNode/components/RenderInputParameters/utils";
import {
  isCanvasVisible,
  isHidden,
  isManageableParameter,
} from "../parameter-filtering";

const field = (overrides: Partial<InputFieldType> = {}): InputFieldType =>
  ({
    type: "str",
    required: false,
    list: false,
    show: true,
    readonly: false,
    advanced: false,
    ...overrides,
  }) as InputFieldType;

const requiredConnection = field({ type: "connection_ref", required: true });
const optionalConnection = field({ type: "connection_ref", required: false });

describe("parameter filtering for connection_ref fields", () => {
  afterEach(() => {
    setEnableIntegrations(false);
  });

  describe("with ENABLE_INTEGRATIONS off", () => {
    it.each([
      ["required", requiredConnection],
      ["optional", optionalConnection],
    ])("keeps a %s connection_ref field off the canvas", (_, template) => {
      expect(isHidden(template, false)).toBe(true);
      expect(isCanvasVisible(template, false)).toBe(false);
    });

    it.each([
      ["required", requiredConnection],
      ["optional", optionalConnection],
    ])(
      "keeps a %s connection_ref field out of the Inspector Panel",
      (_, template) => {
        expect(isManageableParameter("connection", template, false)).toBe(
          false,
        );
      },
    );

    it("leaves other fields and the existing rules unchanged", () => {
      expect(isCanvasVisible(field(), false)).toBe(true);
      expect(isManageableParameter("to", field(), false)).toBe(true);
      expect(isCanvasVisible(field({ show: false }), false)).toBe(false);
      expect(isCanvasVisible(field({ advanced: true }), false)).toBe(false);
      expect(
        isManageableParameter("to", field({ advanced: true }), false),
      ).toBe(true);
      expect(isHidden(field({ tool_mode: true }), true)).toBe(true);
      expect(isManageableParameter("_type", field(), false)).toBe(false);
      expect(
        isManageableParameter("to", field({ readonly: true }), false),
      ).toBe(false);
    });

    it("drops the hidden field's handle so the next handle becomes primary", () => {
      const templates = {
        connection: requiredConnection,
        input_value: field({ input_types: ["Message"] }),
      };
      const shownFields = Object.keys(templates).filter((name) =>
        isCanvasVisible(templates[name], false),
      );

      const { displayHandleMap, primaryInputFieldName } = findPrimaryInput(
        shownFields,
        templates,
        false,
        "node-1",
        [],
      );

      expect(shownFields).toEqual(["input_value"]);
      expect(displayHandleMap.has("connection")).toBe(false);
      expect(primaryInputFieldName).toBe("input_value");
    });
  });

  describe("with ENABLE_INTEGRATIONS on", () => {
    beforeEach(() => {
      setEnableIntegrations(true);
    });

    it("treats connection_ref like any other field", () => {
      expect(isHidden(requiredConnection, false)).toBe(false);
      expect(isCanvasVisible(requiredConnection, false)).toBe(true);
      expect(
        isManageableParameter("connection", requiredConnection, false),
      ).toBe(true);
      expect(
        isCanvasVisible({ ...optionalConnection, advanced: true }, false),
      ).toBe(false);
    });
  });
});
