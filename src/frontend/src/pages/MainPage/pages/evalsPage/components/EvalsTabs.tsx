import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { CustomLink } from "@/customization/components/custom-link";
import { cn } from "@/utils/utils";

export type EvalsTab = "evaluations" | "datasets";

const TABS: { id: EvalsTab; to: string; icon: string; label: string }[] = [
  {
    id: "evaluations",
    to: "/assets/evaluations",
    icon: "FlaskConical",
    label: "evals.evaluations.title",
  },
  {
    id: "datasets",
    to: "/assets/datasets",
    icon: "Table",
    label: "evals.datasets.title",
  },
];

/** The Flows page tab row: each tab is its own address, so these are links, not a tablist. */
export default function EvalsTabs({ active }: { active: EvalsTab }) {
  const { t } = useTranslation();
  return (
    <nav aria-label={t("evals.tabs.label")} className="flex pb-4">
      {TABS.map((tab) => {
        const current = tab.id === active;
        return (
          <CustomLink
            key={tab.id}
            to={tab.to}
            aria-current={current ? "page" : undefined}
            data-testid={`evals-tab-${tab.id}`}
            className={cn(
              "flex items-center gap-1.5 text-nowrap border-b px-2 pb-2 pt-1 text-mmd focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              current
                ? "border-b-2 border-foreground text-foreground"
                : "border-border text-muted-foreground hover:text-foreground",
            )}
          >
            <ForwardedIconComponent
              name={tab.icon}
              aria-hidden="true"
              className={cn("h-3.5 w-3.5", current && "-mb-px")}
            />
            <span className={cn(current && "-mb-px")}>{t(tab.label)}</span>
          </CustomLink>
        );
      })}
      <div className="w-full border-b dark:border-border" />
    </nav>
  );
}
