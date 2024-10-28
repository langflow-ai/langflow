import RenderIcons from "@/components/renderIconComponent";

export default function ShortcutDisplay({
  name,
  shortcut,
}: {
  name: string;
  shortcut: string;
}): JSX.Element {
  const fixedShortcut = shortcut?.split("+");
  return (
    <div className="flex content-center items-center justify-center self-center text-[12px]">
      <span> {name} </span>
      <span
        className={`ml-3 flex items-center rounded-sm bg-primary-hover px-1.5 py-[0.1em] text-muted`}
      >
        <RenderIcons filteredShortcut={fixedShortcut} />
      </span>
    </div>
  );
}
