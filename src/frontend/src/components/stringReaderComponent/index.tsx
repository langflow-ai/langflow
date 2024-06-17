import TextModal from "../../modals/textModal";

export default function StringReader({
  string,
}: {
  string: string;
}): JSX.Element {
  return string.length > 10 ? (
    <TextModal value={string}>
      <span className="truncate">{string}</span>
    </TextModal>
  ) : (
    <span className="truncate">{string}</span>
  );
}
