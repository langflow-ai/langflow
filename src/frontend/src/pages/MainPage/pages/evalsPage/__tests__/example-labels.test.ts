import type { DatasetExample } from "@/controllers/API/queries/evals/types";
import { exampleLabels } from "../utils/example-labels";

const EXAMPLE: DatasetExample = {
  key: "support-triage",
  name: "Support ticket triage",
  description: "Classify each message.",
  item_count: 12,
};

describe("exampleLabels", () => {
  it("should_use_the_translation_for_a_known_example", () => {
    const t = (key: string) =>
      ({
        "evals.examples.support-triage.name": "Triagem de chamados",
        "evals.examples.support-triage.description": "Classifique.",
      })[key] ?? key;

    expect(exampleLabels(t, EXAMPLE)).toEqual({
      name: "Triagem de chamados",
      description: "Classifique.",
    });
  });

  it("should_keep_the_server_text_for_an_example_without_a_translation", () => {
    const t = (_key: string, options?: Record<string, unknown>) =>
      String(options?.defaultValue ?? "");

    expect(exampleLabels(t, { ...EXAMPLE, key: "new-example" })).toEqual({
      name: "Support ticket triage",
      description: "Classify each message.",
    });
  });
});
