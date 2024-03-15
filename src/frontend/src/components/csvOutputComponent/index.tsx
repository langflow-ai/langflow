import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-balham.css"; // Optional Theme applied to the grid
import { AgGridReact } from "ag-grid-react";
import { useEffect, useState } from "react";
import { useDarkStore } from "../../stores/darkStore";
import Loading from "../ui/loading";
import { convertCSVToData } from "./helpers/convert-data-function";

function CsvOutputComponent({ csvNode, csvSeparator }) {
  const [separator, setSeparator] = useState(csvSeparator);

  useEffect(() => {
    setSeparator(csvSeparator);
  }, [csvSeparator]);

  const dark = useDarkStore.getState().dark;

  const [rowData, setRowData] = useState([]);
  const [colDefs, setColDefs] = useState([]);

  const [status, setStatus] = useState("loading");
  const file = csvNode.file;

  useEffect(() => {
    if (file.type === "text/csv") {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const contents = e.target!.result;
          const { rowData: data, colDefs: columns } = convertCSVToData(
            contents,
            separator
          );
          setRowData(data);
          setColDefs(columns);
        } catch (e) {
          setStatus("error");
        }
        setStatus("loaded");
      };
      reader.readAsText(file);
    } else {
      setStatus("nodata");
    }
  }, [csvNode]);

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
          <AgGridReact rowData={rowData} columnDefs={colDefs} />
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
