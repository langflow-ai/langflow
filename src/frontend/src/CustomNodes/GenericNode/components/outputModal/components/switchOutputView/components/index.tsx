export default function ErrorOutput({ value }: { value: string }) {
  return (
    <div className="flex h-full w-full flex-1">
      <textarea
        className="h-full w-full flex-1 resize-none rounded-md border border-border bg-background px-3 py-2 text-sm text-destructive custom-scroll"
        placeholder="Empty"
        value={value}
        readOnly
      />
    </div>
  );
}
