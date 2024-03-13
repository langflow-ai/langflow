import { useState } from "react";
import CSVReader from "react-csv-reader";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui/table";

export default function CsvOutputComponent() {
  const [data, setData] = useState([]);

  const handleForce = (data: any, fileInfo: any) => {
    console.log(data, fileInfo);
    setData(data);
  };

  const handleDarkSideForce = (data: any) => {
    console.log(data);
  };

  const papaparseOptions = {
    header: true,
    dynamicTyping: true,
    skipEmptyLines: true,
    transformHeader: (header: string) =>
      header.toLowerCase().replace(/\W/g, "_"),
  };

  function renderTableHeader() {
    let header = Object.keys(data[0]);
    return header.map((key, index) => {
      return <TableHead key={index}>{key}</TableHead>;
    });
  }

  function renderTableData() {
    return data.map((item, index) => {
      return (
        <TableRow key={index}>
          {Object.values(item).map((value: any, index) => {
            return <TableCell key={index}>{value}</TableCell>;
          })}
        </TableRow>
      );
    });
  }

  if (data.length === 0) {
    return (
      <div className="">
        <CSVReader
          cssClass="csv-reader-input"
          label="Select CSV with secret Death Star statistics"
          onFileLoaded={handleForce}
          onError={handleDarkSideForce}
          parserOptions={papaparseOptions}
          inputId="ObiWan"
          inputName="ObiWan"
          inputStyle={{ color: "red" }}
        />
      </div>
    );
  }

  return (
    <div className="h-[200px] w-fit overflow-hidden">
      <Table className="table-auto origin-top-left scale-50 transform text-sm">
        <TableHeader>
          <TableRow>{renderTableHeader()}</TableRow>
        </TableHeader>
        <TableBody>{renderTableData()}</TableBody>
      </Table>
    </div>
  );
}
