import type { AllNodeType } from "@/types/flow";
import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-balham.css"; // Optional Theme applied to the grid
import { useEffect, useMemo, useState } from "react";
import {
  CSVError,
  CSVNoDataError,
  CSVViewErrorTitle,
} from "../../../constants/constants";
import { useDarkStore } from "../../../stores/darkStore";
import type { VertexBuildTypeAPI } from "../../../types/api";
import ForwardedIconComponent from "../../common/genericIconComponent";
import Loading from "../../ui/loading";
import TableComponent from "../parameterRenderComponent/components/tableComponent";
import { convertCSVToData } from "./helpers/convert-data-function";

function CsvOutputComponent({
  csvNode,
  flowPool,
}: {
  csvNode: AllNodeType;
  flowPool: VertexBuildTypeAPI;
}) {
  const csvNodeArtifacts = flowPool?.data?.artifacts?.repr;
  const jsonString = csvNodeArtifacts?.replace(/'/g, '"');
  let file = null;
  try {
    file = JSON?.parse(jsonString) || "";
  } catch (_e) {
    console.log("Error parsing JSON");
  }

  if (!file) {
    return (
      <div className="align-center flex h-full w-full flex-col items-center justify-center gap-5">
        <div className="align-center flex w-full justify-center gap-2">
          <ForwardedIconComponent name="Table" />
          {CSVViewErrorTitle}
        </div>
        <div className="align-center flex w-full justify-center">
          <div className="langflow-chat-desc align-center flex justify-center px-6 py-8">
            <div className="langflow-chat-desc-span">{CSVError}</div>
          </div>
        </div>
      </div>
    );
  }

  const separator = csvNode?.data?.node?.template?.separator?.value || ",";

  const dark = useDarkStore.getState().dark;

  const [rowData, setRowData] = useState([]);
  const [colDefs, setColDefs] = useState([]);

  const [status, setStatus] = useState("loading");
  const defaultColDef = useMemo(() => {
    return {
      width: 200,
      editable: true,
      filter: true,
    };
  }, []);

  useEffect(() => {
    setStatus("loading");
    if (file) {
      const { rowData: data, colDefs: columns } = convertCSVToData(
        file,
        separator,
      );
      setRowData(data);
      setColDefs(columns);

      setTimeout(() => {
        setStatus("loaded");
      }, 1000);
    } else {
      setStatus("nodata");
    }
  }, [separator]);

  return (
    <div className="h-full rounded-md border bg-muted">
      {status === "nodata" && (
        <div className="align-center flex h-full w-full flex-col items-center justify-center gap-5">
          <div className="align-center flex w-full justify-center gap-2">
            <ForwardedIconComponent name="Table" />
            {CSVViewErrorTitle}
          </div>
          <div className="align-center flex w-full justify-center">
            <div className="langflow-chat-desc align-center flex justify-center px-6 py-8">
              <div className="langflow-chat-desc-span">{CSVNoDataError}</div>
            </div>
          </div>
        </div>
      )}
      {status === "error" && (
        <div className="align-center flex h-full w-full flex-col items-center justify-center gap-5">
          <div className="align-center flex w-full justify-center gap-2">
            <ForwardedIconComponent name="Table" />
            {CSVViewErrorTitle}
          </div>
          <div className="align-center flex w-full justify-center">
            <div className="langflow-chat-desc align-center flex justify-center px-6 py-8">
              <div className="langflow-chat-desc-span">{CSVError}</div>
            </div>
          </div>
        </div>
      )}

      {status === "loaded" && (
        <div
          className={`${dark ? "ag-theme-balham-dark" : "ag-theme-balham"}`}
          style={{ height: "100%", width: "100%" }}
        >
          <TableComponent
            key={"csv-output"}
            rowData={rowData}
            columnDefs={colDefs}
            defaultColDef={defaultColDef}
            scrollbarWidth={8}
            overlayNoRowsTemplate="No data available"
          />
        </div>
      )}
      {status === "loading" && (
        <div className="flex h-full w-full items-center justify-center align-middle">
          <Loading />
        </div>
      )}
    </div>
  );
}

export default CsvOutputComponent;
