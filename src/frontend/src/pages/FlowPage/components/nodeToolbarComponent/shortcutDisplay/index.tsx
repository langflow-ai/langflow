import RenderIcons from "@/components/renderIconComponent";

export default function ShortcutDisplay({
  name,
  shortcut,
}: {
  name: string;
  shortcut: string;
}): JSX.Element {
  let hasShift: boolean = false;
  const fixedShortcut = shortcut?.split("+");
  fixedShortcut.forEach((key) => {
    if (key.toLowerCase().includes("shift")) {
      hasShift = true;
    }
  });
  const filteredShortcut = fixedShortcut.filter(
    (key) => !key.toLowerCase().includes("shift"),
  );
  let shortcutWPlus: string[] = [];
  if (!hasShift) shortcutWPlus = filteredShortcut.join("+").split(" ");
  return (
    <div className="flex justify-center">
      <span> {name} </span>
      <span
        className={`ml-3 flex items-center rounded-sm bg-muted px-1.5 py-[0.1em] text-lg text-muted-foreground`}
      >
        <RenderIcons
          hasShift={hasShift}
          filteredShortcut={filteredShortcut}
          shortcutWPlus={shortcutWPlus}
        />
      </span>
    </div>
  );
}
