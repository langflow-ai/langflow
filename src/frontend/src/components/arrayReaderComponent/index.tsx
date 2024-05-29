export default function ArrayReader({ array }: { array: any[] }): JSX.Element {
  //TODO check array type
  return (
    <div>
      <ul>
        {array.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
