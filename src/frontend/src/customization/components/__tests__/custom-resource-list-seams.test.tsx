import { render, renderHook } from "@testing-library/react";
import CustomResourceAccessLabel from "@/customization/components/custom-resource-access-label";
import { useCustomResourceListFilter } from "@/customization/hooks/use-custom-resource-list-filter";

describe("OSS resource list seams", () => {
  it("should_return_the_same_items_and_no_tools_when_the_filter_is_the_default", () => {
    const items = Array.from({ length: 25 }, (_, index) => ({
      id: `item-${index}`,
    }));
    const isOwned = jest.fn(() => false);

    const { result } = renderHook(() =>
      useCustomResourceListFilter("flow", items, isOwned),
    );

    expect(result.current.items).toBe(items);
    expect(result.current.tools).toBeNull();
    // OSS never judges ownership, so nothing can be hidden.
    expect(isOwned).not.toHaveBeenCalled();
  });

  it("should_return_an_empty_list_when_given_an_empty_list", () => {
    const { result } = renderHook(() =>
      useCustomResourceListFilter("file", [], () => true),
    );

    expect(result.current.items).toEqual([]);
    expect(result.current.tools).toBeNull();
  });

  it.each([true, false])(
    "should_render_nothing_when_the_label_is_the_default_and_isOwned_is_%s",
    (isOwned) => {
      const { container } = render(
        <CustomResourceAccessLabel
          resourceType="knowledge_base"
          resourceId="kb-1"
          isOwned={isOwned}
        />,
      );

      expect(container).toBeEmptyDOMElement();
    },
  );

  it("should_render_the_fallback_unchanged_when_the_label_is_the_default", () => {
    const { container } = render(
      <CustomResourceAccessLabel
        resourceType="variable"
        resourceId="v-1"
        isOwned={false}
        fallback={<span data-testid="pill">Shared</span>}
      />,
    );

    expect(container.innerHTML).toBe('<span data-testid="pill">Shared</span>');
  });
});
