import TextModal from "../../modals/textModal";

export default function StringReader({
  string,
}: {
  string: string;
}): JSX.Element {
  return (
    <TextModal value={string}>
      <span className="truncate">{string}</span>
    </TextModal>
  );
}
