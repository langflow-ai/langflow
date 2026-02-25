import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useFolderStore } from "@/stores/foldersStore";

type EmptyFolderProps = {
  setOpenModal: (open: boolean) => void;
};

export const EmptyFolder = ({ setOpenModal }: EmptyFolderProps) => {
  const folders = useFolderStore((state) => state.folders);
  const { t } = useTranslation();

  return (
    <div className="m-0 flex w-full justify-center">
      <div className="absolute top-1/2 flex w-full -translate-y-1/2 flex-col items-center justify-center gap-2">
        <h3
          className="pt-5 font-chivo text-2xl font-semibold"
          data-testid="mainpage_title"
        >
          {folders?.length > 1
            ? t("main.emptyProject", "空项目")
            : t("main.startBuilding", "开始构建")}
        </h3>
        <p className="pb-5 text-sm text-secondary-foreground">
          {t("main.startBuildingDesc", "从模板开始，或从头创建。")}
        </p>
        <Button
          variant="default"
          onClick={() => setOpenModal(true)}
          id="new-project-btn"
          data-testid="new_project_btn_empty_page"
        >
          <ForwardedIconComponent
            name="plus"
            aria-hidden="true"
            className="h-4 w-4"
          />
          <span className="whitespace-nowrap font-semibold">
            {t("flow.newFlow")}
          </span>
        </Button>
      </div>
    </div>
  );
};

export default EmptyFolder;
