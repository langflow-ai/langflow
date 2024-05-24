export default function StringReader({
  string,
}: {
  string: string;
}): JSX.Element {
  return <span className="truncate">{string}</span>;
}
