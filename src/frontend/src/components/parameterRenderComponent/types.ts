import { APIClassType } from "@/types/api";

// Base type for RefreshParameterComponent children
export type BaseInputProps = {
  id: string;
  value: any;
  editNode: boolean;
  onChange: (value: any) => void;
  disabled: boolean;
  nodeClass?: APIClassType;
  setNodeClass?: (value: any, code?: string, type?: string) => void;
  readonly?: boolean;
};

// Generic type for composing input props
export type InputProps<T = {}> = BaseInputProps & T;
