import type { APIDataType } from "@/types/api";

const OFFICIAL_SLOT_SUFFIX = "@official";

const preferOfficial = (keys: string[]): string | undefined =>
  keys.find((key) => key.endsWith(OFFICIAL_SLOT_SUFFIX)) ?? keys[0];

// Built-in components are keyed in the ``/api/v1/all`` payload by their
// palette name, but extension-bundle components are keyed as
// ``ext:<bundle>:<ClassName>@<slot>`` (see ``classNameFromType``). A
// ``<category>.<name>`` reference, such as a legacy component's
// ``replacement`` hint, is resolved against ``data[category]`` in order:
//   1. the bare key (built-in components);
//   2. ``ext:<category>:<name>@<slot>`` (the reference names the class);
//   3. an entry whose ``name`` matches (the reference names the component's
//      ``name`` attribute, e.g. ``datastax.AstraDB`` for
//      ``AstraDBVectorStoreComponent``; the backend stamps that legacy name
//      onto ext templates).
// The ``@official`` slot wins over any other slot so an ``@extra`` copy never
// shadows the shipped bundle.
export const resolvePaletteKey = (
  data: APIDataType,
  category: string,
  name: string,
): string | undefined => {
  const items = data[category];
  if (!items) return undefined;
  if (Object.hasOwn(items, name)) return name;

  const keys = Object.keys(items);
  const extPrefix = `ext:${category}:${name}@`;
  const byClassName = preferOfficial(
    keys.filter((key) => key.startsWith(extPrefix)),
  );
  if (byClassName) return byClassName;

  return preferOfficial(keys.filter((key) => items[key]?.name === name));
};

export default resolvePaletteKey;
