import noDataIcon from "./no-data-icon";
import noDataText from "./no-data-text";

export default function noDataTemplate() {
  return `
  <div class="z-50 flex h-screen w-screen items-center justify-center bg-foreground bg-opacity-50">
    <div class="flex h-screen w-screen flex bg-background text-start shadow-lg">
      <div class="m-auto grid w-1/2 justify-center gap-5 text-center">
        <div class="p-8 flex flex-col justify-between rounded-lg border bg-muted text-card-foreground shadow-sm transition-all hover:shadow-lg">
          <div class="flex space-x-2 p-4 items-center justify-center">
            <div class="m-auto">
              ${noDataIcon()}
            </div>
            ${noDataText}
          </div>
        </div>
      </div>
    </div>
  </div>
  `;
}
