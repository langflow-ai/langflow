import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import useFlowStore from "@/stores/flowStore";
import { INDENT_BASE_REM, INDENT_PER_DEPTH_REM } from "./spanNode.constants";
import {
  formatTokens,
  formatTotalLatency,
  getSpanIcon,
  getStatusIconProps,
} from "./traceViewHelpers";
import type { Span } from "./types";

function buildSpanAriaLabel(span: Span, tokenStr: string | null): string {
  return [
    span.name,
    tokenStr && `${tokenStr} tokens`,
    formatTotalLatency(span.latencyMs),
    span.status,
  ]
    .filter(Boolean)
    .join(", ");
}

interface UseSpanNodeDataParams {
  span: Span;
  depth: number;
  isExpanded: boolean;
}

export function useSpanNodeData({
  span,
  depth,
  isExpanded,
}: UseSpanNodeDataParams) {
  const { t } = useTranslation();
  const nodes = useFlowStore((state) => state.nodes);

  const indentStyle = useMemo(
    () => ({
      paddingLeft: `${depth * INDENT_PER_DEPTH_REM + INDENT_BASE_REM}rem`,
    }),
    [depth],
  );

  const componentIconMap = useMemo(() => {
    const map = new Map<string, string>();
    nodes.forEach((node) => {
      const nodeData = node.data?.node;
      const displayName = nodeData?.display_name;
      const icon = nodeData && "icon" in nodeData ? nodeData.icon : undefined;
      if (displayName && icon) {
        map.set(displayName.toLowerCase(), icon);
      }
    });
    return map;
  }, [nodes]);

  const spanIconName = span.name
    ? (componentIconMap.get(span.name.toLowerCase()) ?? getSpanIcon(span.type))
    : getSpanIcon(span.type);

  const hasChildren = span.children.length > 0;
  const tokenStr = formatTokens(span.tokenUsage?.totalTokens);
  const latency = formatTotalLatency(span.latencyMs);
  const ariaLabel = buildSpanAriaLabel(span, tokenStr);
  const { colorClass, iconName, shouldSpin } = getStatusIconProps(span.status);

  const expandButtonLabel = hasChildren
    ? isExpanded
      ? t("trace.collapseSpan")
      : t("trace.expandSpan")
    : undefined;

  return {
    indentStyle,
    spanIconName,
    hasChildren,
    tokenStr,
    latency,
    ariaLabel,
    colorClass,
    iconName,
    shouldSpin,
    expandButtonLabel,
  };
}
