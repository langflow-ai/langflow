import { authorAvatarClasses, authorColor } from "../author-color";

describe("author colors", () => {
  const ids = ["u-alice", "u-bob", "e82364aa-0000", "5724aca7-1111", "x"];

  it("is stable for the same user", () => {
    for (const id of ids) {
      expect(authorAvatarClasses(id)).toBe(authorAvatarClasses(id));
      expect(authorColor(id)).toBe(authorColor(id));
    }
  });

  it("gives a user's highlight the token their avatar's text uses", () => {
    for (const id of ids) {
      const token = authorColor(id).match(/var\(--(.+?)\)/)?.[1];
      expect(authorAvatarClasses(id)).toContain(`text-${token}`);
    }
  });

  it("makes a translucent variant of the same color", () => {
    expect(authorColor("u-alice", 0.1)).toBe(
      authorColor("u-alice").replace(")", ") / 0.1"),
    );
  });
});
