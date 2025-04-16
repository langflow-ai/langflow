import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent, {
  TableComponentProps,
} from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Input } from "@/components/ui/input";
import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { TableOptionsTypeAPI } from "@/types/api";
import { parseString } from "@/utils/stringManipulation";
import { ColDef } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { cloneDeep } from "lodash";
import {
  ForwardedRef,
  forwardRef,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import BaseModal from "../baseModal";

interface ToolsModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  description: string;
  rows: {
    name: string;
    tags: string[];
    description: string;
    status: boolean;
  }[];
  handleOnNewValue: handleOnNewValueType;
  title: string;
  icon: string;
}

const ToolsModal = forwardRef<AgGridReact, ToolsModalProps>(
  (
    {
      description,
      rows,
      handleOnNewValue,
      title,
      icon,
      open,
      setOpen,
      ...props
    }: ToolsModalProps,
    ref: ForwardedRef<AgGridReact>,
  ) => {
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedRows, setSelectedRows] = useState<any[] | null>(null);
    const agGrid = useRef<AgGridReact>(null);
    const [data, setData] = useState<any[]>(cloneDeep(rows));

    const handleSetOpen = (newOpen: boolean) => {
      if (setOpen) {
        setOpen(newOpen);
      }
    };

    useEffect(() => {
      const initialData = cloneDeep(rows);
      setData(initialData);
      const filter = initialData.filter((row) => row.status === true);
      setSelectedRows(filter);
    }, [rows, open]);

    useEffect(() => {
      const initialData = cloneDeep(rows);
      const filter = initialData.filter((row) => row.status === true);
      if (agGrid.current) {
        agGrid.current?.api.forEachNode((node) => {
          if (filter.some((row) => row.name === node.data.name)) {
            node.setSelected(true);
          } else {
            node.setSelected(false);
          }
        });
      }
    }, [agGrid.current]);

    useEffect(() => {
      if (!open && selectedRows) {
        handleOnNewValue({
          value: data.map((row) =>
            selectedRows?.some((selected) => selected.name === row.name)
              ? { ...row, status: true }
              : { ...row, status: false },
          ),
        });
      }
    }, [open]);

    const columnDefs: ColDef[] = [
      {
        field: "name",
        headerName: "Name",
        flex: 1,
        valueGetter: (params) => params.data.name,
        valueParser: (params) =>
          parseString(params.newValue, ["snake_case", "no_blank"]),
      },
      {
        field: "description",
        headerName: "Description",
        flex: 2,
        resizable: false,
      },
      {
        field: "tags",
        headerName: "Tags",
        flex: 1,
        hide: true,
      },
    ];
    const handleSelectionChanged = (event) => {
      if (open) {
        const selectedData = event.api.getSelectedRows();
        setSelectedRows(selectedData);
      }
    };

    return (
      <BaseModal
        open={open}
        size="large-h-full"
        className="flex max-h-[50vh] gap-0 p-0"
        setOpen={(newOpen) => {
          handleSetOpen(newOpen);
        }}
      >
        <BaseModal.Header>
          <div className="flex w-full flex-row items-center border-b border-border px-4 py-3">
            <ForwardedIconComponent
              name={icon ?? "Table"}
              className="mr-2 h-6 w-6"
            />
            <div>{title}</div>
          </div>
        </BaseModal.Header>
        <BaseModal.Content className="flex flex-col gap-2 px-0 py-3">
          <div className="flex-1 px-4">
            <Input
              icon="Search"
              placeholder="Search actions..."
              inputClassName="h-8"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="h-[400px]">
            <TableComponent
              columnDefs={columnDefs}
              rowData={data}
              quickFilterText={searchQuery}
              stopEditingWhenCellsLoseFocus={true}
              editable={[
                {
                  field: "name",
                  editableCell: true,
                  onUpdate: () => {},
                },
                {
                  field: "description",
                  editableCell: true,
                  onUpdate: () => {},
                },
              ]}
              ref={agGrid}
              rowSelection="multiple"
              className="ag-tool-mode w-full overflow-visible"
              headerHeight={32}
              rowHeight={32}
              onSelectionChanged={handleSelectionChanged}
              tableOptions={{
                block_hide: true,
              }}
            />
          </div>
        </BaseModal.Content>
      </BaseModal>
    );
  },
);

export default ToolsModal;
