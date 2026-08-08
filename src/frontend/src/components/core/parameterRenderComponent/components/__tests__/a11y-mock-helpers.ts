/**
 * Shared jest.mock() factories for the widget-level a11y regression tests
 * under components/*\/__tests__/*.a11y.test.tsx — the app-wide dependencies
 * (icon component, store selectors, usePostTemplateValue) every widget
 * needs just to render, previously copy-pasted per file.
 *
 * Jest only lets a jest.mock() factory reference an out-of-scope identifier
 * if its name starts with "mock" (case-insensitive), hence the naming here.
 * Always call these from inside an arrow at the use site — babel-plugin-
 * jest-hoist hoists jest.mock() above this module's own require(), so
 * passing the helper directly dereferences it before it's loaded:
 *
 *   jest.mock(path, () => mockGenericIconComponent());   // correct
 *   jest.mock(path, mockGenericIconComponent);           // breaks
 */

/** Icon component stub covering both export shapes callers use (`default` and `ForwardedIconComponent`). */
export const mockGenericIconComponent = () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: () => null,
});

/** Generic Zustand store mock: reproduces `useStore(selector)` / `useStore()` against a fixed state object. */
export const mockZustandStore = <T>(state: T) => ({
  __esModule: true,
  default: (selector?: (state: T) => unknown) =>
    selector ? selector(state) : state,
});

/** `usePostTemplateValue` stub for widgets that only need the hook to satisfy a prop contract. */
export const mockUsePostTemplateValue = () => ({
  usePostTemplateValue: () => jest.fn(),
});
