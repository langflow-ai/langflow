export function buildContent(value: string) {
  const htmlContent = (
    <div className="w-[200px]">
      <span>{value != null && value != "" ? value : "None"}</span>
    </div>
  );
  return htmlContent;
}

export default buildContent;
