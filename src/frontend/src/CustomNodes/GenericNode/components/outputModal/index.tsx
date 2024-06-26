import { Button } from "../../../../components/ui/button";
import BaseModal from "../../../../modals/baseModal";
import SwitchOutputView from "./components/switchOutputView";
import { useTranslation } from "react-i18next";

export default function OutputModal({
  open,
  setOpen,
  nodeId,
  outputName,
}): JSX.Element {
  const { t } = useTranslation();
  return (
    <BaseModal open={open} setOpen={setOpen} size="medium-tall">
      <BaseModal.Header description={t("Inspect the output of the component below.")}>
        <div className="flex items-center">
          <span className="pr-2">{t("Component Output")}</span>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <SwitchOutputView nodeId={nodeId} outputName={outputName} />
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full justify-end pt-2">
          <Button className="flex gap-2 px-3" onClick={() => setOpen(false)}>
            {t("Close")}
          </Button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
