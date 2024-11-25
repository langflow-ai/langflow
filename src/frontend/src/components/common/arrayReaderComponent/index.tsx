import TableAutoCellRender from "../tableComponent/components/tableAutoCellRender";

export default function ArrayReader({ array }: { array: any[] }): JSX.Element {
  //TODO check array type
  return (
    <div>
      <ul>
        {array.map((item, index) => (
          <li key={index}>{<TableAutoCellRender value={item} />}</li>
        ))}
      </ul>
    </div>
  );
}
