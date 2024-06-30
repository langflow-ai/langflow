import { cn } from "../../../../utils/utils";
import { useTranslation } from "react-i18next";

export default function ResetColumns({
  resetGrid,
}: {
  resetGrid: () => void;
}): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className={cn("absolute bottom-4 left-6")}>
      <span
        className="cursor-pointer underline"
        onClick={() => {
          resetGrid();
        }}
      >
        {t("Reset Columns")}
      </span>
    </div>
  );
}
