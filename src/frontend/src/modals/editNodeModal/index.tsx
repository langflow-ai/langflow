import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import { APIClassType } from "@/types/api";
import { useState } from "react";
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

  const { handleNodeClass: handleNodeClassHook } = useHandleNodeClass(data.id);

  const handleNodeClass = (newNodeClass: APIClassType, type?: string) => {
    handleNodeClassHook(newNodeClass, type);
    setNodeClass(newNodeClass);
  };

  return (
    <BaseModal key={data.id} open={open} setOpen={setOpen}>
      <BaseModal.Trigger>
        <></>
      </BaseModal.Trigger>
      <BaseModal.Header description={data.node?.description!}>
        <span className="pr-2">{data.node?.display_name ?? data.type}</span>
        <div>
          <Badge size="sm" variant={isDark ? "gray" : "secondary"}>
            ID: {data.id}
          </Badge>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <EditNodeComponent
          open={open}
          nodeClass={nodeClass}
          setNodeClass={handleNodeClass}
          nodeId={data.id}
        />
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
