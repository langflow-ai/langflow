export default function ObjectRender({ object }: { object: any }): JSX.Element {
  //TODO check object type
  return <div>{JSON.stringify(object)}</div>;
}
