import { CustomCellEditorProps, CustomCellRendererProps } from "ag-grid-react";
import { classNames, cn, isTimeStampString } from "../../utils/utils";
import ArrayReader from "../arrayReaderComponent";
import DateReader from "../dateReaderComponent";
import NumberReader from "../numberReader";
import ObjectRender from "../objectRender";
import StringReader from "../stringReaderComponent";
import { Badge } from "../ui/badge";
import { cloneDeep } from "lodash";
import { type } from "os";
import {
  convertObjToArray,
  convertValuesToNumbers,
  hasDuplicateKeys,
  scapedJSONStringfy,
} from "../../utils/reactflowUtils";
import CodeAreaComponent from "../codeAreaComponent";
import DictComponent from "../dictComponent";
import Dropdown from "../dropdownComponent";
import FloatComponent from "../floatComponent";
import InputFileComponent from "../inputFileComponent";
import InputGlobalComponent from "../inputGlobalComponent";
import InputListComponent from "../inputListComponent";
import IntComponent from "../intComponent";
import KeypairListComponent from "../keypairListComponent";
import PromptAreaComponent from "../promptComponent";
import TextAreaComponent from "../textAreaComponent";
import ToggleShadComponent from "../toggleShadComponent";
import { useState } from "react";
import useFlowStore from "../../stores/flowStore";

export default function TableToggleCellRender({
  value: { name, enabled, setEnabled },
}: CustomCellRendererProps) {
  const [value, setValue] = useState(enabled);

  return (
    <ToggleShadComponent
      id={"show" + name}
      enabled={value}
      setEnabled={(e) => {
        setValue(e);
        setEnabled(e);
      }}
      size="small"
      editNode={true}
    />
  );
}
