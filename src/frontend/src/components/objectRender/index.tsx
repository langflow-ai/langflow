import DictAreaModal from "../../modals/dictAreaModal";

export default function ObjectRender({ object }: { object: any }): JSX.Element {
  //TODO check object type

  return (
    <DictAreaModal value={object}>
      <div className="flex h-full w-full items-center align-middle transition-all">
        <div className="truncate">{JSON.stringify(object)}</div>
      </div>
    </DictAreaModal>
  );
}
