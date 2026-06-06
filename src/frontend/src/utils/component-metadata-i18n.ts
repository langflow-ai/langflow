const KEY_PREFIX = "componentMetadata";

type ComponentMetadataTranslator = (
  key: string,
  options: { defaultValue: string },
) => string;

/**
 * 将后端组件元数据按作用域映射到本地化 key，并在未命中时回退原文。
 * Maps backend component metadata to a scoped locale key and falls back to the original text.
 *
 * @param t - i18next 翻译函数 / i18next translation function.
 * @param scope - 元数据作用域，例如 component、field 或 output / Metadata scope, such as component, field, or output.
 * @param value - 后端返回的原始英文元数据 / Original English metadata returned by the backend.
 * @returns 本地化后的展示文本，未配置时返回原文 / Localized display text, or the original text when no key exists.
 */
export const translateComponentMetadata = (
  t: ComponentMetadataTranslator,
  scope: string,
  value?: string | null,
): string => {
  const fallback = value ?? "";
  const normalized = value?.trim();

  if (!normalized) {
    return fallback;
  }

  const slug = normalized
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, ".")
    .replace(/^\.+|\.+$/g, "");

  if (!slug) {
    return fallback;
  }

  return t(`${KEY_PREFIX}.${scope}.${slug}`, { defaultValue: fallback });
};
