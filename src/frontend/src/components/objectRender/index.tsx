import DictAreaModal from "../../modals/dictAreaModal";

export default function ObjectRender({ object }: { object: any }): JSX.Element {
  //TODO check object type

  return (
    <DictAreaModal value={object}>
      <div className="hover:animate-slow-wiggle">
        <div className="truncate">{JSON.stringify(object)}</div>
      </div>
    </DictAreaModal>
  );
}
