import {
  buildToolbarActionMap,
  type ToolbarActionEvent,
  type ToolbarActionHandlers,
} from "../build-toolbar-action-map";

// Every case that existed in the original handleSelectChange switch.
const ORIGINAL_SWITCH_CASES: ToolbarActionEvent[] = [
  "save",
  "freezeAll",
  "code",
  "show",
  "Share",
  "Download",
  "SaveAll",
  "documentation",
  "disabled",
  "ungroup",
  "override",
  "delete",
  "update",
  "copy",
  "duplicate",
  "toolMode",
];

function makeHandlers(): jest.Mocked<ToolbarActionHandlers> {
  return {
    save: jest.fn(),
    freezeAll: jest.fn(),
    code: jest.fn(),
    show: jest.fn(),
    share: jest.fn(),
    download: jest.fn(),
    saveAll: jest.fn(),
    documentation: jest.fn(),
    ungroup: jest.fn(),
    override: jest.fn(),
    delete: jest.fn(),
    update: jest.fn(),
    copy: jest.fn(),
    duplicate: jest.fn(),
    toolMode: jest.fn(),
  };
}

describe("buildToolbarActionMap", () => {
  it("covers every case of the original switch, no more, no less", () => {
    const map = buildToolbarActionMap(makeHandlers());
    expect(Object.keys(map).sort()).toEqual([...ORIGINAL_SWITCH_CASES].sort());
  });

  it("routes each event to its handler", () => {
    const h = makeHandlers();
    const map = buildToolbarActionMap(h);

    const routing: Array<[ToolbarActionEvent, keyof ToolbarActionHandlers]> = [
      ["save", "save"],
      ["freezeAll", "freezeAll"],
      ["code", "code"],
      ["show", "show"],
      ["Share", "share"],
      ["Download", "download"],
      ["SaveAll", "saveAll"],
      ["documentation", "documentation"],
      ["ungroup", "ungroup"],
      ["override", "override"],
      ["delete", "delete"],
      ["update", "update"],
      ["copy", "copy"],
      ["duplicate", "duplicate"],
      ["toolMode", "toolMode"],
    ];

    for (const [event, handler] of routing) {
      map[event]();
      expect(h[handler]).toHaveBeenCalledTimes(1);
    }
  });

  it("treats 'disabled' as a no-op that touches no handler", () => {
    const h = makeHandlers();
    const map = buildToolbarActionMap(h);
    expect(() => map.disabled()).not.toThrow();
    for (const fn of Object.values(h)) {
      expect(fn).not.toHaveBeenCalled();
    }
  });
});
