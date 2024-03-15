import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-balham.css"; // Optional Theme applied to the grid
import { AgGridReact } from "ag-grid-react";
import { useEffect, useState } from "react";
import { convertCSVToData } from "./helpers/convert-data-function";

function CsvOutputComponent({ csvNode, csvSeparator = ";" }) {
  const [rowData, setRowData] = useState([]);
  const [colDefs, setColDefs] = useState([]);

  const [status, setStatus] = useState("loading");

  const file = csvNode.file;

  useEffect(() => {
    if (file) {
      const reader = new FileReader();

      reader.onload = (e) => {
        try {
          const contents = e.target!.result;

          const { rowData: data, colDefs: columns } = convertCSVToData(
            contents,
            csvSeparator
          );
          setRowData(data);
          setColDefs(columns);
        } catch (e) {
          setStatus("error");
        }

        setStatus("loaded");
      };
      reader.readAsText(file);
    }
  }, [csvNode]);

  return (
    <div>
      <div className="ag-theme-balham" style={{ height: 500, width: "100%" }}>
        <AgGridReact rowData={rowData} columnDefs={colDefs} />
      </div>
    </div>
  );
}

export default CsvOutputComponent;
