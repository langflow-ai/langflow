import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { DecisionFormatters } from "./decision-outcome";

/** Probabilities as percentages and scores as plain numbers, in the UI's locale. */
export function useDecisionFormatters(): DecisionFormatters {
  const { i18n } = useTranslation();
  const locale = i18n.language;
  return useMemo(() => {
    const percent = new Intl.NumberFormat(locale, {
      style: "percent",
      maximumFractionDigits: 1,
    });
    const number = new Intl.NumberFormat(locale, {
      maximumFractionDigits: 2,
    });
    return {
      percent: (value: number) => percent.format(value),
      number: (value: number) => number.format(value),
    };
  }, [locale]);
}
