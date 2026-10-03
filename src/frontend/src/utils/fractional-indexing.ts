/**
 * Fractional indexing: keys that sort between any two keys, so an item's
 * position in a list is a property of the item and moving it is one write.
 *
 * A port of rocicorp's `fractional-indexing`, which implements David
 * Greenspan's scheme ("Implementing Fractional Indexing", CC0, no rights
 * reserved). Keep it identical to the reference algorithm: the backend has its
 * own port, and both must produce the same keys.
 *
 * A key is an integer part followed by an optional fraction. The integer
 * part's first character gives its length: `a`..`z` for 2..27 characters
 * (non-negative integers), `A`..`Z` for 27..2 characters (negative integers).
 * Digits are base 62, `0-9A-Za-z`, in ASCII order, so keys compare as plain
 * strings. A fraction never ends in `0`.
 */

export const BASE_62_DIGITS =
  "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

// `a` may be empty, `b` is null or non-empty, and `a < b` when `b` is set.
// Neither has trailing zeros.
function midpoint(a: string, b: string | null, digits: string): string {
  const zero = digits[0];
  if (b !== null && a >= b) {
    throw new Error(`${a} >= ${b}`);
  }
  if (a.slice(-1) === zero || (b && b.slice(-1) === zero)) {
    throw new Error("trailing zero");
  }
  if (b) {
    // Remove the longest common prefix, padding `a` with zeros as we go. `b`
    // needs no padding: it cannot end before `a` inside the common prefix.
    let n = 0;
    while ((a[n] || zero) === b[n]) {
      n++;
    }
    if (n > 0) {
      return b.slice(0, n) + midpoint(a.slice(n), b.slice(n), digits);
    }
  }
  // The first digits (or the lack of a digit) differ.
  const digitA = a ? digits.indexOf(a[0]) : 0;
  const digitB = b !== null ? digits.indexOf(b[0]) : digits.length;
  if (digitB - digitA > 1) {
    const midDigit = Math.round(0.5 * (digitA + digitB));
    return digits[midDigit];
  }
  // The first digits are consecutive.
  if (b && b.length > 1) {
    return b.slice(0, 1);
  }
  // `b` is null or a single digit, and `a`'s first digit is the one before
  // it (or the last digit when `b` is null): midpoint("49", "5") is
  // "4" + midpoint("9", null), which becomes "495".
  return digits[digitA] + midpoint(a.slice(1), null, digits);
}

function getIntegerLength(head: string): number {
  if (head >= "a" && head <= "z") {
    return head.charCodeAt(0) - "a".charCodeAt(0) + 2;
  }
  if (head >= "A" && head <= "Z") {
    return "Z".charCodeAt(0) - head.charCodeAt(0) + 2;
  }
  throw new Error(`invalid order key head: ${head}`);
}

function validateInteger(int: string): void {
  if (int.length !== getIntegerLength(int[0])) {
    throw new Error(`invalid integer part of order key: ${int}`);
  }
}

function getIntegerPart(key: string): string {
  const integerPartLength = getIntegerLength(key[0]);
  if (integerPartLength > key.length) {
    throw new Error(`invalid order key: ${key}`);
  }
  return key.slice(0, integerPartLength);
}

function validateOrderKey(key: string, digits: string): void {
  if (key === `A${digits[0].repeat(26)}`) {
    throw new Error(`invalid order key: ${key}`);
  }
  // getIntegerPart throws when the head is bad or the key too short.
  const i = getIntegerPart(key);
  const f = key.slice(i.length);
  if (f.slice(-1) === digits[0]) {
    throw new Error(`invalid order key: ${key}`);
  }
}

// Null past the largest integer.
function incrementInteger(x: string, digits: string): string | null {
  validateInteger(x);
  const [head, ...digs] = x.split("");
  let carry = true;
  for (let i = digs.length - 1; carry && i >= 0; i--) {
    const d = digits.indexOf(digs[i]) + 1;
    if (d === digits.length) {
      digs[i] = digits[0];
    } else {
      digs[i] = digits[d];
      carry = false;
    }
  }
  if (carry) {
    if (head === "Z") {
      return `a${digits[0]}`;
    }
    if (head === "z") {
      return null;
    }
    const h = String.fromCharCode(head.charCodeAt(0) + 1);
    if (h > "a") {
      digs.push(digits[0]);
    } else {
      digs.pop();
    }
    return h + digs.join("");
  }
  return head + digs.join("");
}

// Null past the smallest integer.
function decrementInteger(x: string, digits: string): string | null {
  validateInteger(x);
  const [head, ...digs] = x.split("");
  let borrow = true;
  for (let i = digs.length - 1; borrow && i >= 0; i--) {
    const d = digits.indexOf(digs[i]) - 1;
    if (d === -1) {
      digs[i] = digits.slice(-1);
    } else {
      digs[i] = digits[d];
      borrow = false;
    }
  }
  if (borrow) {
    if (head === "a") {
      return `Z${digits.slice(-1)}`;
    }
    if (head === "A") {
      return null;
    }
    const h = String.fromCharCode(head.charCodeAt(0) - 1);
    if (h < "Z") {
      digs.push(digits.slice(-1));
    } else {
      digs.pop();
    }
    return h + digs.join("");
  }
  return head + digs.join("");
}

/** Whether `key` is a well-formed order key. */
export function isValidOrderKey(
  key: unknown,
  digits: string = BASE_62_DIGITS,
): key is string {
  if (typeof key !== "string" || key.length === 0) return false;
  try {
    validateOrderKey(key, digits);
  } catch {
    return false;
  }
  for (const char of key.slice(1)) {
    if (!digits.includes(char)) return false;
  }
  return true;
}

/**
 * A key that sorts after `a` and before `b`. Null `a` means the start of the
 * list and null `b` its end; when both are set, `a < b`.
 */
export function generateKeyBetween(
  a: string | null,
  b: string | null,
  digits: string = BASE_62_DIGITS,
): string {
  if (a !== null) {
    validateOrderKey(a, digits);
  }
  if (b !== null) {
    validateOrderKey(b, digits);
  }
  if (a !== null && b !== null && a >= b) {
    throw new Error(`${a} >= ${b}`);
  }
  if (a === null) {
    if (b === null) {
      return `a${digits[0]}`;
    }
    const ib = getIntegerPart(b);
    const fb = b.slice(ib.length);
    if (ib === `A${digits[0].repeat(26)}`) {
      return ib + midpoint("", fb, digits);
    }
    if (ib < b) {
      return ib;
    }
    const res = decrementInteger(ib, digits);
    if (res === null) {
      throw new Error("cannot decrement any more");
    }
    return res;
  }

  if (b === null) {
    const ia = getIntegerPart(a);
    const fa = a.slice(ia.length);
    const i = incrementInteger(ia, digits);
    return i === null ? ia + midpoint(fa, null, digits) : i;
  }

  const ia = getIntegerPart(a);
  const fa = a.slice(ia.length);
  const ib = getIntegerPart(b);
  const fb = b.slice(ib.length);
  if (ia === ib) {
    return ia + midpoint(fa, fb, digits);
  }
  const i = incrementInteger(ia, digits);
  if (i === null) {
    throw new Error("cannot increment any more");
  }
  if (i < b) {
    return i;
  }
  return ia + midpoint(fa, null, digits);
}

/**
 * `n` distinct keys between `a` and `b`, in order. With both ends open they
 * are `a0`, `a1`, ...; with one end open, consecutive integers; otherwise
 * short keys spread between the two.
 */
export function generateNKeysBetween(
  a: string | null,
  b: string | null,
  n: number,
  digits: string = BASE_62_DIGITS,
): string[] {
  if (n === 0) {
    return [];
  }
  if (n === 1) {
    return [generateKeyBetween(a, b, digits)];
  }
  if (b === null) {
    let c = generateKeyBetween(a, b, digits);
    const result = [c];
    for (let i = 0; i < n - 1; i++) {
      c = generateKeyBetween(c, b, digits);
      result.push(c);
    }
    return result;
  }
  if (a === null) {
    let c = generateKeyBetween(a, b, digits);
    const result = [c];
    for (let i = 0; i < n - 1; i++) {
      c = generateKeyBetween(a, c, digits);
      result.push(c);
    }
    result.reverse();
    return result;
  }
  const mid = Math.floor(n / 2);
  const c = generateKeyBetween(a, b, digits);
  return [
    ...generateNKeysBetween(a, c, mid, digits),
    c,
    ...generateNKeysBetween(c, b, n - mid - 1, digits),
  ];
}
