export const convertCSVToData = (csvFile) => {
  const lines = csvFile.split("\n");
  const headers = lines[0].trim().split(";");

  const initialRowData: any = [];
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