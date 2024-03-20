import { cloneDeep } from "lodash";
import useFlowStore from "../../stores/flowStore";
import { IOOutputProps } from "../../types/components";
import ImageViewer from "../ImageViewer";
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

  function handleOutputType() {
    if (!node) return <>"No node found!"</>;
    switch (outputType) {
      case "TextOutput":
        return (
          <Textarea
            className={`w-full custom-scroll ${left ? "" : " h-full"}`}
            placeholder={"Empty"}
            // update to real value on flowPool
            value={flowPoolNode?.data.results.result.result ?? ""}
            readOnly
          />
        );
      case "PDFOutput":
        return left ? (
          <div>Expand the ouptut to see the PDF</div>
        ) : (
          <PdfViewer pdf={flowPoolNode?.params ?? ""} />
        );
      case "CSVOutput":
        return left ? (
          <>
            <div className="flex justify-between">
              Expand the ouptut to see the CSV
            </div>
            <div className="flex items-center justify-between pt-5">
              <span>CSV separator </span>
              <Select
                value={node.data.node.template.separator.value}
                onValueChange={(e) => handleChangeSelect(e)}
              >
                <SelectTrigger className="w-[70px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {node?.data?.node?.template?.separator?.options.map(
                      (separator) => (
                        <SelectItem key={separator} value={separator}>
                          {separator}
                        </SelectItem>
                      )
                    )}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
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
              (flowPool[node.id] ?? [])[(flowPool[node.id]?.length ?? 1) - 1]
                ?.params ?? ""
            }
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
