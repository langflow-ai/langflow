import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import GlobalVariableModal from "@/components/core/GlobalVariableModal/GlobalVariableModal";
import { CommandItem } from "@/components/ui/command";
import { cn } from "@/utils/utils";

const GeneralGlobalVariableModal = () => {
  const { t } = useTranslation();
  return (
    <>
      <GlobalVariableModal disabled={false}>
        <CommandItem value="doNotFilter-addNewVariable">
          <ForwardedIconComponent
            name="Plus"
            className={cn("mr-2 h-4 w-4 text-primary")}
            aria-hidden="true"
          />
          <span>{t("input.addNewVariable")}</span>
        </CommandItem>
      </GlobalVariableModal>
    </>
  );
};

export default GeneralGlobalVariableModal;
