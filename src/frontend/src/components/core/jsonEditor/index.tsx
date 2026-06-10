import { jsonquery } from "@jsonquerylang/jsonquery";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  type Content,
  createJSONEditor,
  type MenuItem,
  type Mode,
  type JsonEditor as VanillaJsonEditor,
} from "vanilla-jsoneditor";
import useAlertStore from "../../../stores/alertStore";
import { cn } from "../../../utils/utils";
import { useMenuCustomization } from "./useMenuCustomization";

interface JsonEditorProps {
  data?: Content;
  onChange?: (data: Content) => void;
  readOnly?: boolean;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  options?: any;
  jsonRef?: React.MutableRefObject<VanillaJsonEditor | null>;
  width?: string;
  height?: string;
  className?: string;
  setFilter?: (filter: string) => void;
  allowFilter?: boolean;
  initialFilter?: string;
}

const JsonEditor = ({
  data = { json: {} },
  onChange,
  readOnly,
  jsonRef,
  options = {},
  width = "100%",
  height = "400px",
  className,
  setFilter,
  allowFilter = false,
  initialFilter,
}: JsonEditorProps) => {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const jsonEditorRef = useRef<VanillaJsonEditor | null>(null);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const newRef = jsonRef ?? jsonEditorRef;
  const [transformQuery, setTransformQuery] = useState(initialFilter ?? "");
  const [originalData, setOriginalData] = useState(data);
  const [isFiltered, setIsFiltered] = useState(false);
  const [_showSuccess, setShowSuccess] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const { customizeMenu } = useMenuCustomization(setSuccessData, setErrorData);

  // Apply initial filter when component mounts
  useEffect(() => {
    if (initialFilter && newRef.current) {
      setTransformQuery(initialFilter);
      handleTransform(true);
    }
  }, [initialFilter, newRef.current]);

  // biome-ignore lint/suspicious/noExplicitAny: legacy
  const isValidResult = (result: any): boolean => {
    // Only allow objects and arrays
    return (
      result !== null &&
      (Array.isArray(result) ||
        (typeof result === "object" && !Array.isArray(result)))
    );
  };

  // biome-ignore lint/suspicious/noExplicitAny: legacy
  const applyFilter = (filtered: { json: any }, query: string) => {
    onChange?.(filtered);
    setFilter?.(query.trim());
    setShowSuccess(true);
    setTimeout(() => {
      setShowSuccess(false);
    }, 5000);
  };

  const handleTransform = (isInitial = false) => {
    if (!newRef.current) return;

    // If query is empty, act as reset
    if (!transformQuery.trim()) {
      handleReset();
      return;
    }

    try {
      // Always start with original data for transformation
      const json =
        "json" in originalData
          ? originalData.json
          : JSON.parse(originalData.text!);

      // Try JSONQuery first
      try {
        const result = jsonquery(json, transformQuery);
        if (result !== undefined) {
          // Validate that result is a JSON object or array
          if (isValidResult(result)) {
            try {
              JSON.stringify(result); // Still check JSON serializability
              const filteredContent = { json: result };
              newRef.current.set(filteredContent);
              if (isFiltered && !isInitial) {
                // Apply the filter
                applyFilter(filteredContent, transformQuery.trim());
              } else {
                // Just preview the filter
                setIsFiltered(true);
              }
              return;
            } catch (_jsonError) {
              setErrorData({
                title: t("jsonEditor.invalidResult"),
                list: [
                  "The filtered result contains values that cannot be serialized to JSON",
                ],
              });
              return;
            }
          } else {
            setErrorData({
              title: t("jsonEditor.invalidResult"),
              list: [
                "The filtered result must be a JSON object or array, not a primitive value",
              ],
            });
            return;
          }
        }
      } catch (jsonQueryError) {
        // If JSONQuery fails, continue with our path-based method
        console.error(
          "JSONQuery parsing failed, falling back to path-based method:",
          jsonQueryError,
        );
      }

      // Fallback to our path-based method
      const normalizedQuery = transformQuery.replace(/\[/g, ".[");
      const path = normalizedQuery.trim().split(".").filter(Boolean);
      let result = json;

      for (const key of path) {
        if (result === undefined || result === null) {
          setErrorData({
            title: t("jsonEditor.invalidPath"),
            list: [`Path '${transformQuery}' led to undefined or null value`],
          });
          return;
        }
        if (Array.isArray(result)) {
          // Handle array access with [index] notation
          const indexMatch = key.match(/\[(\d+)\]/);
          if (indexMatch) {
            const index = parseInt(indexMatch[1]);
            if (index >= result.length) {
              setErrorData({
                title: t("jsonEditor.invalidArrayIndex"),
                list: [
                  `Index ${index} is out of bounds for array of length ${result.length}`,
                ],
              });
              return;
            }
            result = result[index];
            continue;
          }
          // Apply operation to all array items
          result = result
            .map((item) => {
              if (!(key in item)) {
                setErrorData({
                  title: t("jsonEditor.invalidProperty"),
                  list: [`Property '${key}' does not exist in array items`],
                });
                return undefined;
              }
              return item[key];
            })
            .filter((item) => item !== undefined);
        } else {
          if (!(key in result)) {
            setErrorData({
              title: t("jsonEditor.invalidProperty"),
              list: [`Property '${key}' does not exist in object`],
            });
            return;
          }
          result = result[key];
        }
      }

      if (result !== undefined) {
        // Validate that result is a JSON object or array
        if (isValidResult(result)) {
          try {
            JSON.stringify(result); // Still check JSON serializability
            const filteredContent = { json: result };
            newRef.current.set(filteredContent);

            if (isFiltered && !isInitial) {
              // Apply the filter
              applyFilter(filteredContent, transformQuery.trim());
            } else {
              // Just preview the filter
              setIsFiltered(true);
            }
            return;
          } catch (_jsonError) {
            setErrorData({
              title: t("jsonEditor.invalidResult"),
              list: [
                "The filtered result contains values that cannot be serialized to JSON",
              ],
            });
          }
        } else {
          setErrorData({
            title: t("jsonEditor.invalidResult"),
            list: [
              "The filtered result must be a JSON object or array, not a primitive value",
            ],
          });
        }
      } else {
        setErrorData({
          title: t("jsonEditor.invalidResult"),
          list: [t("errors.transformUndefined")],
        });
      }
    } catch (error) {
      console.error("Error applying transform:", error);
      setErrorData({
        title: t("jsonEditor.transformError"),
        list: [(error as Error).message],
      });
    }
  };

  const handleReset = () => {
    if (!newRef.current) return;
    newRef.current.set(originalData);
    onChange?.(originalData);
    setTransformQuery("");
    setFilter?.("");
    setIsFiltered(false);
    setShowSuccess(false);
  };

  const _handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleTransform();
    }
  };

  const getFilteredContent = (
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    sourceJson: any,
    query: string,
    // biome-ignore lint/suspicious/noExplicitAny: legacy
  ): { json: any } | undefined => {
    // Try JSONQuery first
    try {
      const result = jsonquery(sourceJson, query);
      if (result !== undefined && isValidResult(result)) {
        try {
          JSON.stringify(result); // Check serializability
          return { json: result };
        } catch {
          return undefined;
        }
      }
    } catch (jsonQueryError) {
      console.error(
        "JSONQuery parsing failed, falling back to path-based method:",
        jsonQueryError,
      );
    }

    // Fallback to path-based method
    try {
      const normalizedQuery = query.replace(/\[/g, ".[");
      const path = normalizedQuery.trim().split(".").filter(Boolean);
      let result = sourceJson;

      for (const key of path) {
        if (result === undefined || result === null) return undefined;
        if (Array.isArray(result)) {
          const indexMatch = key.match(/\[(\d+)\]/);
          if (indexMatch) {
            const index = parseInt(indexMatch[1]);
            if (index >= result.length) return undefined;
            result = result[index];
            continue;
          }
          result = result
            .map((item) => (key in item ? item[key] : undefined))
            .filter((item) => item !== undefined);
        } else {
          if (!(key in result)) return undefined;
          result = result[key];
        }
      }

      if (result !== undefined && isValidResult(result)) {
        try {
          JSON.stringify(result);
          return { json: result };
        } catch {
          return undefined;
        }
      }
    } catch {
      return undefined;
    }
    return undefined;
  };

  useEffect(() => {
    if (!containerRef.current) return;

    let initialContent = data;
    if (initialFilter?.trim()) {
      try {
        const json = "json" in data ? data.json : JSON.parse(data.text!);
        const filtered = getFilteredContent(json, initialFilter);
        if (filtered) {
          initialContent = filtered;
        }
      } catch (error) {
        console.error("Error applying initial filter:", error);
      }
    }

    // Ensure the container has the correct dimensions before creating the editor
    if (containerRef.current) {
      containerRef.current.style.width = width;
      containerRef.current.style.height = height;
    }

    let editorInstance: VanillaJsonEditor | null = null;

    const editor = createJSONEditor({
      target: containerRef.current,
      props: {
        ...options,
        navigationBar: false,
        mode: "text",
        content: initialContent,
        readOnly,
        onChange: (content) => {
          onChange?.(content);
        },
        onRenderMenu: (
          items: MenuItem[],
          context: { mode: Mode; modal: boolean; readOnly: boolean },
        ) => {
          // Use a getter function that will return the editor when called
          return customizeMenu(items, context, () => editorInstance);
        },
      },
    });

    // Set the editor instance immediately after creation
    editorInstance = editor;

    setTimeout(() => editor.focus(), 100);

    newRef.current = editor;
    setOriginalData(data);

    return () => {
      if (newRef.current) {
        newRef.current.destroy();
      }
    };
  }, []);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* {allowFilter && (
        <div className="mb-2 flex shrink-0 gap-2">
          <Input
            placeholder={t("jsonEditor.pathPlaceholder")}
            value={transformQuery}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            className="font-mono text-sm"
          />
          <Button
            onClick={() => handleTransform()}
            variant="primary"
            size="sm"
            className={cn(
              "min-w-[60px] whitespace-nowrap",
              showSuccess && "!bg-accent-emerald-foreground hover:!bg-accent-emerald-foreground/90",
            )}
          >
            {showSuccess ? (
              <Check className="h-4 w-4" />
            ) : isFiltered ? (
              "Apply"
            ) : (
              "Filter"
            )}
          </Button>
          <Button
            onClick={handleReset}
            variant="outline"
            size="sm"
            className="whitespace-nowrap"
          >
            Clear
          </Button>
        </div>
      )} */}
      <div className="relative h-full min-h-0 flex-1">
        <div ref={containerRef} className={cn("!h-full w-full", className)} />
      </div>
    </div>
  );
};

export default JsonEditor;
