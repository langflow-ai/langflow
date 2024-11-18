import TextModal from "../../../modals/textModal";

export default function StringReader({
  string,
  setValue,
  editable = false,
}: {
  string: string | null;
  setValue: (value: string) => void;
  editable: boolean;
}): JSX.Element {
  return (
    <TextModal editable={editable} setValue={setValue} value={string ?? ""}>
      {/* INVISIBLE CHARACTER TO PREVENT AGgrid bug */}
      <span className="truncate">{string ?? "‎"}</span>
    </TextModal>
  );
}
