import { cloneDeep } from "lodash";
import { useState } from "react";
import ImageViewer from "../../../../components/ImageViewer";
import CsvOutputComponent from "../../../../components/csvOutputComponent";
import InputListComponent from "../../../../components/inputListComponent";
import PdfViewer from "../../../../components/pdfViewer";
import RecordsOutputComponent from "../../../../components/recordsOutputComponent";
import { Textarea } from "../../../../components/ui/textarea";
import { PDFViewConstant } from "../../../../constants/constants";
import { InputOutput } from "../../../../constants/enums";
import TextOutputView from "../../../../shared/components/textOutputView";
import useFlowStore from "../../../../stores/flowStore";
import { IOFieldViewProps } from "../../../../types/components";
import {
  convertValuesToNumbers,
  hasDuplicateKeys,
} from "../../../../utils/reactflowUtils";
import IOFileInput from "./components/FileInput";
import IoJsonInput from "./components/JSONInput";
import CsvSelect from "./components/csvSelect";
import IOKeyPairInput from "./components/keyPairInput";

export default function IOFieldView({
  type,
  fieldType,
  fieldId,
  left,
}: IOFieldViewProps): JSX.Element | undefined {
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const flowPool = useFlowStore((state) => state.flowPool);
  const node = nodes.find((node) => node.id === fieldId);
  const flowPoolNode = (flowPool[node!.id] ?? [])[
    (flowPool[node!.id]?.length ?? 1) - 1
  ];
  const handleChangeSelect = (e) => {
    if (node) {
      let newNode = cloneDeep(node);
      if (newNode.data.node.template.separator) {
        newNode.data.node.template.separator.value = e;
        setNode(newNode.id, newNode);
      }
    }
  };

  const [errorDuplicateKey, setErrorDuplicateKey] = useState(false);

  const textOutputValue =
    (flowPool[node!.id] ?? [])[(flowPool[node!.id]?.length ?? 1) - 1]?.data
      .results.result ?? "";

  console.log(
    (flowPool[node!.id] ?? [])[(flowPool[node!.id]?.length ?? 1) - 1]?.data,
  );

  function handleOutputType() {
    if (!node) return <>"No node found!"</>;
    switch (type) {
      case InputOutput.INPUT:
        switch (fieldType) {
          case "TextInput":
            return (
              <Textarea
                className={`w-full custom-scroll ${
                  left ? " min-h-32" : " h-full"
                }`}
                placeholder={"Enter text..."}
                value={node.data.node!.template["input_value"].value}
                onChange={(e) => {
                  e.target.value;
                  if (node) {
                    let newNode = cloneDeep(node);
                    newNode.data.node!.template["input_value"].value =
                      e.target.value;
                    setNode(node.id, newNode);
                  }
                }}
              />
            );
          case "FileLoader":
            return (
              <IOFileInput
                field={node.data.node!.template["file_path"]["value"]}
                updateValue={(e) => {
                  if (node) {
                    let newNode = cloneDeep(node);
                    newNode.data.node!.template["file_path"].value = e;
                    setNode(node.id, newNode);
                  }
                }}
              />
            );

          case "KeyPairInput":
            return (
              <IOKeyPairInput
                value={node.data.node!.template["input_value"]?.value}
                onChange={(e) => {
                  if (node) {
                    let newNode = cloneDeep(node);
                    newNode.data.node!.template["input_value"].value = e;
                    setNode(node.id, newNode);
                  }
                  const valueToNumbers = convertValuesToNumbers(e);
                  setErrorDuplicateKey(hasDuplicateKeys(valueToNumbers));
                }}
                duplicateKey={errorDuplicateKey}
                isList={node.data.node!.template["input_value"]?.list ?? false}
                isInputField
              />
            );

          case "JsonInput":
            return (
              <IoJsonInput
                value={node.data.node!.template["input_value"]?.value}
                onChange={(e) => {
                  if (node) {
                    let newNode = cloneDeep(node);
                    newNode.data.node!.template["input_value"].value = e;
                    setNode(node.id, newNode);
                  }
                }}
                left={left}
              />
            );

          case "StringListInput":
            return (
              <>
                <InputListComponent
                  value={node.data.node!.template["input_value"]?.value}
                  onChange={(e) => {
                    if (node) {
                      let newNode = cloneDeep(node);
                      newNode.data.node!.template["input_value"].value = e;
                      setNode(node.id, newNode);
                    }
                  }}
                  disabled={false}
                />
              </>
            );

          default:
            return (
              <Textarea
                className={`w-full custom-scroll ${
                  left ? " min-h-32" : " h-full"
                }`}
                placeholder={"Enter text..."}
                value={node.data.node!.template["input_value"]}
                onChange={(e) => {
                  e.target.value;
                  if (node) {
                    let newNode = cloneDeep(node);
                    newNode.data.node!.template["input_value"].value =
                      e.target.value;
                    setNode(node.id, newNode);
                  }
                }}
              />
            );
        }
      case InputOutput.OUTPUT:
        switch (fieldType) {
          case "TextOutput":
            return <TextOutputView left={left} value={textOutputValue} />;
          case "PDFOutput":
            return left ? (
              <div>{PDFViewConstant}</div>
            ) : (
              <PdfViewer pdf={flowPoolNode?.params ?? ""} />
            );
          case "CSVOutput":
            return left ? (
              <>
                <CsvSelect
                  node={node}
                  handleChangeSelect={handleChangeSelect}
                />
              </>
            ) : (
              <>
                <CsvOutputComponent csvNode={node} flowPool={flowPoolNode} />
              </>
            );
          case "ImageOutput":
            return left ? (
              <div>Expand the view to see the image</div>
            ) : (
              <ImageViewer
                image={
                  (flowPool[node.id] ?? [])[
                    (flowPool[node.id]?.length ?? 1) - 1
                  ]?.params ?? ""
                }
              />
            );

          case "JsonOutput":
            return (
              <IoJsonInput
                value={node.data.node!.template["input_value"]?.value}
                onChange={(e) => {
                  if (node) {
                    let newNode = cloneDeep(node);
                    newNode.data.node!.template["input_value"].value = e;
                    setNode(node.id, newNode);
                  }
                }}
                left={left}
                output
              />
            );

          case "KeyPairOutput":
            return (
              <IOKeyPairInput
                value={node.data.node!.template["input_value"]?.value}
                onChange={(e) => {
                  if (node) {
                    let newNode = cloneDeep(node);
                    newNode.data.node!.template["input_value"].value = e;
                    setNode(node.id, newNode);
                  }
                  const valueToNumbers = convertValuesToNumbers(e);
                  setErrorDuplicateKey(hasDuplicateKeys(valueToNumbers));
                }}
                duplicateKey={errorDuplicateKey}
                isList={node.data.node!.template["input_value"]?.list ?? false}
              />
            );

          case "StringListOutput":
            return (
              <>
                <InputListComponent
                  value={node.data.node!.template["input_value"]?.value}
                  onChange={(e) => {
                    if (node) {
                      let newNode = cloneDeep(node);
                      newNode.data.node!.template["input_value"].value = e;
                      setNode(node.id, newNode);
                    }
                  }}
                  playgroundDisabled
                  disabled={false}
                />
              </>
            );
          case "RecordsOutput":
            return (
              <div className={left ? "h-56" : "h-full"}>
                <RecordsOutputComponent
                  pagination={!left}
                  rows={
                    Array.isArray(flowPoolNode?.data?.artifacts)
                      ? flowPoolNode?.data?.artifacts?.map(
                          (artifact) => artifact.data,
                        ) ?? []
                      : [flowPoolNode?.data?.artifacts]
                  }
                  columnMode="union"
                />
              </div>
            );

          default:
            return (
              <Textarea
                className={`w-full custom-scroll ${
                  left ? " min-h-32" : " h-full"
                }`}
                placeholder={"Empty"}
                // update to real value on flowPool
                value={
                  (flowPool[node.id] ?? [])[
                    (flowPool[node.id]?.length ?? 1) - 1
                  ]?.data.results.result ?? ""
                }
                readOnly
              />
            );
        }
      default:
        break;
    }
  }
  return handleOutputType();
}
