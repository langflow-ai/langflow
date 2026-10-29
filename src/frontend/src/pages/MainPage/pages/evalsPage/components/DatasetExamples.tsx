import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useGetDatasetExamples } from "@/controllers/API/queries/evals/use-datasets";
import { cn } from "@/utils/utils";
import { useAddExampleDataset } from "../hooks/use-add-example-dataset";

export const EXAMPLE_ICONS: Record<string, string> = {
  "support-triage": "Tags",
  "grounded-answers": "BookOpenCheck",
  "safety-checks": "ShieldCheck",
};

/** One card per ready-made dataset, for the empty Datasets page. */
export default function DatasetExamples() {
  const { t } = useTranslation();
  const { data: examples } = useGetDatasetExamples();
  const { add, pendingKey } = useAddExampleDataset();
  if (!examples?.length) return null;

  return (
    <section
      aria-labelledby="dataset-examples-title"
      className="flex w-full max-w-3xl flex-col gap-3"
    >
      <h2
        id="dataset-examples-title"
        className="text-center text-sm font-medium text-muted-foreground"
      >
        {t("evals.examples.title")}
      </h2>
      <ul className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {examples.map((example) => {
          const pending = pendingKey === example.key;
          return (
            <li key={example.key} className="flex">
              <button
                type="button"
                aria-busy={pending}
                disabled={pendingKey !== null}
                onClick={() => add(example.key)}
                data-testid={`dataset-example-${example.key}`}
                className={cn(
                  "flex w-full flex-col gap-2 rounded-lg border px-4 py-3 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed",
                  pendingKey !== null && !pending && "opacity-60",
                )}
              >
                <span className="flex items-center gap-2 text-sm font-medium">
                  <ForwardedIconComponent
                    name={
                      pending
                        ? "Loader2"
                        : (EXAMPLE_ICONS[example.key] ?? "Table")
                    }
                    aria-hidden="true"
                    className={cn(
                      "h-4 w-4 shrink-0 text-muted-foreground",
                      pending && "animate-spin motion-reduce:animate-none",
                    )}
                  />
                  {example.name}
                </span>
                <span className="line-clamp-3 text-xs text-muted-foreground">
                  {example.description}
                </span>
                <span className="mt-auto text-xs text-muted-foreground">
                  {t("evals.examples.items", { count: example.item_count })}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
