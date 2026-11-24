import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import type {
  ExtensionErrorPayload,
  ReloadBundleResponse,
} from "@/controllers/API/queries/extensions";

// Mocks --------------------------------------------------------------------

// The feature flag gates the entire component; flip it on for these tests
// so we exercise the rendered UI rather than the early-return branch.
jest.mock("@/customization/feature-flags", () => ({
  ENABLE_EXTENSION_RELOAD: true,
}));

const setSuccessData = jest.fn();
const setErrorData = jest.fn();
const setNoticeData = jest.fn();

interface AlertStoreSlice {
  setSuccessData: typeof setSuccessData;
  setErrorData: typeof setErrorData;
  setNoticeData: typeof setNoticeData;
}

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: AlertStoreSlice) => unknown) =>
    selector({ setSuccessData, setErrorData, setNoticeData }),
}));

// The runtime gate (mirrored from /config) must be on for the rendered-UI
// tests; the off-path is exercised separately below.
interface UtilitySlice {
  enableExtensionReload: boolean;
}
let runtimeReloadEnabled = true;
jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (selector: (state: UtilitySlice) => unknown) =>
    selector({ enableExtensionReload: runtimeReloadEnabled }),
}));

// The reload-success path clears the cached types snapshot and invalidates
// the ``useGetTypes`` React Query entry so the palette re-fetches templates
// without a hard refresh.  Capture both calls so the wiring is verifiable.
const setTypes = jest.fn();
interface TypesStoreSlice {
  setTypes: typeof setTypes;
}
jest.mock("@/stores/typesStore", () => ({
  useTypesStore: (selector: (state: TypesStoreSlice) => unknown) =>
    selector({ setTypes }),
}));

const invalidateQueries = jest.fn();
jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries }),
}));

// Captured between tests so we can poke the latest onSuccess / onError
// directly without round-tripping through MSW.
type ReloadVars = { extensionId: string; bundleName: string };
type ReloadOpts = {
  onSuccess?: (data: ReloadBundleResponse) => void;
  onError?: (error: Error) => void;
};
const mutateMock = jest.fn();
let lastOptions: ReloadOpts = {};
let pending = false;

jest.mock("@/controllers/API/queries/extensions", () => ({
  useReloadBundle: (options?: ReloadOpts) => {
    lastOptions = options ?? {};
    return { mutate: mutateMock, isPending: pending };
  },
}));

interface IconProps {
  name: string;
  className?: string;
}
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: IconProps) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

// Make `t(key, { defaultValue })` actually return the defaultValue with
// interpolation so the toast-content assertions can match human text.
interface TranslateOpts {
  defaultValue?: string;
  [key: string]: string | number | undefined;
}
jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: TranslateOpts) => {
      if (!opts || typeof opts !== "object") return key;
      const value: string = opts.defaultValue ?? key;
      return Object.keys(opts).reduce((acc, k) => {
        if (k === "defaultValue") return acc;
        const replacement = opts[k];
        if (replacement === undefined) return acc;
        return acc.replace(
          new RegExp(`\\{\\{${k}\\}\\}`, "g"),
          String(replacement),
        );
      }, value);
    },
  }),
}));

// DropdownMenu is the action-menu primitive; the underlying behavior we
// care about is "clicking the Reload item invokes the item's onSelect
// callback".  Stub the primitive with plain elements so the click flow is
// trivially testable without spinning up the full Radix portal.
interface PassthroughProps {
  children: React.ReactNode;
  [key: string]: unknown;
}
interface DropdownMenuItemMockProps extends PassthroughProps {
  onSelect?: () => void;
  disabled?: boolean;
  onClick?: (e: React.MouseEvent) => void;
}
jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: PassthroughProps) => (
    <div data-testid="dropdown">{children}</div>
  ),
  DropdownMenuTrigger: ({ children, ...rest }: PassthroughProps) => (
    <button type="button" {...rest}>
      {children}
    </button>
  ),
  DropdownMenuContent: ({ children, ...rest }: PassthroughProps) => (
    <div data-testid="dropdown-content" {...rest}>
      {children}
    </div>
  ),
  DropdownMenuItem: ({
    children,
    onSelect,
    disabled,
    onClick,
    ...rest
  }: DropdownMenuItemMockProps) => (
    <button
      type="button"
      onClick={(e) => {
        onClick?.(e);
        if (!disabled) onSelect?.();
      }}
      disabled={disabled}
      {...rest}
    >
      {children}
    </button>
  ),
}));

// Imported AFTER the mocks above so its module-level imports pick up the
// mocked versions.
// eslint-disable-next-line import/first
import BundleHeaderActions from "../bundleHeaderActions";

// Tests --------------------------------------------------------------------

const baseProps = {
  bundleName: "openai",
  extensionId: "lfx-openai",
  displayName: "OpenAI",
};

function makeResponse(
  overrides: Partial<ReloadBundleResponse> = {},
): ReloadBundleResponse {
  return {
    ok: true,
    bundle: "openai",
    reload_id: "abc",
    components_added: [],
    components_removed: [],
    components_changed: [],
    errors: [],
    warnings: [],
    ...overrides,
  };
}

function makeTypedError(
  overrides: Partial<ExtensionErrorPayload> = {},
): ExtensionErrorPayload {
  return {
    code: "module-import-failed",
    message: "ImportError: missing X",
    hint: "Add X to your requirements.",
    location: null,
    content: null,
    ref_url: null,
    ...overrides,
  };
}

describe("BundleHeaderActions", () => {
  beforeEach(() => {
    mutateMock.mockReset();
    setSuccessData.mockReset();
    setErrorData.mockReset();
    setNoticeData.mockReset();
    setTypes.mockReset();
    invalidateQueries.mockReset();
    lastOptions = {};
    pending = false;
    runtimeReloadEnabled = true;
  });

  it("renders nothing when the runtime backend flag is off", () => {
    runtimeReloadEnabled = false;
    const { container } = render(<BundleHeaderActions {...baseProps} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when extensionId is missing", () => {
    const { container } = render(
      <BundleHeaderActions {...baseProps} extensionId={undefined} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("calls reloadBundle with the registry coordinates on click", () => {
    render(<BundleHeaderActions {...baseProps} />);
    fireEvent.click(screen.getByTestId("bundle-header-reload-openai"));
    expect(mutateMock).toHaveBeenCalledTimes(1);
    expect(mutateMock).toHaveBeenCalledWith({
      extensionId: "lfx-openai",
      bundleName: "openai",
    } satisfies ReloadVars);
  });

  it("shows the loading icon while a reload is pending", () => {
    pending = true;
    render(<BundleHeaderActions {...baseProps} />);
    expect(screen.getByTestId("icon-Loader2")).toBeInTheDocument();
  });

  it("emits a success toast with the components delta on ok=true", () => {
    render(<BundleHeaderActions {...baseProps} />);
    lastOptions.onSuccess?.(
      makeResponse({ components_added: ["FooComponent"] }),
    );
    expect(setSuccessData).toHaveBeenCalledTimes(1);
    expect(setSuccessData.mock.calls[0][0].title).toContain("OpenAI");
    expect(setSuccessData.mock.calls[0][0].title).toContain("+1");
  });

  it("counts components_changed when class names are unchanged but bodies edited", () => {
    render(<BundleHeaderActions {...baseProps} />);
    lastOptions.onSuccess?.(
      makeResponse({ components_changed: ["HelloComponent"] }),
    );
    expect(setSuccessData).toHaveBeenCalledTimes(1);
    const title = setSuccessData.mock.calls[0][0].title;
    expect(title).toContain("OpenAI");
    expect(title).toContain("~1");
    expect(title).not.toMatch(/no.*changes/i);
  });

  it("invalidates the types query and clears the store on successful reload", () => {
    render(<BundleHeaderActions {...baseProps} />);
    lastOptions.onSuccess?.(makeResponse());
    expect(setTypes).toHaveBeenCalledWith({});
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetTypes"],
    });
  });

  it("does not invalidate types on a structural failure (ok=false)", () => {
    render(<BundleHeaderActions {...baseProps} />);
    lastOptions.onSuccess?.(
      makeResponse({ ok: false, errors: [makeTypedError()] }),
    );
    expect(setTypes).not.toHaveBeenCalled();
    expect(invalidateQueries).not.toHaveBeenCalled();
  });

  it("emits an error toast with typed-error hints on ok=false", () => {
    render(<BundleHeaderActions {...baseProps} />);
    lastOptions.onSuccess?.(
      makeResponse({ ok: false, errors: [makeTypedError()] }),
    );
    expect(setErrorData).toHaveBeenCalledTimes(1);
    const call = setErrorData.mock.calls[0][0];
    expect(call.title).toContain("OpenAI");
    expect(call.list).toEqual(
      expect.arrayContaining([
        expect.stringContaining("[module-import-failed]"),
        expect.stringContaining("Add X to your requirements."),
      ]),
    );
  });

  it("treats reload-in-progress as a notice, not an error", () => {
    render(<BundleHeaderActions {...baseProps} />);
    lastOptions.onError?.(new Error("reload-in-progress: already running"));
    expect(setNoticeData).toHaveBeenCalledTimes(1);
    expect(setErrorData).not.toHaveBeenCalled();
  });

  it("surfaces transport errors with the underlying message", () => {
    render(<BundleHeaderActions {...baseProps} />);
    lastOptions.onError?.(new Error("Network down"));
    expect(setErrorData).toHaveBeenCalledTimes(1);
    expect(setErrorData.mock.calls[0][0].list).toEqual(["Network down"]);
  });
});
