import {
  focusCommandListOnOpen,
  refocusSelectedCommandItemOnNavigate,
} from "../focus-command-list-on-open";

// Builds a minimal cmdk-shaped DOM fragment: a container with [cmdk-list]
// containing [role="option"] items, matching what the real functions query
// for. Testing against a hand-built fixture rather than a mounted React
// component isolates this file's own logic precisely, independent of
// whether any particular consumer (ModelInputComponent,
// DBProviderInputComponent, ...) happens to wire it up correctly.
function buildList(
  options: Array<{ selected?: boolean; disabled?: boolean }>,
): { container: HTMLElement; list: HTMLElement; items: HTMLElement[] } {
  const container = document.createElement("div");
  const list = document.createElement("div");
  list.setAttribute("cmdk-list", "");
  container.appendChild(list);

  const items = options.map(({ selected, disabled }) => {
    const item = document.createElement("div");
    item.setAttribute("role", "option");
    item.setAttribute("aria-selected", selected ? "true" : "false");
    if (disabled) item.setAttribute("aria-disabled", "true");
    list.appendChild(item);
    return item;
  });

  document.body.appendChild(container);
  return { container, list, items };
}

describe("focusCommandListOnOpen", () => {
  const fireOpen = (content: HTMLElement) => {
    const preventDefault = jest.fn();
    focusCommandListOnOpen({
      currentTarget: content,
      preventDefault,
    } as unknown as Event);
    return preventDefault;
  };

  it("does nothing when the content has no [cmdk-list]", () => {
    const content = document.createElement("div");
    document.body.appendChild(content);

    expect(() => fireOpen(content)).not.toThrow();
  });

  it("focuses the aria-selected option and calls preventDefault", () => {
    const { container, items } = buildList([{}, { selected: true }, {}]);

    const preventDefault = fireOpen(container);

    expect(preventDefault).toHaveBeenCalled();
    expect(items[1]).toHaveFocus();
  });

  it("falls back to the first non-disabled option when nothing is selected", () => {
    const { container, items } = buildList([{}, {}, {}]);

    fireOpen(container);

    expect(items[0]).toHaveFocus();
  });

  it("skips a disabled option even when it is marked selected", () => {
    const { container, items } = buildList([
      { selected: true, disabled: true },
      {},
    ]);

    fireOpen(container);

    expect(items[1]).toHaveFocus();
  });

  it("still calls preventDefault when the list has no options at all", () => {
    const { container } = buildList([]);

    const preventDefault = fireOpen(container);

    expect(preventDefault).toHaveBeenCalled();
  });

  it("applies roving tabindex: only the focused option is tabindex=0", () => {
    const { container, items } = buildList([{}, { selected: true }, {}]);

    fireOpen(container);

    expect(items[0]).toHaveAttribute("tabindex", "-1");
    expect(items[1]).toHaveAttribute("tabindex", "0");
    expect(items[2]).toHaveAttribute("tabindex", "-1");
  });
});

describe("refocusSelectedCommandItemOnNavigate", () => {
  const fireKey = (root: HTMLElement, key: string) => {
    refocusSelectedCommandItemOnNavigate({
      key,
      currentTarget: root,
    } as unknown as React.KeyboardEvent<HTMLElement>);
  };

  // cmdk moves aria-selected synchronously in the same onKeyDown pass this
  // fires from, but the refocus itself is deferred a frame (see the file's
  // own comment on why) — wait one animation frame before asserting.
  const nextFrame = () =>
    new Promise((resolve) => requestAnimationFrame(resolve));

  it.each(["ArrowDown", "ArrowUp", "Home", "End"])(
    "refocuses the newly-selected option on %s",
    async (key) => {
      const { container, items } = buildList([{}, { selected: true }]);

      fireKey(container, key);
      await nextFrame();

      expect(items[1]).toHaveFocus();
    },
  );

  it("does nothing for a non-navigation key", async () => {
    const { container, items } = buildList([{ selected: true }]);
    // A plain <div role="option"> with no tabindex isn't actually
    // focusable — .focus() on it is a silent no-op, same as in a real
    // browser. Give it a tabindex first so "focus is untouched" is a
    // meaningful assertion instead of trivially true either way.
    items[0].setAttribute("tabindex", "0");
    items[0].focus();

    fireKey(container, "a");
    await nextFrame();

    // Focus should be untouched — still on items[0], since nothing was
    // ever refocused via the function under test.
    expect(items[0]).toHaveFocus();
  });

  // Regression guard: cmdk also responds to Ctrl+N/Ctrl+J and Ctrl+P/Ctrl+K
  // as vim/emacs-style alternatives to the arrow keys, but this function
  // deliberately no longer mirrors those — only the plain arrow/Home/End
  // keys refocus. Locks in that narrower scope was an intentional choice,
  // not a gap that crept in unnoticed.
  it.each(["n", "j", "p", "k"])(
    "does not refocus on the vim/emacs alternative key %s",
    async (key) => {
      const { container, items } = buildList([{ selected: true }]);
      items[0].setAttribute("tabindex", "0");
      items[0].focus();

      fireKey(container, key);
      await nextFrame();

      expect(items[0]).toHaveFocus();
    },
  );

  it("does nothing when there is no [cmdk-list] under currentTarget", async () => {
    const root = document.createElement("div");
    document.body.appendChild(root);

    expect(() => fireKey(root, "ArrowDown")).not.toThrow();
    await nextFrame();
  });
});
