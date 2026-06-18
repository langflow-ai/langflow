// Epic D.5 — D2 render infra. We can't load the real WASM worker in jsdom, so
// we mock @terrastruct/d2 with a fake whose compile/render are individually
// resolvable. That lets us prove the property that matters: the single worker
// never has two requests in flight, so concurrent compileD2() calls can't cross
// their responses (the bug `compileD2`'s serialized queue exists to prevent).

// --- controllable fake D2 worker --------------------------------------------
// Each compile(src) returns a sentinel object tagged with its src; render()
// echoes that tag back as the "svg". If responses ever cross, a call's svg
// won't match the src it asked for.
let inFlight = 0;
let maxInFlight = 0;
const deferred: Array<() => void> = [];

function gated<T>(value: T): Promise<T> {
  inFlight += 1;
  maxInFlight = Math.max(maxInFlight, inFlight);
  return new Promise<T>((resolve) => {
    deferred.push(() => {
      inFlight -= 1;
      resolve(value);
    });
  });
}

const compileSpy = jest.fn((src: string) =>
  gated({ diagram: { __src: src }, renderOptions: {} }),
);
const renderSpy = jest.fn((diagram: { __src: string }) =>
  gated(`<svg data-src="${diagram.__src}"></svg>`),
);

jest.mock("@terrastruct/d2", () => ({
  D2: class {
    compile = compileSpy;
    render = renderSpy;
  },
}));

import { compileD2 } from "../d2/render";

// Let queued microtasks settle so the next gated call registers in `deferred`.
async function flush() {
  for (let i = 0; i < 5; i += 1) await Promise.resolve();
}

// Drain the serialized queue: flush so pending work registers, then release the
// one gated call that's in flight, flush again so the chained render / next
// compile registers, and repeat until nothing is outstanding.
async function drain() {
  await flush();
  let guard = 0;
  while (deferred.length && guard < 1000) {
    deferred.shift()?.();
    await flush();
    guard += 1;
  }
}

beforeEach(() => {
  inFlight = 0;
  maxInFlight = 0;
  deferred.length = 0;
  compileSpy.mockClear();
  renderSpy.mockClear();
});

describe("compileD2", () => {
  it("renders an SVG string for valid source", async () => {
    const p = compileD2("a -> b");
    await drain();
    const result = await p;
    expect(result.error).toBeUndefined();
    expect(result.svg).toBe('<svg data-src="a -> b"></svg>');
  });

  it("short-circuits empty source without touching the worker", async () => {
    const result = await compileD2("   ");
    expect(result.svg).toBe("");
    expect(compileSpy).not.toHaveBeenCalled();
  });

  it("never lets concurrent calls cross responses, and serializes the worker", async () => {
    const sources = ["x -> y", "a.b: hi", "p -> q -> r", "lone", "m -> n"];
    const pending = sources.map((s) => compileD2(s));

    await drain();
    const results = await Promise.all(pending);

    // Every call got back the SVG for ITS OWN source — never "[object Object]"
    // and never another call's diagram.
    results.forEach((r, i) => {
      expect(r.svg).toBe(`<svg data-src="${sources[i]}"></svg>`);
    });

    // The whole point of the queue: the worker only ever saw one request at a
    // time (a compile AND its render), so responses cannot interleave.
    expect(maxInFlight).toBe(1);
    expect(compileSpy).toHaveBeenCalledTimes(sources.length);
    expect(renderSpy).toHaveBeenCalledTimes(sources.length);
  });

  it("survives React StrictMode-style double invocation", async () => {
    // StrictMode double-invokes effects; fire the same compile twice rapidly.
    const a = compileD2("dup -> dup");
    const b = compileD2("dup -> dup");
    await drain();
    expect((await a).svg).toBe('<svg data-src="dup -> dup"></svg>');
    expect((await b).svg).toBe('<svg data-src="dup -> dup"></svg>');
    expect(maxInFlight).toBe(1);
  });

  it("returns the compiler message as an error without breaking the queue", async () => {
    compileSpy.mockImplementationOnce(() => {
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      return new Promise((_, reject) =>
        deferred.push(() => {
          inFlight -= 1;
          reject(new Error("d2: line 1: bad"));
        }),
      );
    });

    const bad = compileD2("@@@");
    const good = compileD2("a -> b");
    await drain();

    expect((await bad).error).toBe("d2: line 1: bad");
    expect((await bad).svg).toBeUndefined();
    // The queue recovered: the next call still resolves to a real SVG.
    expect((await good).svg).toBe('<svg data-src="a -> b"></svg>');
    expect(maxInFlight).toBe(1);
  });
});
