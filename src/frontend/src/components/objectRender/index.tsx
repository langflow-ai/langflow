import DictAreaModal from "../../modals/dictAreaModal";

export default function ObjectRender({ object }: { object: any }): JSX.Element {
  //TODO check object type

  return (
    <DictAreaModal value={object}>
      <div className="flex h-full w-full items-center align-middle hover:animate-slow-wiggle">
        <div className="flex h-full w-full items-center truncate align-middle">
          {JSON.stringify(object)}
        </div>
      </div>
    </DictAreaModal>
  );
}
