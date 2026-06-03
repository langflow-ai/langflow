import { cloneDeep } from "lodash";
import type { NodeFieldPath } from "@/types/flow-operations";

export type PathLookupResult =
  | { exists: true; value: unknown }
  | { exists: false; value?: undefined };

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isArrayIndex(segment: unknown): segment is number {
  return Number.isInteger(segment);
}

function resolveChild(container: unknown, segment: string | number): unknown {
  if (Array.isArray(container)) {
    if (!isArrayIndex(segment) || segment < 0 || segment >= container.length) {
      throw new Error("array path segment must be an existing integer index");
    }
    return container[segment];
  }
  if (isObject(container)) {
    if (typeof segment !== "string") {
      throw new Error("object path segment must be a string");
    }
    if (!Object.hasOwn(container, segment)) {
      throw new Error("parent path does not exist");
    }
    return container[segment];
  }
  throw new Error("parent path must resolve through objects or arrays");
}

function resolveParent(
  target: unknown,
  path: NodeFieldPath,
): { parent: unknown; key: string | number } {
  if (path.length === 0) {
    throw new Error("path must not be empty");
  }
  let parent = target;
  for (const segment of path.slice(0, -1)) {
    parent = resolveChild(parent, segment);
  }
  return { parent, key: path[path.length - 1]! };
}

export function getValueAtPath(
  target: unknown,
  path: NodeFieldPath,
): PathLookupResult {
  const { parent, key } = resolveParent(target, path);
  if (Array.isArray(parent)) {
    if (!isArrayIndex(key) || key < 0 || key >= parent.length) {
      return { exists: false };
    }
    return { exists: true, value: cloneDeep(parent[key]) };
  }
  if (isObject(parent)) {
    if (typeof key !== "string" || !Object.hasOwn(parent, key)) {
      return { exists: false };
    }
    return { exists: true, value: cloneDeep(parent[key]) };
  }
  return { exists: false };
}

export function setValueAtPath(
  target: unknown,
  path: NodeFieldPath,
  value: unknown,
): void {
  const { parent, key } = resolveParent(target, path);
  if (Array.isArray(parent)) {
    if (!isArrayIndex(key) || key < 0 || key >= parent.length) {
      throw new Error("array path segment must be an existing integer index");
    }
    parent[key] = cloneDeep(value);
    return;
  }
  if (isObject(parent)) {
    if (typeof key !== "string") {
      throw new Error("object path segment must be a string");
    }
    parent[key] = cloneDeep(value);
    return;
  }
  throw new Error("parent path must resolve to an object or array");
}

export function deleteValueAtPath(target: unknown, path: NodeFieldPath): void {
  const { parent, key } = resolveParent(target, path);
  if (!isObject(parent)) {
    throw new Error("delete only supports object properties");
  }
  if (typeof key !== "string") {
    throw new Error("delete path segment must be an object property");
  }
  delete parent[key];
}
