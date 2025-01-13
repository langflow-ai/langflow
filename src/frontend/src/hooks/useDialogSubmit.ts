import { useState } from "react";
import { APIClassType, APITemplateType } from "../types/api";

export type DialogOperation = "create" | "update" | "delete";

interface UseDialogSubmitProps {
  endpoint?: string;
}

export const useDialogSubmit = ({
  endpoint = "/api/v1/dialog",
}: UseDialogSubmitProps = {}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const extractTemplateValues = (template: APITemplateType) => {
    const values: { [key: string]: any } = {};

    Object.entries(template).forEach(([key, field]) => {
      values[key] = field.value;
    });

    return values;
  };

  const submitDialogData = async (
    dialogData: { data: { node: APIClassType } },
    operation: DialogOperation = "create",
  ) => {
    try {
      setLoading(true);
      setError(null);

      const templateValues = extractTemplateValues(
        dialogData.data.node.template,
      );

      const method =
        operation === "create"
          ? "POST"
          : operation === "update"
            ? "PUT"
            : "DELETE";

      const response = await fetch(endpoint, {
        method,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(templateValues),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return {
    submitDialogData,
    loading,
    error,
  };
};
