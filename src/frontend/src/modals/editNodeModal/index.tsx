import { APIClassType } from "@/types/api";
import { customStringify } from "@/utils/reactflowUtils";
import { useEffect, useState } from "react";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { useDarkStore } from "../../stores/darkStore";
import { NodeDataType } from "../../types/flow";
import BaseModal from "../baseModal";
import { EditNodeComponent } from "./components/editNodeComponent";

const EditNodeModal = ({
  open,
  setOpen,
  data,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
  data: NodeDataType;
}) => {
  const isDark = useDarkStore((state) => state.dark);

  const [nodeClass, setNodeClass] = useState<APIClassType>(data.node!);

  useEffect(() => {
    if (
      customStringify(Object.keys(data?.node?.template ?? {})) ===
      customStringify(Object.keys(nodeClass?.template ?? {}))
    )
      return;
    setNodeClass(data.node!);
  }, [data.node]);

  return (
    <BaseModal key={data.id} open={open} setOpen={setOpen} size="x-large">
      <BaseModal.Trigger>
        <></>
      </BaseModal.Trigger>
      <BaseModal.Header description={data.node?.description!}>
        <span data-testid="node-modal-title" className="pr-2">
          {data.node?.display_name ?? data.type}
        </span>
        <div>
          <Badge size="sm" variant={isDark ? "gray" : "secondary"}>
            ID: {data.id}
          </Badge>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <EditNodeComponent open={open} nodeClass={nodeClass} nodeId={data.id} />
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full justify-end gap-2 pt-2">
          <Button onClick={() => setOpen(false)}>Close</Button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
};

export default EditNodeModal;
