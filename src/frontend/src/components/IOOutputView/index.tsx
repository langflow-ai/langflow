import { useState } from "react";
import useFlowStore from "../../stores/flowStore";
import { IOOutputProps } from "../../types/components";
import CsvOutputComponent from "../csvOutputComponent";
import PdfViewer from "../pdfViewer";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import { Textarea } from "../ui/textarea";

export default function IOOutputView({
  outputType,
  outputId,
  left,
}: IOOutputProps): JSX.Element | undefined {
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const flowPool = useFlowStore((state) => state.flowPool);
  const node = nodes.find((node) => node.id === outputId);
  const [csvSeparator, setCsvSeparator] = useState<string>(";");

  const handleChangeSelect = (e) => {
    setCsvSeparator(e);
  };

  function handleOutputType() {
    if (!node) return <>"No node found!"</>;
    switch (outputType) {
      case "TextOutput":
        return (
          <Textarea
            className={`w-full custom-scroll ${left ? "" : " h-full"}`}
            placeholder={"Empty"}
            // update to real value on flowPool
            value={
              (flowPool[node.id] ?? [])[(flowPool[node.id]?.length ?? 1) - 1]
                ?.data.results.result.result ?? ""
            }
            readOnly
          />
        );
      case "PDFOutput":
        return left ? (
          <div>Expand the ouptut to see the PDF</div>
        ) : (
          <PdfViewer
            pdf={
              (flowPool[node.id] ?? [])[(flowPool[node.id]?.length ?? 1) - 1]
                ?.params ?? ""
            }
          />
        );
      case "CSVLoader":
        return left ? (
          <>
            <div className="flex justify-between">
              Expand the ouptut to see the CSV
            </div>
            <div className="flex items-center justify-between pt-5">
              <span>CSV separator </span>
              <Select onValueChange={(e) => handleChangeSelect(e)}>
                <SelectTrigger className="w-[70px]">
                  <SelectValue placeholder=";" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value=",">,</SelectItem>
                    <SelectItem value=".">.</SelectItem>
                    <SelectItem value=";">;</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
          </>
        ) : (
          <CsvOutputComponent
            key={csvSeparator}
            csvNode={node.data}
            csvSeparator={csvSeparator}
          />
        );

      default:
        return (
          <Textarea
            className={`w-full custom-scroll ${left ? "" : " h-full"}`}
            placeholder={"Empty"}
            // update to real value on flowPool
            value={
              (flowPool[node.id] ?? [])[(flowPool[node.id]?.length ?? 1) - 1]
                ?.params ?? ""
            }
            readOnly
          />
        );
    }
  }
  return handleOutputType();
}
