import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import Loading from "@/components/ui/loading";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  useGetTritonModelConfig,
  useGetTritonModels,
} from "@/controllers/API/queries/triton/use-get-triton-models";
import { usePostTritonInfer } from "@/controllers/API/queries/triton/use-post-triton-infer";
import useAlertStore from "@/stores/alertStore";
import type { TritonInferRequest, TritonInferResponse } from "@/types/triton";

type InferTabProps = {
  serverId: string;
};

export function InferTab({ serverId }: InferTabProps) {
  const { t } = useTranslation();
  const { data: modelsData, isLoading: modelsLoading } = useGetTritonModels({
    serverId,
  });
  const [modelName, setModelName] = useState<string>("");
  const [body, setBody] = useState<string>("");
  const [response, setResponse] = useState<TritonInferResponse | null>(null);
  const [responseRaw, setResponseRaw] = useState<string>("");
  const { mutateAsync, isPending } = usePostTritonInfer();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const models = modelsData?.models ?? [];

  useEffect(() => {
    if (models.length > 0 && !modelName) {
      setModelName(models[0].name);
    }
  }, [models, modelName]);

  const { refetch: refetchConfig } = useGetTritonModelConfig(
    { serverId, modelName },
    { enabled: false },
  );

  const generateTemplate = async () => {
    if (!modelName) return;
    try {
      const res = await refetchConfig();
      const cfg = res.data;
      if (!cfg) {
        setErrorData({
          title: t("triton.infer.error"),
          list: [t("triton.inference.noModelConfig")],
        });
        return;
      }
      const inputs = (cfg.inputs ?? []).map((tensor) => ({
        name: tensor.name,
        shape: tensor.shape,
        data: [exampleValueForDataType(tensor.data_type)],
        datatype: dataTypeToDatatype(tensor.data_type),
      }));
      const template: TritonInferRequest = { inputs };
      setBody(JSON.stringify(template, null, 2));
      setSuccessData({
        title: t("triton.inference.templateGenerated"),
      });
    } catch {
      setErrorData({
        title: t("triton.infer.error"),
        list: [t("triton.inference.noModelConfig")],
      });
    }
  };

  const handleSend = async () => {
    if (!modelName) return;
    let parsed: TritonInferRequest;
    try {
      parsed = JSON.parse(body);
    } catch {
      setErrorData({
        title: t("triton.infer.error"),
        list: [t("triton.inference.invalidJson")],
      });
      return;
    }
    try {
      const res = await mutateAsync({
        serverId,
        modelName,
        body: parsed,
      });
      setResponse(res);
      setResponseRaw(JSON.stringify(res, null, 2));
      setSuccessData({ title: t("triton.infer.success") });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrorData({ title: t("triton.infer.error"), list: [msg] });
    }
  };

  const canSend = modelName && body.trim().length > 0 && !isPending;

  if (modelsLoading) return <Loading />;

  if (models.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        {t("triton.models.noModels")}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">
            {t("triton.inference.modelLabel")}
          </label>
          <Select value={modelName} onValueChange={setModelName}>
            <SelectTrigger
              className="w-64"
              data-testid="triton-infer-model-select"
            >
              <SelectValue placeholder={t("triton.inference.selectModel")} />
            </SelectTrigger>
            <SelectContent>
              {models.map((m) => (
                <SelectItem key={m.name} value={m.name}>
                  {m.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={generateTemplate}
          disabled={!modelName}
          data-testid="triton-infer-generate-template"
        >
          <ForwardedIconComponent name="Wand2" className="h-3.5 w-3.5" />
          {t("triton.inference.generateTemplate")}
        </Button>
        <Button
          variant="primary"
          size="sm"
          onClick={handleSend}
          disabled={!canSend}
          loading={isPending}
          data-testid="triton-infer-send"
          className="ml-auto"
        >
          <ForwardedIconComponent name="Play" className="h-3.5 w-3.5" />
          {t("triton.inference.send")}
        </Button>
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-xs text-muted-foreground">
          {t("triton.inference.requestLabel")}
        </label>
        <Textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={12}
          className="font-mono text-xs"
          placeholder={
            '{\n  "inputs": [\n    {\n      "name": "input",\n      "shape": [1],\n      "data": ["hello"],\n      "datatype": "BYTES"\n    }\n  ]\n}'
          }
          data-testid="triton-infer-body"
        />
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-xs text-muted-foreground">
          {t("triton.inference.responseLabel")}
        </label>
        <pre
          className="max-h-96 overflow-auto rounded-md border bg-muted/30 p-3 font-mono text-xs"
          data-testid="triton-infer-response"
        >
          {responseRaw || "—"}
        </pre>
      </div>
      {response?.outputs?.map((o) => (
        <OutputPreview key={o.name} output={o} />
      ))}
    </div>
  );
}

function OutputPreview({
  output,
}: {
  output: TritonInferResponse["outputs"][number];
}) {
  const first = output.data?.[0];
  if (typeof first === "string" && first.length < 200) {
    return (
      <div className="flex items-center gap-2 rounded-md border p-2 text-sm">
        <span className="font-mono text-xs text-muted-foreground">
          {output.name}:
        </span>
        <span>{first}</span>
      </div>
    );
  }
  return null;
}

function exampleValueForDataType(dataType: string): unknown {
  const lower = dataType.toLowerCase();
  if (lower.includes("bool")) return [true];
  if (lower.includes("int")) return [0];
  if (lower.includes("fp") || lower.includes("float")) return [0.0];
  return ["sample"];
}

function dataTypeToDatatype(dataType: string): string {
  const lower = dataType.toLowerCase();
  if (lower.includes("bool")) return "BOOL";
  if (lower.includes("int8")) return "INT8";
  if (lower.includes("int16")) return "INT16";
  if (lower.includes("int32")) return "INT32";
  if (lower.includes("int64")) return "INT64";
  if (lower.includes("fp16") || lower.includes("float16")) return "FP16";
  if (lower.includes("fp32") || lower.includes("float32")) return "FP32";
  if (lower.includes("fp64") || lower.includes("float64")) return "FP64";
  if (lower.includes("bytes") || lower.includes("string")) return "BYTES";
  return "BYTES";
}
