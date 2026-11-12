import type { DatasetExample } from "@/controllers/API/queries/evals/types";

type TranslateFn = (key: string, options?: Record<string, unknown>) => string;

/** An example's name and description in the interface language; an unknown example keeps the server's text. */
export function exampleLabels(
  t: TranslateFn,
  example: DatasetExample,
): { name: string; description: string } {
  return {
    name: t(`evals.examples.${example.key}.name`, {
      defaultValue: example.name,
    }),
    description: t(`evals.examples.${example.key}.description`, {
      defaultValue: example.description,
    }),
  };
}
