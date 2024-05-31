import { Button } from "../../../../components/ui/button";
import BaseModal from "../../../../modals/baseModal";
import SwitchOutputView from "./components/switchOutputView";

export default function OutputModal({ open, setOpen, nodeId }): JSX.Element {
  return (
    <BaseModal open={open} setOpen={setOpen} size="medium">
      <BaseModal.Header description="DESCRICAO RODRIGO">
        <div className="flex items-center">
          <span className="pr-2">TITULO RODRIGO</span>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <SwitchOutputView nodeId={nodeId} />
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full justify-end  pt-2">
          <Button className="flex gap-2 px-3" onClick={() => setOpen(false)}>
            Ok
          </Button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
