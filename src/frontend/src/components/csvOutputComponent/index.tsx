import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-balham.css"; // Optional Theme applied to the grid
import { AgGridReact } from "ag-grid-react";
import { useState } from "react";

function CsvOutputComponent() {
  const [rowData, setRowData] = useState([]);
  const [colDefs, setColDefs] = useState([]);

  // Function to handle file upload
  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    const reader = new FileReader();
    reader.onload = (e) => {
      const contents = e.target.result;
      const { rowData: data, colDefs: columns } = convertCSVToData(contents);
      setRowData(data);
      setColDefs(columns);
    };
    reader.readAsText(file);
  };

  // Function to convert CSV to data
  const convertCSVToData = (csvFile) => {
    const lines = csvFile.split("\n");
    const headers = lines[0].trim().split(";");

    const initialRowData = [];
    const initialColDefs = headers.map((header) => ({ field: header.trim() }));

    for (let i = 1; i < lines.length; i++) {
      const data = lines[i].trim().split(";");
      const rowDataEntry = {};

      for (let j = 0; j < headers.length; j++) {
        const value = isNaN(data[j]) ? data[j] : parseFloat(data[j]);
        rowDataEntry[headers[j].trim()] = value;
      }

      initialRowData.push(rowDataEntry);
    }

    return { rowData: initialRowData, colDefs: initialColDefs };
  };

  return (
    <div>
      <input type="file" onChange={handleFileUpload} />
      <div className="ag-theme-balham" style={{ height: 500, width: "100%" }}>
        <AgGridReact rowData={rowData} columnDefs={colDefs} />
      </div>
    </div>
  );
}

export default CsvOutputComponent;
