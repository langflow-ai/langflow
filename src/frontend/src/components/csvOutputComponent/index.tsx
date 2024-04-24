import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-balham.css"; // Optional Theme applied to the grid
import { AgGridReact } from "ag-grid-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CSVError,
  CSVNoDataError,
  CSVViewErrorTitle,
} from "../../constants/constants";
import { useDarkStore } from "../../stores/darkStore";
import { FlowPoolObjectType } from "../../types/chat";
import { NodeType } from "../../types/flow";
import ForwardedIconComponent from "../genericIconComponent";
import Loading from "../ui/loading";
import { convertCSVToData } from "./helpers/convert-data-function";

function CsvOutputComponent({
  csvNode,
  flowPool,
}: {
  csvNode: NodeType;
  flowPool: FlowPoolObjectType;
}) {
  const csvNodeArtifacts = flowPool?.data?.artifacts?.repr;
  const jsonString = csvNodeArtifacts?.replace(/'/g, '"');
  let file = null;
  try {
    file = JSON?.parse(jsonString) || "";
  } catch (e) {
    console.log("Error parsing JSON");
  }

  if (!file) {
    return (
      <div className=" align-center flex h-full w-full flex-col items-center justify-center gap-5">
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
  var currentRowHeight: number;
  var minRowHeight = 25;
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
        separator
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

  const getRowHeight = useCallback(() => {
    return currentRowHeight;
  }, []);

  const onGridReady = useCallback((params: any) => {
    minRowHeight = params.api.getSizesForCurrentTheme().rowHeight;
    currentRowHeight = minRowHeight;
  }, []);

  const updateRowHeight = (params: { api: any }) => {
    const bodyViewport = document.querySelector(".ag-body-viewport");
    if (!bodyViewport) {
      return;
    }
    var gridHeight = bodyViewport.clientHeight;
    var renderedRowCount = params.api.getDisplayedRowCount();

    if (renderedRowCount * minRowHeight >= gridHeight) {
      if (currentRowHeight !== minRowHeight) {
        currentRowHeight = minRowHeight;
        params.api.resetRowHeights();
      }
    } else {
      currentRowHeight = Math.floor(gridHeight / renderedRowCount);
      params.api.resetRowHeights();
    }
  };

  const onFirstDataRendered = useCallback(
    (params: any) => {
      updateRowHeight(params);
    },
    [updateRowHeight]
  );

  const onGridSizeChanged = useCallback(
    (params: any) => {
      updateRowHeight(params);
    },
    [updateRowHeight]
  );

  return (
    <div className=" h-full rounded-md border bg-muted">
      {status === "nodata" && (
        <div className=" align-center flex h-full w-full flex-col items-center justify-center gap-5">
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
        <div className=" align-center flex h-full w-full flex-col items-center justify-center gap-5">
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
          <AgGridReact
            rowData={rowData}
            columnDefs={colDefs}
            defaultColDef={defaultColDef}
            getRowHeight={getRowHeight}
            onGridReady={onGridReady}
            onFirstDataRendered={onFirstDataRendered}
            onGridSizeChanged={onGridSizeChanged}
            scrollbarWidth={8}
          />
        </div>
      )}
      {status === "loading" && (
        <div className="  flex h-full w-full items-center justify-center align-middle">
          <Loading />
        </div>
      )}
    </div>
  );
}

export default CsvOutputComponent;
