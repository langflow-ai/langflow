import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import type { TAB_TYPES } from "@/types/global_variables";
import GlobalVariableModal from "../GlobalVariableModal";
import { assignTab } from "../utils/assign-tab";

const mockUpsert = jest.fn();
const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();
const mockUseGetTypes = jest.fn((_options?: unknown) => ({}));
const mockGlobalVariablesData: unknown[] = [];
const mockUseGetGlobalVariables = jest.fn((_options?: unknown) => ({
  data: mockGlobalVariablesData,
}));
const mockUseGlobalVariableUpsert = jest.fn(
  (_scope?: unknown, _variables?: unknown) => ({
    upsertGlobalVariable: mockUpsert,
    updateGlobalVariable: jest.fn(),
  }),
);

// BaseModal is mocked to a passthrough that renders the modal body plus a
// stand-in submit button wired to onSubmit, so the test drives handleSaveVariable
// deterministically without depending on the real dialog/footer internals.
jest.mock("@/modals/baseModal", () => {
  const Mock = ({
    children,
    onSubmit,
  }: {
    children: ReactNode;
    onSubmit?: () => void;
  }) => (
    <div data-testid="base-modal">
      {children}
      <button
        type="button"
        data-testid="modal-submit"
        onClick={() => onSubmit?.()}
      >
        submit
      </button>
    </div>
  );
  Mock.Header = ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  );
  Mock.Trigger = ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  );
  Mock.Content = ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  );
  Mock.Footer = () => null;
  return { __esModule: true, default: Mock };
});

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: () => null,
}));

jest.mock("../../parameterRenderComponent/components/inputComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/controllers/API/queries/flows/use-get-types", () => ({
  useGetTypes: (options?: unknown) => mockUseGetTypes(options),
}));

jest.mock("@/stores/typesStore", () => {
  // Stable reference: the modal feeds ComponentFields into a useEffect dep list,
  // so a fresh Set per render would loop.
  const componentFields = new Set<string>();
  return {
    useTypesStore: (
      selector: (s: { ComponentFields: Set<string> }) => unknown,
    ) => selector({ ComponentFields: componentFields }),
  };
});

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (
    selector: (s: {
      setSuccessData: typeof mockSetSuccessData;
      setErrorData: typeof mockSetErrorData;
    }) => unknown,
  ) =>
    selector({
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
    }),
}));

jest.mock("@/controllers/API/queries/variables", () => {
  return {
    useGetGlobalVariables: (options?: unknown) =>
      mockUseGetGlobalVariables(options),
    useGlobalVariableUpsert: (scope?: unknown, variables?: unknown) =>
      mockUseGlobalVariableUpsert(scope, variables),
  };
});

jest.mock("react-i18next", () => ({
  ...jest.requireActual("react-i18next"),
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe("GlobalVariableModal - assignTab Function", () => {
  describe("Basic Functionality", () => {
    it("should convert 'credential' (lowercase) to 'Credential'", () => {
      const result = assignTab("credential");
      expect(result).toBe("Credential");
    });

    it("should convert 'generic' (lowercase) to 'Generic'", () => {
      const result = assignTab("generic");
      expect(result).toBe("Generic");
    });

    it("should preserve 'Credential' input", () => {
      const result = assignTab("Credential");
      expect(result).toBe("Credential");
    });

    it("should preserve 'Generic' input", () => {
      const result = assignTab("Generic");
      expect(result).toBe("Generic");
    });
  });

  describe("Case Insensitivity", () => {
    it("should handle uppercase 'CREDENTIAL'", () => {
      const result = assignTab("CREDENTIAL");
      expect(result).toBe("Credential");
    });

    it("should handle uppercase 'GENERIC'", () => {
      const result = assignTab("GENERIC");
      expect(result).toBe("Generic");
    });

    it("should handle mixed case 'CrEdEnTiAl'", () => {
      const result = assignTab("CrEdEnTiAl");
      expect(result).toBe("Credential");
    });

    it("should handle mixed case 'GeNeRiC'", () => {
      const result = assignTab("GeNeRiC");
      expect(result).toBe("Generic");
    });
  });

  describe("Default Behavior", () => {
    it("should default to 'Credential' for unknown input", () => {
      const result = assignTab("unknown");
      expect(result).toBe("Credential");
    });

    it("should default to 'Credential' for empty string", () => {
      const result = assignTab("");
      expect(result).toBe("Credential");
    });

    it("should default to 'Credential' for whitespace", () => {
      const result = assignTab("   ");
      expect(result).toBe("Credential");
    });

    it("should default to 'Credential' for special characters", () => {
      const result = assignTab("@#$%");
      expect(result).toBe("Credential");
    });

    it("should default to 'Credential' for numeric input", () => {
      const result = assignTab("123");
      expect(result).toBe("Credential");
    });

    it("should default to 'Credential' for null/undefined converted to string", () => {
      const result = assignTab("null");
      expect(result).toBe("Credential");
    });
  });

  describe("Edge Cases", () => {
    it("should handle 'credential ' with trailing space", () => {
      const result = assignTab("credential ");
      expect(result).toBe("Credential");
    });

    it("should handle ' credential' with leading space", () => {
      const result = assignTab(" credential");
      expect(result).toBe("Credential");
    });

    it("should handle multiple spaces around input", () => {
      const result = assignTab("  generic  ");
      expect(result).toBe("Generic");
    });
  });

  describe("Return Type Safety", () => {
    it("should always return a valid TAB_TYPES value", () => {
      const validTypes: TAB_TYPES[] = ["Credential", "Generic"];

      const inputs = [
        "credential",
        "generic",
        "Credential",
        "Generic",
        "unknown",
        "",
      ];

      inputs.forEach((input) => {
        const result = assignTab(input);
        expect(validTypes).toContain(result);
      });
    });
  });
});

describe("GlobalVariableModal - Type Safety & onValueChange", () => {
  describe("Tab Type Definitions", () => {
    it("should define TAB_TYPES as union of 'Credential' and 'Generic'", () => {
      const credentialType: TAB_TYPES = "Credential";
      const genericType: TAB_TYPES = "Generic";

      expect(credentialType).toBe("Credential");
      expect(genericType).toBe("Generic");
    });
  });
});

describe("GlobalVariableModal - provider scope", () => {
  it("uses the same flow scope for palette, lookup, and upsert", () => {
    const providerScope = { flowId: "flow-project-a" };

    render(
      <GlobalVariableModal
        open
        setOpen={jest.fn()}
        providerScope={providerScope}
      />,
    );

    expect(mockUseGlobalVariableUpsert).toHaveBeenCalledWith(
      providerScope,
      mockGlobalVariablesData,
    );
    expect(mockUseGetGlobalVariables).toHaveBeenCalledWith(providerScope);
    expect(mockUseGetTypes).toHaveBeenCalledWith({
      ...providerScope,
      enabled: true,
    });
  });
});

describe("GlobalVariableModal - handleSaveVariable", () => {
  // A falsy id keeps submitForm on the create branch (handleSaveVariable) while
  // still prefilling key/value/type, so the save can be triggered with a single
  // click and no field interaction.
  const createSeed = {
    id: "",
    name: "MY_VAR",
    value: "secret",
    type: "Credential" as TAB_TYPES,
    default_fields: [] as string[],
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  function renderModal() {
    render(
      <GlobalVariableModal open setOpen={jest.fn()} initialData={createSeed} />,
    );
  }

  it("shows the created toast when the upsert reports action 'created'", async () => {
    mockUpsert.mockResolvedValue({ action: "created", name: "MY_VAR" });
    renderModal();

    fireEvent.click(screen.getByTestId("modal-submit"));

    await waitFor(() =>
      expect(mockSetSuccessData).toHaveBeenCalledWith({
        title: "globalVars.modal.successCreated",
      }),
    );
    expect(mockUpsert).toHaveBeenCalledWith({
      name: "MY_VAR",
      type: "Credential",
      value: "secret",
      default_fields: [],
    });
    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("shows the updated toast when the upsert reports action 'updated' (name collision)", async () => {
    mockUpsert.mockResolvedValue({ action: "updated", name: "MY_VAR" });
    renderModal();

    fireEvent.click(screen.getByTestId("modal-submit"));

    await waitFor(() =>
      expect(mockSetSuccessData).toHaveBeenCalledWith({
        title: "globalVars.modal.successUpdated",
      }),
    );
  });

  it("attributes a failed create to 'errorCreating' and surfaces the API detail", async () => {
    mockUpsert.mockRejectedValue({ response: { data: { detail: "boom" } } });
    renderModal();

    fireEvent.click(screen.getByTestId("modal-submit"));

    await waitFor(() =>
      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "globalVars.modal.errorCreating",
        list: ["boom"],
      }),
    );
    expect(mockSetSuccessData).not.toHaveBeenCalled();
  });

  it("attributes a failed name-collision update to 'errorUpdating' via the tagged action", async () => {
    mockUpsert.mockRejectedValue({
      action: "updated",
      response: { data: { detail: "forbidden" } },
    });
    renderModal();

    fireEvent.click(screen.getByTestId("modal-submit"));

    await waitFor(() =>
      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "globalVars.modal.errorUpdating",
        list: ["forbidden"],
      }),
    );
  });
});
