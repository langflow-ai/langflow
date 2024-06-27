import {
  getCodesObjProps,
  getCodesObjReturn,
} from "../../../types/utils/functions";

export default function getCodesObj({
  runCurlCode,
  webhookCurlCode,
  pythonApiCode,
  jsApiCode,
  pythonCode,
  widgetCode,
}: getCodesObjProps): getCodesObjReturn {
  return [
    {
      name: "run curl",
      code: runCurlCode,
    },
    {
      name: "webhook curl",
      code: webhookCurlCode,
    },
    {
      name: "python api",
      code: pythonApiCode,
    },
    {
      name: "js api",
      code: jsApiCode,
    },
    {
      name: "python code",
      code: pythonCode,
    },
    {
      name: "chat widget html",
      code: widgetCode,
    },
  ];
}
