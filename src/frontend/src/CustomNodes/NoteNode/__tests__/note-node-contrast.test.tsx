/**
 * Regression test for IBM Equal Access `text_contrast_sufficient` violation:
 * preset-colored note backgrounds (amber/rose/lime/blue/neutral) previously fell
 * back to `text-muted-foreground` in light mode with no override, which fails
 * WCAG AA contrast against light pastel backgrounds (e.g. 3.98:1 on amber vs the
 * 4.5:1 required). The fix adds a `text-foreground` override for presets in light
 * mode, alongside the pre-existing `dark:` overrides.
 */
import { render } from "@testing-library/react";
import { COLOR_OPTIONS } from "@/constants/constants";
import type { NoteDataType } from "@/types/flow";
import NoteNode from "../index";

jest.mock("@xyflow/react", () => ({
  NodeResizer: () => null,
}));

jest.mock("@/contexts/permissionsContext", () => ({
  useIsFlowReadOnly: () => false,
}));

jest.mock("@/controllers/API/queries/flows/use-get-note-translations", () => ({
  useGetNoteTranslationsQuery: () => ({ data: undefined }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      currentFlow: { id: "flow-1", data: { nodes: [] } },
      setNode: jest.fn(),
    }),
  syncNoteTranslations: jest.fn(),
}));

jest.mock("../NoteToolbarComponent", () => ({
  __esModule: true,
  default: () => null,
}));

let lastNodeDescriptionProps: Record<string, unknown> = {};
jest.mock("../../GenericNode/components/NodeDescription", () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => {
    lastNodeDescriptionProps = props;
    return null;
  },
}));

describe("NoteNode text contrast on preset backgrounds", () => {
  beforeEach(() => {
    lastNodeDescriptionProps = {};
  });

  Object.keys(COLOR_OPTIONS)
    .filter((color) => COLOR_OPTIONS[color] !== null)
    .forEach((color) => {
      it(`applies a light-mode text-foreground override for the "${color}" preset`, () => {
        const data = {
          id: "note-1",
          node: {
            description: "Some note text",
            template: { backgroundColor: color },
          },
        } as unknown as NoteDataType;

        render(<NoteNode data={data} />);

        expect(lastNodeDescriptionProps.inputClassName).toContain(
          "text-foreground",
        );
        expect(lastNodeDescriptionProps.mdClassName).toContain(
          "text-foreground",
        );
        // Dark-mode override must be preserved alongside the new light-mode fix.
        expect(lastNodeDescriptionProps.inputClassName).toContain(
          "dark:text-background",
        );
        expect(lastNodeDescriptionProps.mdClassName).toContain(
          "dark:!text-background",
        );
      });
    });

  it("leaves the transparent/no-background preset without a forced text color", () => {
    const data = {
      id: "note-1",
      node: {
        description: "Some note text",
        template: { backgroundColor: "transparent" },
      },
    } as unknown as NoteDataType;

    render(<NoteNode data={data} />);

    expect(lastNodeDescriptionProps.inputClassName).not.toContain(
      "text-foreground",
    );
  });
});
