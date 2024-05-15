import DictAreaModal from "../../modals/dictAreaModal";

export default function ObjectRender({ object }: { object: any }): JSX.Element {
  //TODO check object type
  return (
    <DictAreaModal value={object}>
      <>{JSON.stringify(object)}</>
    </DictAreaModal>
  );
}
