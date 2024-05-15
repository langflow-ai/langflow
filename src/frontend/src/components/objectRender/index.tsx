import DictAreaModal from "../../modals/dictAreaModal";

export default function ObjectRender({ object }: { object: any }): JSX.Element {
  //TODO check object type
  return (
    <DictAreaModal value={object}>
      <div className="flex gap-1">
        <div className="truncate">{JSON.stringify(object)}</div>
        see more
      </div>
    </DictAreaModal>
  );
}
