import TextModal from "../../modals/textModal";

export default function StringReader({
  string,
  setValue,
}: {
  string: string;
  setValue: (value: string) => void;
}): JSX.Element {
  return (
    <TextModal setValue={setValue} value={string}>
      <span className="truncate">{string}</span>
    </TextModal>
  );
}
