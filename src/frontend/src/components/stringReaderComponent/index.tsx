export default function StringReader({
  string,
}: {
  string: string;
}): JSX.Element {
  return (
    <span className="text-wrap py-2.5 leading-5 truncate-multiline">
      {string}
    </span>
  );
}
