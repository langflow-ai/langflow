import ShadTooltip from "@/components/common/shadTooltipComponent";

export default function DragFilesComponent() {
  const image = `url("data:image/svg+xml,%3Csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg'%3E%3Crect width='100%25' height='100%25' fill='none' rx='16' ry='16' stroke='%23FFFFFF' stroke-width='2px' stroke-dasharray='5%2c 5' stroke-dashoffset='0' stroke-linecap='butt'/%3E%3C/svg%3E")`;
  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative flex h-full w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl p-8">
        <h3 className="text-sm font-semibold">Click or drag files here</h3>
        <p className="flex items-center gap-1 text-xs">
          <span>csv, json, pdf</span>
          <ShadTooltip content="txt, md, mdx, csv, json, yaml, yml, xml, html, htm, pdf, docx, py, sh, sql, js, ts, tsx, or zip">
            <span className="cursor-help text-accent-pink-foreground underline">
              +16 more
            </span>
          </ShadTooltip>
          <span className="font-semibold">150 MB</span>
          <span>max</span>
        </p>
        <div
          className="pointer-events-none absolute h-full w-full rounded-2xl bg-placeholder-foreground"
          style={{
            WebkitMaskImage: image,
            maskImage: image,
          }}
        />
      </div>
    </div>
  );
}
