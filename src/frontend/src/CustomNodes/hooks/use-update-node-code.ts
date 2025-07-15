import { cloneDeep } from 'lodash';
import { useCallback } from 'react';
import useFlowStore from '@/stores/flowStore';
import type { APIClassType } from '../../types/api';

const useUpdateNodeCode = (
  dataId: string,
  dataNode: APIClassType,
  setNode: (id: string, callback: (oldNode) => any) => void,
  updateNodeInternals: (id: string) => void
) => {
  const { setComponentsToUpdate } = useFlowStore();

  const updateNodeCode = useCallback(
    (newNodeClass: APIClassType, code: string, name: string, type: string) => {
      setNode(dataId, oldNode => {
        const newNode = cloneDeep(oldNode);

        newNode.data = {
          ...newNode.data,
          node: { ...newNodeClass, edited: false },
          description: newNodeClass.description ?? dataNode.description,
          display_name: newNodeClass.display_name ?? dataNode.display_name,
        };
        if (type) {
          newNode.data.type = type;
        }

        newNode.data.node.template[name].value = code;

        newNode.data.node!.outputs = newNodeClass.outputs;

        return newNode;
      });

      setComponentsToUpdate(old =>
        old.filter(component => component.id !== dataId)
      );
      updateNodeInternals(dataId);
    },
    [dataId, dataNode, setNode, updateNodeInternals]
  );

  return updateNodeCode;
};

export default useUpdateNodeCode;
