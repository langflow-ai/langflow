// D2 render infrastructure (Epic D.5).
//
// Lothal stores the diagram as D2 source and renders D2's *own* SVG (the
// click-to-anchor layer in D.6/D.7 reads the base64 element ids D2 bakes into
// each shape/connection class). One render path for every diagram type, no
// xyflow converter in the product.
//
// Two things make this work in the browser:
//   1. Vite must NOT pre-bundle "@terrastruct/d2" — the WASM build embeds its
//      worker + wasm as a base64 blob and esbuild's dep-optimization corrupts
//      it. See `optimizeDeps.exclude` in vite.config.mts.
//   2. D2.js uses a single WASM worker that correlates one request to one
//      response; overlapping compile/render calls get their responses crossed
//      (a render ends up holding a compile object → "[object Object]" instead
//      of an SVG string). So every call is serialized through one queue.

import type { D2 } from "@terrastruct/d2";

// Lazy-load the D2 WASM module on first compile. The browser build embeds the
// worker + wasm as a large base64 blob (~9 MB), so a dynamic import keeps it
// out of the initial app bundle (its own chunk, fetched when a diagram first
// renders) and keeps merely *importing* this module side-effect-free — jest
// pulls the barrel in without ever loading the real WASM.
let instancePromise: Promise<D2> | null = null;
function d2(): Promise<D2> {
  if (!instancePromise) {
    instancePromise = import("@terrastruct/d2").then((m) => new m.D2());
  }
  return instancePromise;
}

/** Result of a single D2 compile + render. Exactly one of svg/error is set. */
export interface D2Compiled {
  /** The rendered SVG markup (empty string for empty source). */
  svg?: string;
  /** The D2 compiler message when the source failed to compile. */
  error?: string;
}

async function doCompile(src: string): Promise<D2Compiled> {
  if (!src.trim()) return { svg: "" };
  try {
    const d = await d2();
    const result = await d.compile(src);
    const svg = await d.render(result.diagram, result.renderOptions);
    return { svg };
  } catch (err) {
    return { error: (err as Error)?.message ?? String(err) };
  }
}

// Serialize every compile/render through one promise chain so the single WASM
// worker never has two requests in flight at once.
let queue: Promise<unknown> = Promise.resolve();

/**
 * Compile D2 source and render it to an SVG string (serialized).
 *
 * Always resolves — a compile failure comes back as `{ error }`, never a
 * rejection — so callers can render the error inline. Concurrent calls are run
 * one at a time in call order; their results never cross.
 */
export function compileD2(src: string): Promise<D2Compiled> {
  const run = queue.then(() => doCompile(src));
  // Keep the chain alive even if a run throws (doCompile never does, but guard
  // against the WASM worker rejecting outright).
  queue = run.catch(() => undefined);
  return run;
}
