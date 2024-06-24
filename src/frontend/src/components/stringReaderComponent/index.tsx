import { ColDef, Column } from "ag-grid-community";
import TextModal from "../../modals/textModal";

export default function StringReader({
  string,
  setValue,
  editable = false,
}: {
  string: string;
  setValue: (value: string) => void;
  editable: boolean;
}): JSX.Element {
  return (
    <TextModal editable={editable} setValue={setValue} value={string}>
      <span className="truncate">{string}</span>
    </TextModal>
  );
}
