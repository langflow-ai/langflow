import { act, renderHook } from "@testing-library/react";

// Mock lodash uniqueId to make tests predictable
let idCounter = 0;
jest.mock("lodash", () => ({
  uniqueId: jest.fn(() => `test-id-${++idCounter}`),
}));

// Mock customStringify utility
jest.mock("@/utils/reactflowUtils", () => ({
  customStringify: jest.fn((obj) => JSON.stringify(obj)),
}));

import type { AlertItemType } from "@/types/alerts";
import useAlertStore from "../alertStore";

describe("useAlertStore", () => {
  beforeEach(() => {
    // Reset the ID counter before each test
    idCounter = 0;

    // Reset the store state by calling the store directly
    useAlertStore.setState({
      errorData: { title: "", list: [] },
      noticeData: { title: "", link: "" },
      successData: { title: "" },
      notificationCenter: false,
      notificationList: [],
      tempNotificationList: [],
    });
  });

  describe("initial state", () => {
    it("should have correct initial state", () => {
      const { result } = renderHook(() => useAlertStore());

      expect(result.current.errorData).toEqual({ title: "", list: [] });
      expect(result.current.noticeData).toEqual({ title: "", link: "" });
      expect(result.current.successData).toEqual({ title: "" });
      expect(result.current.notificationCenter).toBe(false);
      expect(result.current.notificationList).toEqual([]);
      expect(result.current.tempNotificationList).toEqual([]);
    });
  });

  describe("setErrorData", () => {
    it("should set error data with title only", () => {
      const { result } = renderHook(() => useAlertStore());
      const errorData = { title: "Test error" };

      act(() => {
        result.current.setErrorData(errorData);
      });

      expect(result.current.errorData).toEqual(errorData);
    });

    it("should set error data with title and list", () => {
      const { result } = renderHook(() => useAlertStore());
      const errorData = { title: "Test error", list: ["Error 1", "Error 2"] };

      act(() => {
        result.current.setErrorData(errorData);
      });

      expect(result.current.errorData).toEqual(errorData);
    });

    it("should add error notification to history and temp list", () => {
      const { result } = renderHook(() => useAlertStore());
      const errorData = { title: "Test error", list: ["Error 1"] };

      act(() => {
        result.current.setErrorData(errorData);
      });

      expect(result.current.notificationList).toHaveLength(1);
      expect(result.current.notificationList[0]).toMatchObject({
        type: "error",
        title: "Test error",
        list: ["Error 1"],
        id: "test-id-1",
      });

      expect(result.current.tempNotificationList).toHaveLength(1);
      expect(result.current.tempNotificationList[0]).toMatchObject({
        type: "error",
        title: "Test error",
        list: ["Error 1"],
        id: "test-id-2",
      });
    });

    it("should not set error data when title is empty", () => {
      const { result } = renderHook(() => useAlertStore());

      act(() => {
        result.current.setErrorData({ title: "" });
      });

      expect(result.current.errorData).toEqual({ title: "", list: [] });
      expect(result.current.notificationList).toHaveLength(0);
      expect(result.current.tempNotificationList).toHaveLength(0);
    });
  });

  describe("setNoticeData", () => {
    it("should set notice data with title only", () => {
      const { result } = renderHook(() => useAlertStore());
      const noticeData = { title: "Test notice" };

      act(() => {
        result.current.setNoticeData(noticeData);
      });

      expect(result.current.noticeData).toEqual(noticeData);
    });

    it("should set notice data with title and link", () => {
      const { result } = renderHook(() => useAlertStore());
      const noticeData = { title: "Test notice", link: "https://example.com" };

      act(() => {
        result.current.setNoticeData(noticeData);
      });

      expect(result.current.noticeData).toEqual(noticeData);
    });

    it("should add notice notification to history and temp list", () => {
      const { result } = renderHook(() => useAlertStore());
      const noticeData = { title: "Test notice", link: "https://example.com" };

      act(() => {
        result.current.setNoticeData(noticeData);
      });

      expect(result.current.notificationList).toHaveLength(1);
      expect(result.current.notificationList[0]).toMatchObject({
        type: "notice",
        title: "Test notice",
        link: "https://example.com",
        id: "test-id-1",
      });

      expect(result.current.tempNotificationList).toHaveLength(1);
      expect(result.current.tempNotificationList[0]).toMatchObject({
        type: "notice",
        title: "Test notice",
        link: "https://example.com",
        id: "test-id-2",
      });
    });

    it("should not set notice data when title is empty", () => {
      const { result } = renderHook(() => useAlertStore());

      act(() => {
        result.current.setNoticeData({ title: "" });
      });

      expect(result.current.noticeData).toEqual({ title: "", link: "" });
      expect(result.current.notificationList).toHaveLength(0);
      expect(result.current.tempNotificationList).toHaveLength(0);
    });
  });

  describe("setSuccessData", () => {
    it("should set success data", () => {
      const { result } = renderHook(() => useAlertStore());
      const successData = { title: "Test success" };

      act(() => {
        result.current.setSuccessData(successData);
      });

      expect(result.current.successData).toEqual(successData);
    });

    it("should add success notification to history and temp list", () => {
      const { result } = renderHook(() => useAlertStore());
      const successData = { title: "Test success" };

      act(() => {
        result.current.setSuccessData(successData);
      });

      expect(result.current.notificationList).toHaveLength(1);
      expect(result.current.notificationList[0]).toMatchObject({
        type: "success",
        title: "Test success",
        id: "test-id-1",
      });

      expect(result.current.tempNotificationList).toHaveLength(1);
      expect(result.current.tempNotificationList[0]).toMatchObject({
        type: "success",
        title: "Test success",
        id: "test-id-2",
      });
    });

    it("should not set success data when title is empty", () => {
      const { result } = renderHook(() => useAlertStore());

      act(() => {
        result.current.setSuccessData({ title: "" });
      });

      expect(result.current.successData).toEqual({ title: "" });
      expect(result.current.notificationList).toHaveLength(0);
      expect(result.current.tempNotificationList).toHaveLength(0);
    });
  });

  describe("notification center", () => {
    it("should set notification center state", () => {
      const { result } = renderHook(() => useAlertStore());

      act(() => {
        result.current.setNotificationCenter(true);
      });

      expect(result.current.notificationCenter).toBe(true);

      act(() => {
        result.current.setNotificationCenter(false);
      });

      expect(result.current.notificationCenter).toBe(false);
    });

    it("should open notification center when adding notifications to history", () => {
      const { result } = renderHook(() => useAlertStore());

      act(() => {
        result.current.setSuccessData({ title: "Test success" });
      });

      expect(result.current.notificationCenter).toBe(true);
    });
  });

  describe("notification list management", () => {
    it("should add notification to history", () => {
      const { result } = renderHook(() => useAlertStore());
      const notification: Omit<AlertItemType, "id"> = {
        type: "error",
        title: "Manual error",
        list: ["Error detail"],
      };

      act(() => {
        result.current.addNotificationToHistory(notification);
      });

      expect(result.current.notificationList).toHaveLength(1);
      expect(result.current.notificationList[0]).toMatchObject({
        ...notification,
        id: "test-id-1",
      });
      expect(result.current.notificationCenter).toBe(true);
    });

    it("should clear notification list", () => {
      const { result } = renderHook(() => useAlertStore());

      // Add some notifications
      act(() => {
        result.current.setSuccessData({ title: "Success 1" });
        result.current.setSuccessData({ title: "Success 2" });
      });

      expect(result.current.notificationList).toHaveLength(2);

      act(() => {
        result.current.clearNotificationList();
      });

      expect(result.current.notificationList).toHaveLength(0);
    });

    it("should remove notification from list by id", () => {
      const { result } = renderHook(() => useAlertStore());

      // Add notifications
      act(() => {
        result.current.setSuccessData({ title: "Success 1" });
        result.current.setSuccessData({ title: "Success 2" });
      });

      const firstNotificationId = result.current.notificationList[0].id;
      expect(result.current.notificationList).toHaveLength(2);

      act(() => {
        result.current.removeFromNotificationList(firstNotificationId);
      });

      expect(result.current.notificationList).toHaveLength(1);
      expect(result.current.notificationList[0].title).toBe("Success 1"); // Second notification becomes first
    });
  });

  describe("temp notification list management", () => {
    it("should add notification to temp list", () => {
      const { result } = renderHook(() => useAlertStore());
      const notification: Omit<AlertItemType, "id"> = {
        type: "notice",
        title: "Manual notice",
        link: "https://example.com",
      };

      act(() => {
        result.current.addNotificationToTempList(notification);
      });

      expect(result.current.tempNotificationList).toHaveLength(1);
      expect(result.current.tempNotificationList[0]).toMatchObject({
        ...notification,
        id: "test-id-1",
      });
    });

    it("should not add duplicate notifications to temp list", () => {
      const { result } = renderHook(() => useAlertStore());
      const notification: Omit<AlertItemType, "id"> = {
        type: "notice",
        title: "Duplicate notice",
        link: "https://example.com",
      };

      act(() => {
        result.current.addNotificationToTempList(notification);
        result.current.addNotificationToTempList(notification);
      });

      // Should only have one notification due to duplicate prevention
      expect(result.current.tempNotificationList).toHaveLength(1);
    });

    it("should clear temp notification list", () => {
      const { result } = renderHook(() => useAlertStore());

      // Add some notifications
      act(() => {
        result.current.setSuccessData({ title: "Success 1" });
        result.current.setSuccessData({ title: "Success 2" });
      });

      expect(result.current.tempNotificationList).toHaveLength(2);

      act(() => {
        result.current.clearTempNotificationList();
      });

      expect(result.current.tempNotificationList).toHaveLength(0);
    });

    it("should remove notification from temp list by id", () => {
      const { result } = renderHook(() => useAlertStore());

      // Add notifications
      act(() => {
        result.current.setSuccessData({ title: "Success 1" });
        result.current.setSuccessData({ title: "Success 2" });
      });

      const firstTempNotificationId = result.current.tempNotificationList[0].id;
      expect(result.current.tempNotificationList).toHaveLength(2);

      act(() => {
        result.current.removeFromTempNotificationList(firstTempNotificationId);
      });

      expect(result.current.tempNotificationList).toHaveLength(1);
      expect(result.current.tempNotificationList[0].title).toBe("Success 1"); // Second notification becomes first
    });
  });

  describe("integration scenarios", () => {
    it("should handle multiple notification types", () => {
      const { result } = renderHook(() => useAlertStore());

      act(() => {
        result.current.setErrorData({
          title: "Error message",
          list: ["Detail"],
        });
        result.current.setNoticeData({
          title: "Notice message",
          link: "https://example.com",
        });
        result.current.setSuccessData({ title: "Success message" });
      });

      expect(result.current.notificationList).toHaveLength(3);
      expect(result.current.tempNotificationList).toHaveLength(3);

      expect(result.current.notificationList[2].type).toBe("error");
      expect(result.current.notificationList[1].type).toBe("notice");
      expect(result.current.notificationList[0].type).toBe("success");
    });

    it("should maintain separate history and temp lists", () => {
      const { result } = renderHook(() => useAlertStore());

      act(() => {
        result.current.setSuccessData({ title: "Success message" });
      });

      const historyId = result.current.notificationList[0].id;
      const tempId = result.current.tempNotificationList[0].id;

      // Remove from temp list only
      act(() => {
        result.current.removeFromTempNotificationList(tempId);
      });

      expect(result.current.notificationList).toHaveLength(1);
      expect(result.current.tempNotificationList).toHaveLength(0);

      // Remove from history list
      act(() => {
        result.current.removeFromNotificationList(historyId);
      });

      expect(result.current.notificationList).toHaveLength(0);
    });
  });
});
