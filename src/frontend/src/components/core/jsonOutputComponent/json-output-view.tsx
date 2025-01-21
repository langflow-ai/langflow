import React from "react";
import JsonEditor from "../jsonEditor";

interface JsonOutputViewComponentProps {
  data: string | object;
  width?: string;
  height?: string;
}

const JsonOutputViewComponent: React.FC<JsonOutputViewComponentProps> = ({
  data,
  width = "100%",
  height = "600px",
}) => {
  const jsonData = typeof data === "string" ? JSON.parse(data) : data;

  return (
    <JsonEditor
      data={{ json: jsonData }}
      readOnly={true}
      width={width}
      height={height}
      className=" border border-border rounded"
    />
  );
};

export default JsonOutputViewComponent;
