import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-balham.css"; // Optional Theme applied to the grid
import { AgGridReact } from "ag-grid-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useDarkStore } from "../../stores/darkStore";
import Loading from "../ui/loading";
import { convertCSVToData } from "./helpers/convert-data-function";

function CsvOutputComponent({ csvNode }) {
  const separator = csvNode?.separator || ";";
  const file = csvNode?.data || "";

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
    if (file) {
      const { rowData: data, colDefs: columns } = convertCSVToData(
        file,
        separator
      );
      setRowData(data);
      setColDefs(columns);
      setStatus("loaded");
    } else {
      setStatus("nodata");
    }
  }, [csvNode]);

  const getRowHeight = useCallback((params: any) => {
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
        <div className=" h-full w-full items-center justify-center">
          <div className="chat-alert-box ">
            <span className="langflow-chat-span">No data available</span>
          </div>
        </div>
      )}
      {status === "error" && (
        <div className=" h-full w-full items-center justify-center">
          <div className="chat-alert-box ">
            <span className="langflow-chat-span">Error loading CSV</span>
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
            autoSizeStrategy={{
              type: "fitGridWidth",
            }}
            getRowHeight={getRowHeight}
            onGridReady={onGridReady}
            onFirstDataRendered={onFirstDataRendered}
            onGridSizeChanged={onGridSizeChanged}
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
