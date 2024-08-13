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
    <div className="flex justify-center">
      <span> {name} </span>
      <span
        className={`ml-3 flex items-center rounded-sm bg-muted px-1.5 py-[0.1em] text-lg text-muted-foreground`}
      >
        <RenderIcons filteredShortcut={fixedShortcut} />
      </span>
    </div>
  );
}
