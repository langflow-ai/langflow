import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useFolderStore } from "@/stores/foldersStore";
import { useUtilityStore } from "@/stores/utilityStore";

type EmptyFolderProps = {
  setOpenModal: (open: boolean) => void;
  /** Preferred handler — bypasses the templates modal and starts a fresh
   *  flow with the welcome overlay primed. Falls back to ``setOpenModal``
   *  when omitted to keep legacy callers working. */
  onNewFlow?: () => void;
};

export const EmptyFolder = ({ setOpenModal, onNewFlow }: EmptyFolderProps) => {
  const { t } = useTranslation();
  const folders = useFolderStore((state) => state.folders);
  const hideNewFlowButton = useUtilityStore((state) => state.hideNewFlowButton);

  return (
    <div className="m-0 flex w-full justify-center">
      <div className="absolute top-1/2 flex w-full -translate-y-1/2 flex-col items-center justify-center gap-2">
        <h3
          className="pt-5 font-chivo text-2xl font-semibold"
          data-testid="mainpage_title"
        >
          {folders?.length > 1
            ? t("emptyPage.emptyProject")
            : t("emptyPage.startBuilding")}
        </h3>
        <p className="pb-5 text-sm text-secondary-foreground">
          {t("emptyPage.description")}
        </p>
        {!hideNewFlowButton && (
          <Button
            variant="default"
            onClick={() => (onNewFlow ? onNewFlow() : setOpenModal(true))}
            id="new-project-btn"
            data-testid="new_project_btn_empty_page"
          >
            <ForwardedIconComponent
              name="plus"
              aria-hidden="true"
              className="h-4 w-4"
            />
            <span className="whitespace-nowrap font-semibold">
              {t("emptyPage.newFlow")}
            </span>
          </Button>
        )}
      </div>
    </div>
  );
};

export default EmptyFolder;
