import { Button } from "../../../../components/ui/button";
import BaseModal from "../../../../modals/baseModal";
import SwitchOutputView from "./components/switchOutputView";

export default function OutputModal({ open, setOpen, nodeId }): JSX.Element {
  return (
    <BaseModal open={open} setOpen={setOpen} size="medium-tall">
      <BaseModal.Header description="Inspect the output of the component below.">
        <div className="flex items-center">
          <span className="pr-2">Component Output</span>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <SwitchOutputView nodeId={nodeId} />
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full justify-end  pt-2">
          <Button className="flex gap-2 px-3" onClick={() => setOpen(false)}>
            Close
          </Button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
