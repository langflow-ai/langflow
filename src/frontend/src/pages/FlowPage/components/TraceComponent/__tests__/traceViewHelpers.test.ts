import {
  downloadJson,
  endOfDay,
  formatCost,
  formatIOPreview,
  formatJsonData,
  formatSpanDetailLatency,
  formatSpanNodeLatency,
  formatTimestamp,
  formatTokens,
  formatTotalCost,
  formatTotalLatency,
  getSpanIcon,
  getSpanStatusLabel,
  getSpanTypeLabel,
  getStatusIconProps,
  getStatusVariant,
  startOfDay,
} from "../traceViewHelpers";

jest.mock("@/utils/dateTime", () => ({
  formatSmartTimestamp: jest.fn(() => "mocked-timestamp"),
}));

describe("traceViewHelpers", () => {
  describe("downloadJson", () => {
    const originalCreateObjectURL = (
      URL as unknown as { createObjectURL?: unknown }
    ).createObjectURL;
    const originalRevokeObjectURL = (
      URL as unknown as { revokeObjectURL?: unknown }
    ).revokeObjectURL;

    beforeEach(() => {
      (URL as unknown as { createObjectURL: unknown }).createObjectURL = jest
        .fn()
        .mockReturnValue("blob:mock-url");
      (URL as unknown as { revokeObjectURL: unknown }).revokeObjectURL = jest
        .fn()
        .mockImplementation(() => undefined);
    });

    afterEach(() => {
      if (originalCreateObjectURL === undefined) {
        delete (URL as unknown as { createObjectURL?: unknown })
          .createObjectURL;
      } else {
        (URL as unknown as { createObjectURL?: unknown }).createObjectURL =
          originalCreateObjectURL;
      }

      if (originalRevokeObjectURL === undefined) {
        delete (URL as unknown as { revokeObjectURL?: unknown })
          .revokeObjectURL;
      } else {
        (URL as unknown as { revokeObjectURL?: unknown }).revokeObjectURL =
          originalRevokeObjectURL;
      }

      jest.restoreAllMocks();
    });

    it("creates a JSON blob and triggers a download", async () => {
      const clickSpy = jest
        .spyOn(HTMLAnchorElement.prototype, "click")
        .mockImplementation(() => undefined);
      const appendSpy = jest.spyOn(document.body, "appendChild");
      const createSpy = (URL as unknown as { createObjectURL: jest.Mock })
        .createObjectURL;
      const revokeSpy = (URL as unknown as { revokeObjectURL: jest.Mock })
        .revokeObjectURL;

      downloadJson("trace.json", { a: 1 });

      expect(createSpy).toHaveBeenCalledTimes(1);
      const blobArg = createSpy.mock.calls[0]?.[0] as Blob;
      expect(blobArg).toBeInstanceOf(Blob);

      const reader = new FileReader();
      const textPromise = new Promise<string>((resolve) => {
        reader.onload = () => resolve(reader.result as string);
      });
      reader.readAsText(blobArg);
      await expect(textPromise).resolves.toBe('{\n  "a": 1\n}');
      expect(blobArg.type).toBe("application/json;charset=utf-8");

      expect(appendSpy).toHaveBeenCalledTimes(1);
      const appended = appendSpy.mock.calls[0]?.[0] as HTMLAnchorElement;
      expect(appended).toBeInstanceOf(HTMLAnchorElement);
      expect(appended.download).toBe("trace.json");
      expect(appended.href).toBe("blob:mock-url");
      expect(clickSpy).toHaveBeenCalledTimes(1);
      expect(revokeSpy).toHaveBeenCalledWith("blob:mock-url");

      const clickOrder = clickSpy.mock.invocationCallOrder[0];
      const revokeOrder = revokeSpy.mock.invocationCallOrder[0];
      expect(revokeOrder).toBeGreaterThan(clickOrder);
    });
  });

  describe("startOfDay", () => {
    it("returns a new Date at 00:00:00.000 and does not mutate input", () => {
      const original = new Date(2026, 1, 27, 15, 30, 45, 123);
      const result = startOfDay(original);

      expect(result).not.toBe(original);
      expect(result.getFullYear()).toBe(original.getFullYear());
      expect(result.getMonth()).toBe(original.getMonth());
      expect(result.getDate()).toBe(original.getDate());
      expect(result.getHours()).toBe(0);
      expect(result.getMinutes()).toBe(0);
      expect(result.getSeconds()).toBe(0);
      expect(result.getMilliseconds()).toBe(0);

      expect(original.getHours()).toBe(15);
      expect(original.getMinutes()).toBe(30);
      expect(original.getSeconds()).toBe(45);
      expect(original.getMilliseconds()).toBe(123);
    });
  });

  describe("endOfDay", () => {
    it("returns a new Date at 23:59:59.999 and does not mutate input", () => {
      const original = new Date(2026, 1, 27, 15, 30, 45, 123);
      const result = endOfDay(original);

      expect(result).not.toBe(original);
      expect(result.getFullYear()).toBe(original.getFullYear());
      expect(result.getMonth()).toBe(original.getMonth());
      expect(result.getDate()).toBe(original.getDate());
      expect(result.getHours()).toBe(23);
      expect(result.getMinutes()).toBe(59);
      expect(result.getSeconds()).toBe(59);
      expect(result.getMilliseconds()).toBe(999);

      expect(original.getHours()).toBe(15);
      expect(original.getMinutes()).toBe(30);
      expect(original.getSeconds()).toBe(45);
      expect(original.getMilliseconds()).toBe(123);
    });
  });

  describe("getSpanIcon", () => {
    it("returns icon names for known types", () => {
      expect(getSpanIcon("agent")).toBe("Bot");
      expect(getSpanIcon("chain")).toBe("Link");
      expect(getSpanIcon("retriever")).toBe("Search");
      expect(getSpanIcon("none")).toBe("");
    });

    it("falls back to Circle for unknown types", () => {
      const unknownType = "unknown" as unknown as Parameters<
        typeof getSpanIcon
      >[0];
      expect(getSpanIcon(unknownType)).toBe("Circle");
    });
  });

  describe("getStatusVariant", () => {
    it("maps status to badge variants", () => {
      expect(getStatusVariant("ok")).toBe("successStatic");
      expect(getStatusVariant("error")).toBe("errorStatic");
      expect(getStatusVariant("unset")).toBe("secondaryStatic");
    });
  });

  describe("getSpanStatusLabel", () => {
    it("maps span statuses to user-facing labels", () => {
      expect(getSpanStatusLabel("ok")).toBe("success");
      expect(getSpanStatusLabel("error")).toBe("error");
      expect(getSpanStatusLabel("unset")).toBe("running");
    });
  });

  describe("formatSpanNodeLatency", () => {
    it("formats ms and seconds", () => {
      expect(formatSpanNodeLatency(450)).toBe("450ms");
      expect(formatSpanNodeLatency(1500)).toBe("1.5s");
    });
  });

  describe("formatTokens", () => {
    it("formats token counts", () => {
      expect(formatTokens(12)).toBe("12");
      expect(formatTokens(1250)).toBe("1.3k");
    });

    it("returns null for empty input", () => {
      expect(formatTokens(undefined)).toBeNull();
      expect(formatTokens(0)).toBeNull();
    });
  });

  describe("getSpanTypeLabel", () => {
    it("returns display labels", () => {
      expect(getSpanTypeLabel("llm")).toBe("LLM");
      expect(getSpanTypeLabel("tool")).toBe("Tool");
      expect(getSpanTypeLabel("none")).toBe("");
    });
  });

  describe("formatCost", () => {
    it("formats costs with thresholds", () => {
      expect(formatCost(undefined)).toBe("$0.00");
      expect(formatCost(0)).toBe("$0.00");
      expect(formatCost(0.005)).toBe("$0.005000");
      expect(formatCost(0.12)).toBe("$0.1200");
    });
  });

  describe("formatSpanDetailLatency", () => {
    it("formats seconds and minutes", () => {
      expect(formatSpanDetailLatency(1500)).toBe("1.50s");
      expect(formatSpanDetailLatency(120000)).toBe("2.00m");
    });
  });

  describe("formatJsonData", () => {
    it("stringifies objects", () => {
      expect(formatJsonData({ a: 1 })).toBe('{\n  "a": 1\n}');
    });

    it("falls back to String on circular data", () => {
      const obj: { self?: unknown } = {};
      obj.self = obj;
      expect(formatJsonData(obj)).toBe("[object Object]");
    });
  });

  describe("formatTotalCost", () => {
    it("formats total cost", () => {
      expect(formatTotalCost(0)).toBe("$0.00");
      expect(formatTotalCost(0.005)).toBe("$0.005000");
      expect(formatTotalCost(0.12)).toBe("$0.1200");
    });
  });

  describe("formatTotalLatency", () => {
    it("formats total latency", () => {
      expect(formatTotalLatency(800)).toBe("800ms");
      expect(formatTotalLatency(1200)).toBe("1.20s");
    });
  });

  describe("formatTimestamp", () => {
    it("delegates to formatSmartTimestamp", () => {
      expect(formatTimestamp("2024-01-01T00:00:00")).toBe("mocked-timestamp");
    });
  });

  describe("formatIOPreview", () => {
    it("returns N/A for null", () => {
      expect(formatIOPreview(null)).toBe("N/A");
    });

    it("truncates string input", () => {
      const value = "a".repeat(200);
      expect(formatIOPreview(value as unknown as Record<string, unknown>)).toBe(
        `${"a".repeat(150)}...`,
      );
    });

    it("returns value from known text fields", () => {
      expect(formatIOPreview({ message: "hello" })).toBe("hello");
    });

    it("returns nested value from known text fields", () => {
      expect(formatIOPreview({ nested: { text: "nested" } })).toBe("nested");
    });

    it("returns Empty for empty object", () => {
      expect(formatIOPreview({})).toBe("Empty");
    });

    it("returns fallback on circular data", () => {
      const obj: { self?: unknown } = {};
      obj.self = obj;
      expect(formatIOPreview(obj)).toBe("[Complex Object]");
    });
  });

  describe("getStatusIconProps", () => {
    it("maps statuses to icons", () => {
      expect(getStatusIconProps("ok")).toEqual({
        colorClass: "text-status-green",
        iconName: "CircleCheck",
        shouldSpin: false,
      });

      expect(getStatusIconProps("error")).toEqual({
        colorClass: "text-status-red",
        iconName: "CircleX",
        shouldSpin: false,
      });

      expect(getStatusIconProps("unset")).toEqual({
        colorClass: "text-muted-foreground",
        iconName: "Loader2",
        shouldSpin: true,
      });
    });
  });
});
