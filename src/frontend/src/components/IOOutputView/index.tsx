import useFlowStore from "../../stores/flowStore";
import { IOOutputProps } from "../../types/components";
import CsvOutputComponent from "../csvOutputComponent";
import PdfViewer from "../pdfViewer";
import { Textarea } from "../ui/textarea";
import ImageViewer from "../ImageViewer";
import { CSVViewConstant, IMGViewConstant, PDFViewConstant } from "../../constants/constants";


export default function IOOutputView({
  outputType,
  outputId,
  left,
}: IOOutputProps): JSX.Element | undefined {
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const flowPool = useFlowStore((state) => state.flowPool);
  const node = nodes.find((node) => node.id === outputId);

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
          <div>{PDFViewConstant}</div>
        ) : (
          <PdfViewer
            pdf={
              (flowPool[node.id] ?? [])[(flowPool[node.id]?.length ?? 1) - 1]
                ?.params ?? ""
            }
          />
        );
      case "CSVOutput":
        return left ? (
          <>
            <div className="flex align-center justify-center">
              {CSVViewConstant}
            </div>
          </>
        ) : (
          <>
            <CsvOutputComponent
              csvNode={
                (flowPool[node!.id] ?? [])[
                  (flowPool[node!.id]?.length ?? 1) - 1
                ]?.data?.artifacts?.repr
              }
            />
          </>
        );
      case "ImageOutput":
        return (
          left ? (
            <div>{IMGViewConstant}</div>
          ) : (
            <ImageViewer image={
              (flowPool[node.id] ?? [])[(flowPool[node.id]?.length ?? 1) - 1]
                  ?.params ?? ""
            } />
          )
        ) 
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
