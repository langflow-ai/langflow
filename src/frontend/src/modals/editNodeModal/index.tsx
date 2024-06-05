import { ColDef, ValueGetterParams } from "ag-grid-community";
import { forwardRef, useEffect, useRef } from "react";
import IconComponent from "../../components/genericIconComponent";
import TableAutoCellRender from "../../components/tableAutoCellRender";
import TableComponent from "../../components/tableComponent";
import TableNodeCellRender from "../../components/tableNodeCellRender";
import TableTooltipRender from "../../components/tableTooltipRender";
import ToggleShadComponent from "../../components/toggleShadComponent";
import { Badge } from "../../components/ui/badge";
import { LANGFLOW_SUPPORTED_TYPES } from "../../constants/constants";
import useFlowStore from "../../stores/flowStore";
import { TemplateVariableType } from "../../types/api";
import { NodeDataType } from "../../types/flow";
import BaseModal from "../baseModal";

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

    const myData = useRef(dataFromStore ?? data);

    const setNode = useFlowStore((state) => state.setNode);

    function changeAdvanced(n) {
      myData.current.node!.template[n].advanced =
        !myData.current.node!.template[n]?.advanced;
    }

    const handleOnNewValue = (newValue: any, name) => {
      myData.current.node!.template[name].value = newValue;
    };

    useEffect(() => {
      if (open) {
        myData.current = data;
      }
    }, [open]);

    const rowData = Object.keys(myData.current.node!.template)
      .filter((key: string) => {
        const templateParam = myData.current.node!.template[
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
        const templateParam = myData.current.node!.template[
          key
        ] as TemplateVariableType;
        return {
          ...templateParam,
          key: key,
          id: key,
        };
      });

    const columnDefs: ColDef[] = [
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
        cellClass: "no-border",
      },
      {
        headerName: "Description",
        field: "info",
        tooltipField: "info",
        tooltipComponent: TableTooltipRender,
        cellRenderer: TableAutoCellRender,
        autoHeight: true,
        flex: 2,
        resizable: false,
        cellClass: "no-border",
      },
      {
        headerName: "Value",
        field: "value",
        cellRenderer: TableNodeCellRender,
        valueGetter: (params: ValueGetterParams) => {
          return {
            value: params.data.value,
            nodeClass: myData.current.node,
            handleOnNewValue: handleOnNewValue,
            handleOnChangeDb: (value, key) => {
              myData.current.node!.template[key].load_from_db = value;
            },
          };
        },
        minWidth: 330,
        flex: 1,
        resizable: false,
        cellClass: "no-border",
      },
      {
        headerName: "Show",
        field: "advanced",
        cellRenderer: (params) => {
          const templateParam = params.data;
          return (
            <>
              <ToggleShadComponent
                id={"show" + templateParam?.name}
                enabled={!templateParam?.advanced}
                setEnabled={() => {
                  changeAdvanced(params.data.key);
                }}
                size="small"
                editNode={true}
              />
            </>
          );
        },
        editable: false,
        maxWidth: 80,
        resizable: false,
        cellClass: "no-border",
      },
    ];

    return (
      <BaseModal
        key={data.id}
        size="large-h-full"
        open={open}
        setOpen={setOpen}
        onChangeOpenModal={(open) => {
          myData.current = data;
        }}
        onSubmit={() => {
          setNode(data.id, (old) => ({
            ...old,
            data: {
              ...old.data,
              node: myData.current.node,
            },
          }));
          setOpen(false);
        }}
      >
        <BaseModal.Trigger>
          <></>
        </BaseModal.Trigger>
        <BaseModal.Header description={myData.current.node?.description!}>
          <span className="pr-2">{myData.current.type}</span>
          <Badge variant="secondary">ID: {myData.current.id}</Badge>
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
                  <TableComponent
                    tooltipShowMode="whenTruncated"
                    tooltipShowDelay={0.5}
                    columnDefs={columnDefs}
                    rowData={rowData}
                  />
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
