export default function DragFilesComponent() {
  return (
    <div className="flex flex-col items-center justify-center">
      <div
        className="flex h-full w-full flex-col items-center justify-center gap-2 rounded-2xl p-8"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg'%3E%3Crect width='100%25' height='100%25' fill='none' rx='16' ry='16' stroke='%23D6D6D6' stroke-width='1' stroke-dasharray='6%2c 6' stroke-dashoffset='0' stroke-linecap='butt'/%3E%3C/svg%3E")`,
          backgroundRepeat: "no-repeat",
          backgroundPosition: "center",
          backgroundSize: "100% 100%",
        }}
      >
        <h3 className="text-sm font-semibold">Click or drag files here</h3>
        <p className="flex items-center gap-1 text-xs">
          <span>csv, json, pdf</span>
          <span className="text-accent-pink-foreground underline">
            +16 more
          </span>
          <span className="font-semibold">150 MB</span>
          <span>max</span>
        </p>
      </div>
    </div>
  );
}
