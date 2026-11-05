import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useGetDatasetExamples } from "@/controllers/API/queries/evals/use-datasets";
import { useAddExampleDataset } from "../hooks/use-add-example-dataset";
import { EXAMPLE_ICONS } from "./DatasetExamples";

/** The examples again, from the toolbar, once the page already lists datasets. */
export default function ExamplesMenu() {
  const { t } = useTranslation();
  const { data: examples } = useGetDatasetExamples();
  const { add, pendingKey } = useAddExampleDataset();
  if (!examples?.length) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="flex items-center gap-2"
          loading={pendingKey !== null}
          data-testid="dataset-examples-menu"
        >
          <ForwardedIconComponent name="LayoutTemplate" className="h-4 w-4" />
          {t("evals.examples.menu")}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        {examples.map((example) => (
          <DropdownMenuItem
            key={example.key}
            onSelect={() => add(example.key)}
            className="flex items-start gap-2"
            data-testid={`dataset-example-menu-${example.key}`}
          >
            <ForwardedIconComponent
              name={EXAMPLE_ICONS[example.key] ?? "Table"}
              aria-hidden="true"
              className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
            />
            <span className="flex flex-col">
              <span className="text-sm">{example.name}</span>
              <span className="text-xs text-muted-foreground">
                {t("evals.examples.items", { count: example.item_count })}
              </span>
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
