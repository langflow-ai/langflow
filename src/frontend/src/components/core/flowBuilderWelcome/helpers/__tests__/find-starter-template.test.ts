import type { FlowType } from "@/types/flow";
import { findStarterTemplate } from "../find-starter-template";

function makeFlow(overrides: Partial<FlowType>): FlowType {
  return {
    id: overrides.id ?? "fid-" + Math.random().toString(36).slice(2),
    name: overrides.name ?? "Untitled",
    description: overrides.description ?? "",
    data: overrides.data ?? {
      nodes: [],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    },
    name_key: overrides.name_key ?? null,
    tags: overrides.tags ?? [],
  } as FlowType;
}

describe("findStarterTemplate", () => {
  it("should_return_the_example_when_name_key_matches", () => {
    const simple = makeFlow({ name: "Simple Agent", name_key: "simple_agent" });
    const rag = makeFlow({
      name: "Vector Store RAG",
      name_key: "vector_store_rag",
    });
    const examples = [simple, rag];

    expect(findStarterTemplate(examples, "simple_agent")).toBe(simple);
    expect(findStarterTemplate(examples, "vector_store_rag")).toBe(rag);
  });

  it("should_return_null_when_no_example_has_the_requested_name_key", () => {
    const examples = [makeFlow({ name_key: "basic_prompting" })];
    expect(findStarterTemplate(examples, "simple_agent")).toBeNull();
  });

  it("should_return_null_when_examples_list_is_empty", () => {
    expect(findStarterTemplate([], "simple_agent")).toBeNull();
  });

  it("should_ignore_examples_with_null_name_key", () => {
    // ``name_key`` is nullable; the helper must not throw on null entries —
    // it should just skip them in the search.
    const examples = [
      makeFlow({ name: "Generic", name_key: null }),
      makeFlow({ name: "Simple Agent", name_key: "simple_agent" }),
    ];
    const found = findStarterTemplate(examples, "simple_agent");
    expect(found?.name).toBe("Simple Agent");
  });
});
