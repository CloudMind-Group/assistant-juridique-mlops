import { act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useChatStore } from "@/lib/store";

describe("useChatStore", () => {
  beforeEach(() => {
    useChatStore.setState({ messages: [], isResponding: false });
    vi.useFakeTimers();
  });

  it("appends a user message immediately and a mocked assistant reply after a delay", () => {
    act(() => {
      useChatStore.getState().sendMessage("Quel est le délai de préavis ?");
    });

    let state = useChatStore.getState();
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0].role).toBe("user");
    expect(state.isResponding).toBe(true);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    state = useChatStore.getState();
    expect(state.messages).toHaveLength(2);
    expect(state.messages[1].role).toBe("assistant");
    expect(state.messages[1].sources?.length).toBeGreaterThan(0);
    expect(state.isResponding).toBe(false);
  });

  it("records feedback on a message", () => {
    act(() => {
      useChatStore.getState().sendMessage("Question ?");
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    const assistantMessage = useChatStore.getState().messages[1];
    act(() => {
      useChatStore.getState().setFeedback(assistantMessage.id, "up");
    });

    expect(useChatStore.getState().messages[1].feedback).toBe("up");
  });
});
