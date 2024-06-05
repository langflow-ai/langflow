import { cloneDeep } from "lodash";
import { forwardRef, useEffect, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import { Badge } from "../../components/ui/badge";
import {
  LANGFLOW_SUPPORTED_TYPES,
  limitScrollFieldsModal,
} from "../../constants/constants";
import useFlowStore from "../../stores/flowStore";
import { NodeDataType } from "../../types/flow";
import { classNames } from "../../utils/utils";
import BaseModal from "../baseModal";
import TableComponent from "../../components/tableComponent";
import TableAutoCellRender from "../../components/tableAutoCellRender";
import { TemplateVariableType } from "../../types/api";
import TableNodeCellRender from "../../components/tableNodeCellRender";
import { ValueGetterParams } from "ag-grid-community";

const EditNodeModal = forwardRef(
  (
    {
      nodeLength,
      open,
      setOpen,
      data,
    }: {
      nodeLength: number;
      open: boolean;
      setOpen: (open: boolean) => void;
      data: NodeDataType;
    },
    ref,
  ) => {
    const nodes = useFlowStore((state) => state.nodes);

    const dataFromStore = nodes.find((node) => node.id === node.id)?.data;

    const [myData, setMyData] = useState(dataFromStore ?? data);

    const setNode = useFlowStore((state) => state.setNode);

    function changeAdvanced(n) {
      setMyData((old) => {
        let newData = cloneDeep(old);
        newData.node!.template[n].advanced =
          !newData.node!.template[n].advanced;
        return newData;
      });
    }

    const handleOnNewValue = (newValue: any, name) => {
      setMyData((old) => {
        let newData = cloneDeep(old);
        newData.node!.template[name].value = newValue;
        return newData;
      });
    };

    useEffect(() => {
      if (open) {
        setMyData(data); // reset data to what it is on node when opening modal
      }
    }, [open]);

    const rowData = Object.keys(myData.node!.template)
      .filter((key: string) => {
        const templateParam = myData.node!.template[
          key
        ] as TemplateVariableType;
        return (
          key.charAt(0) !== "_" &&
          templateParam.show &&
          LANGFLOW_SUPPORTED_TYPES.has(templateParam.type) &&
          !(
            (key === "code" && templateParam.type === "code") ||
            (key.includes("code") && templateParam.proxy)
          )
        );
      })
      .map((key: string) => {
        const templateParam = myData.node!.template[
          key
        ] as TemplateVariableType;
        return {
          ...templateParam,
          key: key,
        };
      });

    const columnDefs = [
      {
        headerName: "Name",
        field: "display_name",
        valueGetter: (params) => {
          const templateParam = params.data;
          return (
            (templateParam.display_name
              ? templateParam.display_name
              : templateParam.name) ?? params.data.key
          );
        },
        cellRenderer: TableAutoCellRender,
        flex: 1,
        resizable: false,
      },
      {
        headerName: "Description",
        field: "info",
        cellRenderer: TableAutoCellRender,
        flex: 2,
        resizable: false,
      },
      {
        headerName: "Value",
        field: "value",
        cellRenderer: TableNodeCellRender,
        valueGetter: (params: ValueGetterParams) => {
          console.log("params", params);
          return {
            value: params.data.value,
            nodeClass: myData.node,
            handleOnNewValue: handleOnNewValue,
            handleOnChangeDb: (value, key) => {
              setMyData((oldData) => {
                let newData = cloneDeep(oldData);
                newData.node!.template[key].load_from_db = value;
                return newData;
              });
            },
          };
        },
        minWidth: 300,
        flex: 1,
        resizable: false,
      },
      {
        headerName: "Show",
        field: "advanced",
        cellRenderer: "agCheckboxCellRenderer",
        cellEditor: "agCheckboxCellEditor",
        valueGetter: (params) => {
          return !params.data.advanced;
        },
        valueSetter: (params) => {
          changeAdvanced(params.data.key);
          return true;
        },
        editable: true,
        flex: 1,
        maxWidth: 70,
        resizable: false,
      },
    ];

    return (
      <BaseModal
        key={data.id}
        size="large-h-full"
        open={open}
        setOpen={setOpen}
        onChangeOpenModal={(open) => {
          setMyData(data);
        }}
        onSubmit={() => {
          setNode(data.id, (old) => ({
            ...old,
            data: {
              ...old.data,
              node: myData.node,
            },
          }));
          setOpen(false);
        }}
      >
        <BaseModal.Trigger>
          <></>
        </BaseModal.Trigger>
        <BaseModal.Header description={myData.node?.description!}>
          <span className="pr-2">{myData.type}</span>
          <Badge variant="secondary">ID: {myData.id}</Badge>
        </BaseModal.Header>
        <BaseModal.Content>
          <div className="flex pb-2">
            <IconComponent
              name="Variable"
              className="edit-node-modal-variable "
            />
            <span className="edit-node-modal-span">Parameters</span>
          </div>

          <div className="w-full">
            {nodeLength > 0 && (
              <div className="edit-node-modal-table">
                <div className="h-96">
                  <TableComponent columnDefs={columnDefs} rowData={rowData} />
                </div>
              </div>
            )}
          </div>
        </BaseModal.Content>

        <BaseModal.Footer submit={{ label: "Save Changes" }} />
      </BaseModal>
    );
  },
);

export default EditNodeModal;
