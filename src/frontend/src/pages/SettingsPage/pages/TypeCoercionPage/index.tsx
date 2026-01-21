import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useCoercionStore } from "@/stores/coercionStore";

export default function TypeCoercionPage() {
  const { coercionSettings, setCoercionEnabled, setAutoParse } =
    useCoercionStore();

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex w-full flex-col">
          <h2
            className="flex items-center text-lg font-semibold tracking-tight"
            data-testid="settings_menu_header"
          >
            Type Coercion
            <ForwardedIconComponent
              name="Repeat"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Configure automatic type conversion between Data, Message, and
            DataFrame types.
          </p>
        </div>
      </div>

      <div className="grid gap-6 pb-8">
        {/* Enable Auto-Coercion */}
        <div className="flex flex-col space-y-4 rounded-lg border border-border p-4">
          <div className="flex items-center justify-between">
            <div className="flex flex-col space-y-1">
              <Label
                htmlFor="auto-coercion-toggle"
                className="text-sm font-medium"
              >
                Enable Auto-Coercion
              </Label>
              <p className="text-sm text-muted-foreground">
                Allow Data, Message, and DataFrame types to connect
                interchangeably. When enabled, handles for these types will
                display with a unified violet color.
              </p>
            </div>
            <Switch
              id="auto-coercion-toggle"
              checked={coercionSettings.enabled}
              onCheckedChange={setCoercionEnabled}
              data-testid="auto-coercion-toggle"
            />
          </div>

          {/* Visual indicator */}
          {coercionSettings.enabled && (
            <div className="flex items-center gap-2 rounded-md bg-accent/50 p-3 text-sm">
              <ForwardedIconComponent
                name="Info"
                className="h-4 w-4 text-pink-500"
              />
              <span>
                Coercible types (Data, Message, DataFrame) will now show{" "}
                <span className="font-medium text-pink-500">pink</span> colored
                handles and can connect to each other.
              </span>
            </div>
          )}
        </div>

        {/* Auto Parse (only shown when coercion is enabled) */}
        {coercionSettings.enabled && (
          <div className="flex flex-col space-y-4 rounded-lg border border-border p-4">
            <div className="flex items-center justify-between">
              <div className="flex flex-col space-y-1">
                <Label
                  htmlFor="auto-parse-toggle"
                  className="text-sm font-medium"
                >
                  Auto Parse
                </Label>
                <p className="text-sm text-muted-foreground">
                  Automatically detect and convert JSON/CSV strings when
                  transforming between types. This mirrors the behavior of the
                  Type Convert component&apos;s auto_parse option.
                </p>
              </div>
              <Switch
                id="auto-parse-toggle"
                checked={coercionSettings.autoParse}
                onCheckedChange={setAutoParse}
                data-testid="auto-parse-toggle"
              />
            </div>
          </div>
        )}

        {/* Information Card */}
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-medium">
            <ForwardedIconComponent name="HelpCircle" className="h-4 w-4" />
            How Auto-Coercion Works
          </h3>
          <div className="space-y-2 text-sm text-muted-foreground">
            <p>
              When auto-coercion is enabled, the following conversions happen
              automatically at runtime:
            </p>
            <ul className="list-inside list-disc space-y-1 pl-2">
              <li>
                <strong>Data → Message:</strong> Converts using the{" "}
                <code className="rounded bg-muted px-1">to_message()</code>{" "}
                method
              </li>
              <li>
                <strong>Message → Data:</strong> Extracts text content into a
                Data object
              </li>
              <li>
                <strong>DataFrame → Message:</strong> Converts to a markdown
                table representation
              </li>
              <li>
                <strong>Data → DataFrame:</strong> Creates a single-row
                DataFrame
              </li>
            </ul>
            <p className="mt-3">
              <strong>Note:</strong> Other types (LanguageModel, Tool,
              Embeddings, etc.) remain strictly typed and are not affected by
              this setting.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
