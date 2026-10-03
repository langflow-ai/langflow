import {
  generateKeyBetween,
  generateNKeysBetween,
  isValidOrderKey,
} from "../fractional-indexing";

const SMALLEST_INTEGER = `A${"0".repeat(26)}`;
const LARGEST_INTEGER = `z${"z".repeat(26)}`;

describe("generateKeyBetween", () => {
  it.each([
    [null, null, "a0"],
    [null, "a0", "Zz"],
    [null, "Zz", "Zy"],
    ["a0", null, "a1"],
    ["a1", null, "a2"],
    ["a0", "a1", "a0V"],
    ["a1", "a2", "a1V"],
    ["a0V", "a1", "a0l"],
    ["Zz", "a0", "ZzV"],
    ["Zz", "a1", "a0"],
    [null, "Y00", "Xzzz"],
    ["bzz", null, "c000"],
    ["a0", "a0V", "a0G"],
    ["a0", "a0G", "a08"],
    ["b125", "b129", "b127"],
    ["a0", "a1V", "a1"],
    ["Zz", "a01", "a0"],
    [null, "a0V", "a0"],
    [null, "b999", "b99"],
    [null, `${SMALLEST_INTEGER}1`, `${SMALLEST_INTEGER}0V`],
    [`z${"z".repeat(25)}y`, null, LARGEST_INTEGER],
    [LARGEST_INTEGER, null, `${LARGEST_INTEGER}V`],
  ])("between %s and %s is %s", (a, b, expected) => {
    expect(generateKeyBetween(a, b)).toBe(expected);
  });

  it.each([
    [null, SMALLEST_INTEGER, `invalid order key: ${SMALLEST_INTEGER}`],
    ["a00", null, "invalid order key: a00"],
    ["a00", "a1", "invalid order key: a00"],
    ["0", "1", "invalid order key head: 0"],
    ["a1", "a0", "a1 >= a0"],
    ["a1", "a1", "a1 >= a1"],
  ])("rejects %s and %s", (a, b, message) => {
    expect(() => generateKeyBetween(a, b)).toThrow(message);
  });

  it("keeps sorting between repeated inserts at the same spot", () => {
    let low = "a0";
    const high = "a1";
    for (let i = 0; i < 50; i++) {
      const key = generateKeyBetween(low, high);
      expect(key > low && key < high).toBe(true);
      low = key;
    }
  });
});

describe("generateNKeysBetween", () => {
  it.each([
    [null, null, 5, "a0 a1 a2 a3 a4"],
    ["a4", null, 10, "a5 a6 a7 a8 a9 aA aB aC aD aE"],
    [null, "a0", 5, "Zv Zw Zx Zy Zz"],
    [
      "a0",
      "a2",
      20,
      "a04 a08 a0G a0K a0O a0V a0Z a0d a0l a0t a1 a14 a18 a1G a1O a1V a1Z a1d a1l a1t",
    ],
    ["a1", "a2", 2, "a1G a1V"],
  ])("%s .. %s, %s keys", (a, b, n, expected) => {
    expect(generateNKeysBetween(a, b, n).join(" ")).toBe(expected);
  });

  it("returns nothing for zero keys", () => {
    expect(generateNKeysBetween(null, null, 0)).toEqual([]);
  });

  it("returns sorted, distinct keys strictly inside the bounds", () => {
    const keys = generateNKeysBetween("a0", "a0V", 37);
    expect(new Set(keys).size).toBe(37);
    expect([...keys].sort()).toEqual(keys);
    expect(keys[0] > "a0").toBe(true);
    expect(keys[keys.length - 1] < "a0V").toBe(true);
  });
});

describe("isValidOrderKey", () => {
  it.each(["a0", "Zz", "a0V", "b125", "c000"])("accepts %s", (key) => {
    expect(isValidOrderKey(key)).toBe(true);
  });

  it.each(["", "a", "a00", "0", "a0!", SMALLEST_INTEGER, null, 3])(
    "rejects %s",
    (key) => {
      expect(isValidOrderKey(key)).toBe(false);
    },
  );
});
