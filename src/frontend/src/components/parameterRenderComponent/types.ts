import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { APIClassType } from "@/types/api";
import { ColumnField } from "@/types/utils/functions";

// Base type for RefreshParameterComponent children
export type BaseInputProps<valueType = any> = {
  id: string;
  value: valueType;
  editNode: boolean;
  handleOnNewValue: handleOnNewValueType;
  disabled: boolean;
  nodeClass?: APIClassType;
  handleNodeClass?: (value: any, code?: string, type?: string) => void;
  readonly?: boolean;
};

// Generic type for composing input props
export type InputProps<valueType = any, T = {}> = BaseInputProps<valueType> & T;


export type TableComponentType = {
    description: string;
    tableTitle: string;
    columns?: ColumnField[];
  };

  export type CodeAreaComponentType = {
    disabled: boolean;
    onChange: (
      value: string[] | string,
      dbValue?: boolean,
      skipSnapshot?: boolean,
    ) => void;
    value: string;
    editNode?: boolean;
    nodeClass?: APIClassType;
    setNodeClass?: (value: APIClassType, type: string) => void;
    id?: string;
  };
