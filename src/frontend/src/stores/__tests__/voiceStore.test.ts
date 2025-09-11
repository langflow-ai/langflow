import { act, renderHook } from "@testing-library/react";
import { useVoiceStore } from "../voiceStore";
import { mockDataFactory, resetStoreState } from "./testUtils";

// Mock the constants to avoid dependency issues
jest.mock("@/constants/constants", () => ({
  OPENAI_VOICES: [
    { name: "Alloy", value: "alloy" },
    { name: "Echo", value: "echo" },
    { name: "Fable", value: "fable" },
  ],
}));

const mockVoices = [
  mockDataFactory.createVoice({ name: "Voice One", voice_id: "voice-1" }),
  mockDataFactory.createVoice({ name: "Voice Two", voice_id: "voice-2" }),
  mockDataFactory.createVoice({ name: "Voice Three", voice_id: "voice-3" }),
];

const mockProviders = [
  mockDataFactory.createProvider({ name: "Custom Provider", value: "custom" }),
  mockDataFactory.createProvider({ name: "Azure", value: "azure" }),
];

const mockOpenAIVoices = [
  mockDataFactory.createProvider({ name: "Nova", value: "nova" }),
  mockDataFactory.createProvider({ name: "Shimmer", value: "shimmer" }),
];

describe("useVoiceStore", () => {
  beforeEach(() => {
    resetStoreState(useVoiceStore, {
      voices: [],
      providersList: [
        { name: "OpenAI", value: "openai" },
        { name: "ElevenLabs", value: "elevenlabs" },
      ],
      openaiVoices: [
        { name: "Alloy", value: "alloy" },
        { name: "Echo", value: "echo" },
        { name: "Fable", value: "fable" },
      ],
      soundDetected: false,
      isVoiceAssistantActive: false,
      newSessionCloseVoiceAssistant: false,
    });
  });

  describe("initial state", () => {
    it("should have correct initial state", () => {
      const { result } = renderHook(() => useVoiceStore());

      expect(result.current.voices).toEqual([]);
      expect(result.current.providersList).toEqual([
        { name: "OpenAI", value: "openai" },
        { name: "ElevenLabs", value: "elevenlabs" },
      ]);
      expect(result.current.openaiVoices).toEqual([
        { name: "Alloy", value: "alloy" },
        { name: "Echo", value: "echo" },
        { name: "Fable", value: "fable" },
      ]);
      expect(result.current.soundDetected).toBe(false);
      expect(result.current.isVoiceAssistantActive).toBe(false);
      expect(result.current.newSessionCloseVoiceAssistant).toBe(false);
    });
  });

  describe("setVoices", () => {
    it("should set voices array", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setVoices(mockVoices);
      });

      expect(result.current.voices).toEqual(mockVoices);
    });

    it("should replace existing voices", () => {
      const { result } = renderHook(() => useVoiceStore());
      const initialVoices = [{ name: "Initial Voice", voice_id: "initial" }];

      act(() => {
        result.current.setVoices(initialVoices);
      });
      expect(result.current.voices).toEqual(initialVoices);

      act(() => {
        result.current.setVoices(mockVoices);
      });
      expect(result.current.voices).toEqual(mockVoices);
    });

    it("should handle empty voices array", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setVoices([]);
      });

      expect(result.current.voices).toEqual([]);
    });

    it("should handle single voice", () => {
      const { result } = renderHook(() => useVoiceStore());
      const singleVoice = [{ name: "Solo Voice", voice_id: "solo-1" }];

      act(() => {
        result.current.setVoices(singleVoice);
      });

      expect(result.current.voices).toEqual(singleVoice);
    });

    it("should handle voices with special characters", () => {
      const { result } = renderHook(() => useVoiceStore());
      const specialVoices = [
        { name: "Voice with émojis 🎵", voice_id: "special-1" },
        { name: "Voice & More", voice_id: "special-2" },
      ];

      act(() => {
        result.current.setVoices(specialVoices);
      });

      expect(result.current.voices).toEqual(specialVoices);
    });
  });

  describe("setProvidersList", () => {
    it("should set providers list", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setProvidersList(mockProviders);
      });

      expect(result.current.providersList).toEqual(mockProviders);
    });

    it("should replace existing providers", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setProvidersList(mockProviders);
      });
      expect(result.current.providersList).toEqual(mockProviders);

      const newProviders = [{ name: "Google", value: "google" }];
      act(() => {
        result.current.setProvidersList(newProviders);
      });
      expect(result.current.providersList).toEqual(newProviders);
    });

    it("should handle empty providers list", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setProvidersList([]);
      });

      expect(result.current.providersList).toEqual([]);
    });

    it("should handle providers with long names", () => {
      const { result } = renderHook(() => useVoiceStore());
      const longNameProviders = [
        {
          name: "Very Long Provider Name That Exceeds Normal Length",
          value: "long-provider",
        },
      ];

      act(() => {
        result.current.setProvidersList(longNameProviders);
      });

      expect(result.current.providersList).toEqual(longNameProviders);
    });
  });

  describe("setOpenaiVoices", () => {
    it("should set OpenAI voices", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setOpenaiVoices(mockOpenAIVoices);
      });

      expect(result.current.openaiVoices).toEqual(mockOpenAIVoices);
    });

    it("should replace existing OpenAI voices", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setOpenaiVoices(mockOpenAIVoices);
      });
      expect(result.current.openaiVoices).toEqual(mockOpenAIVoices);

      const updatedVoices = [{ name: "Updated Voice", value: "updated" }];
      act(() => {
        result.current.setOpenaiVoices(updatedVoices);
      });
      expect(result.current.openaiVoices).toEqual(updatedVoices);
    });

    it("should handle empty OpenAI voices", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setOpenaiVoices([]);
      });

      expect(result.current.openaiVoices).toEqual([]);
    });

    it("should handle OpenAI voices with duplicate names", () => {
      const { result } = renderHook(() => useVoiceStore());
      const duplicateVoices = [
        { name: "Duplicate", value: "duplicate-1" },
        { name: "Duplicate", value: "duplicate-2" },
      ];

      act(() => {
        result.current.setOpenaiVoices(duplicateVoices);
      });

      expect(result.current.openaiVoices).toEqual(duplicateVoices);
    });
  });

  describe("setSoundDetected", () => {
    it("should set sound detected to true", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setSoundDetected(true);
      });

      expect(result.current.soundDetected).toBe(true);
    });

    it("should set sound detected to false", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setSoundDetected(true);
      });
      expect(result.current.soundDetected).toBe(true);

      act(() => {
        result.current.setSoundDetected(false);
      });
      expect(result.current.soundDetected).toBe(false);
    });

    it("should toggle sound detected multiple times", () => {
      const { result } = renderHook(() => useVoiceStore());

      const toggleSequence = [true, false, true, false, true];
      toggleSequence.forEach((value) => {
        act(() => {
          result.current.setSoundDetected(value);
        });
        expect(result.current.soundDetected).toBe(value);
      });
    });
  });

  describe("setIsVoiceAssistantActive", () => {
    it("should set voice assistant active to true", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setIsVoiceAssistantActive(true);
      });

      expect(result.current.isVoiceAssistantActive).toBe(true);
    });

    it("should set voice assistant active to false", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setIsVoiceAssistantActive(true);
      });
      expect(result.current.isVoiceAssistantActive).toBe(true);

      act(() => {
        result.current.setIsVoiceAssistantActive(false);
      });
      expect(result.current.isVoiceAssistantActive).toBe(false);
    });

    it("should maintain independent state from sound detection", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setSoundDetected(true);
        result.current.setIsVoiceAssistantActive(false);
      });

      expect(result.current.soundDetected).toBe(true);
      expect(result.current.isVoiceAssistantActive).toBe(false);
    });
  });

  describe("setNewSessionCloseVoiceAssistant", () => {
    it("should set new session close voice assistant to true", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setNewSessionCloseVoiceAssistant(true);
      });

      expect(result.current.newSessionCloseVoiceAssistant).toBe(true);
    });

    it("should set new session close voice assistant to false", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setNewSessionCloseVoiceAssistant(true);
      });
      expect(result.current.newSessionCloseVoiceAssistant).toBe(true);

      act(() => {
        result.current.setNewSessionCloseVoiceAssistant(false);
      });
      expect(result.current.newSessionCloseVoiceAssistant).toBe(false);
    });
  });

  describe("state interactions", () => {
    it("should handle voice assistant lifecycle", () => {
      const { result } = renderHook(() => useVoiceStore());

      // Simulate voice assistant activation
      act(() => {
        result.current.setSoundDetected(true);
        result.current.setIsVoiceAssistantActive(true);
      });

      expect(result.current.soundDetected).toBe(true);
      expect(result.current.isVoiceAssistantActive).toBe(true);

      // Simulate deactivation
      act(() => {
        result.current.setSoundDetected(false);
        result.current.setIsVoiceAssistantActive(false);
      });

      expect(result.current.soundDetected).toBe(false);
      expect(result.current.isVoiceAssistantActive).toBe(false);
    });

    it("should handle complete voice setup", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setVoices(mockVoices);
        result.current.setProvidersList(mockProviders);
        result.current.setOpenaiVoices(mockOpenAIVoices);
        result.current.setIsVoiceAssistantActive(true);
      });

      expect(result.current.voices).toEqual(mockVoices);
      expect(result.current.providersList).toEqual(mockProviders);
      expect(result.current.openaiVoices).toEqual(mockOpenAIVoices);
      expect(result.current.isVoiceAssistantActive).toBe(true);
    });

    it("should maintain state consistency across multiple hook instances", () => {
      const { result: result1 } = renderHook(() => useVoiceStore());
      const { result: result2 } = renderHook(() => useVoiceStore());

      act(() => {
        result1.current.setIsVoiceAssistantActive(true);
      });

      expect(result1.current.isVoiceAssistantActive).toBe(true);
      expect(result2.current.isVoiceAssistantActive).toBe(true);
    });

    it("should handle new session behavior", () => {
      const { result } = renderHook(() => useVoiceStore());

      // Start with voice assistant active
      act(() => {
        result.current.setIsVoiceAssistantActive(true);
      });
      expect(result.current.isVoiceAssistantActive).toBe(true);

      // Set new session close behavior
      act(() => {
        result.current.setNewSessionCloseVoiceAssistant(true);
      });
      expect(result.current.newSessionCloseVoiceAssistant).toBe(true);

      // Simulate session end behavior
      act(() => {
        result.current.setIsVoiceAssistantActive(false);
        result.current.setNewSessionCloseVoiceAssistant(false);
      });
      expect(result.current.isVoiceAssistantActive).toBe(false);
      expect(result.current.newSessionCloseVoiceAssistant).toBe(false);
    });
  });

  describe("edge cases", () => {
    it("should handle large voices arrays", () => {
      const { result } = renderHook(() => useVoiceStore());
      const largeVoicesArray = Array.from({ length: 1000 }, (_, i) => ({
        name: `Voice ${i}`,
        voice_id: `voice-${i}`,
      }));

      act(() => {
        result.current.setVoices(largeVoicesArray);
      });

      expect(result.current.voices).toHaveLength(1000);
      expect(result.current.voices[0]).toEqual({
        name: "Voice 0",
        voice_id: "voice-0",
      });
      expect(result.current.voices[999]).toEqual({
        name: "Voice 999",
        voice_id: "voice-999",
      });
    });

    it("should handle rapid boolean state changes", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        for (let i = 0; i < 100; i++) {
          result.current.setSoundDetected(i % 2 === 0);
          result.current.setIsVoiceAssistantActive(i % 3 === 0);
          result.current.setNewSessionCloseVoiceAssistant(i % 5 === 0);
        }
      });

      // Final states after 100 iterations (99th iteration, 0-indexed)
      expect(result.current.soundDetected).toBe(false); // 99 % 2 !== 0
      expect(result.current.isVoiceAssistantActive).toBe(true); // 99 % 3 === 0
      expect(result.current.newSessionCloseVoiceAssistant).toBe(false); // 99 % 5 !== 0
    });

    it("should handle voices with empty strings", () => {
      const { result } = renderHook(() => useVoiceStore());
      const emptyStringVoices = [
        { name: "", voice_id: "empty-name" },
        { name: "Valid Name", voice_id: "" },
        { name: "", voice_id: "" },
      ];

      act(() => {
        result.current.setVoices(emptyStringVoices);
      });

      expect(result.current.voices).toEqual(emptyStringVoices);
    });

    it("should handle providers with same values but different names", () => {
      const { result } = renderHook(() => useVoiceStore());
      const duplicateValueProviders = [
        { name: "Provider A", value: "same-value" },
        { name: "Provider B", value: "same-value" },
      ];

      act(() => {
        result.current.setProvidersList(duplicateValueProviders);
      });

      expect(result.current.providersList).toEqual(duplicateValueProviders);
    });

    it("should handle complex voice objects with additional properties", () => {
      const { result } = renderHook(() => useVoiceStore());
      const complexVoices = [
        {
          name: "Complex Voice",
          voice_id: "complex-1",
          // Additional properties that shouldn't break the store
          extra: { data: "value" },
          metadata: ["tag1", "tag2"],
        } as any,
      ];

      act(() => {
        result.current.setVoices(complexVoices);
      });

      expect(result.current.voices).toEqual(complexVoices);
    });

    it("should handle simultaneous updates to all voice arrays", () => {
      const { result } = renderHook(() => useVoiceStore());

      act(() => {
        result.current.setVoices(mockVoices);
        result.current.setProvidersList(mockProviders);
        result.current.setOpenaiVoices(mockOpenAIVoices);
      });

      expect(result.current.voices).toHaveLength(mockVoices.length);
      expect(result.current.providersList).toHaveLength(mockProviders.length);
      expect(result.current.openaiVoices).toHaveLength(mockOpenAIVoices.length);
    });

    it("should handle Unicode characters in voice names", () => {
      const { result } = renderHook(() => useVoiceStore());
      const unicodeVoices = [
        { name: "声音一", voice_id: "chinese-1" },
        { name: "صوت واحد", voice_id: "arabic-1" },
        { name: "Голос один", voice_id: "russian-1" },
        { name: "🎵 Musical Voice 🎶", voice_id: "emoji-1" },
      ];

      act(() => {
        result.current.setVoices(unicodeVoices);
      });

      expect(result.current.voices).toEqual(unicodeVoices);
    });
  });
});
