import { Fragment } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import {
  type ReplacementComponent,
  useGetReplacementComponents,
} from "../../hooks/use-get-replacement-components";

export default function NodeLegacyComponent({
  legacy,
  replacement,
  setDismissAll,
  disabled = false,
}: {
  legacy?: boolean;
  replacement?: string[];
  setDismissAll: (value: boolean) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const setFilterComponent = useFlowStore((state) => state.setFilterComponent);
  const setFilterType = useFlowStore((state) => state.setFilterType);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);

  const handleFilterComponent = (component: string) => {
    setFilterComponent(component);
    setFilterType(undefined);
    setFilterEdge([]);
  };

  // Separators follow position among the resolved entries, so an unresolved
  // first reference does not leave a leading ", ".
  const foundComponents = useGetReplacementComponents(replacement).filter(
    (component): component is ReplacementComponent => Boolean(component),
  );

  return (
    <div
      className={cn(
        "flex flex-col w-full items-center gap-3 rounded-t-[0.69rem] border-b bg-muted p-2 px-4 py-2",
      )}
    >
      <div className="flex items-center gap-3 w-full">
        <div className="h-2.5 w-2.5 rounded-full bg-warning" />
        <div className="mb-px flex-1 truncate text-mmd font-medium">Legacy</div>

        <Button
          variant="ghost"
          size="icon"
          className="shrink-0 !text-mmd"
          onClick={(e) => {
            e.stopPropagation();
            setDismissAll(true);
          }}
          aria-label={t("node.dismissWarning")}
          data-testid="dismiss-warning-bar"
          disabled={disabled}
        >
          Dismiss
        </Button>
      </div>
      <div className="text-mmd text-muted-foreground w-full">
        {foundComponents.length > 0 ? (
          <span className="block items-center">
            Use{" "}
            {foundComponents.map((component, index) => (
              <Fragment key={component.filterKey}>
                {index > 0 && ", "}
                <Button
                  variant="link"
                  className=" !text-accent-pink-foreground !text-mmd !inline-block"
                  size={null}
                  onClick={() => handleFilterComponent(component.filterKey)}
                >
                  <span>{component.displayName}</span>
                </Button>
              </Fragment>
            ))}
            .
          </span>
        ) : (
          "No direct replacement."
        )}
      </div>
    </div>
  );
}
