import { act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatStore } from "@/lib/store";
import { useHistoryStore } from "@/lib/historyStore";

describe("useChatStore", () => {
  beforeEach(() => {
    useChatStore.setState({ messages: [], isResponding: false });
    vi.useFakeTimers();
  });

  // Fake timers must not leak into other test files (this was previously
  // missing, which could make unrelated tests hang or behave inconsistently
  // depending on run order).
  afterEach(() => {
    vi.useRealTimers();
  });

  it("appends a user message immediately and a mapped assistant reply after a delay", async () => {
    act(() => {
      useChatStore.getState().sendMessage("Quel est le délai de préavis ?");
    });

    let state = useChatStore.getState();
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]?.role).toBe("user");
    expect(state.isResponding).toBe(true);

    // sendMessage now goes through the async API boundary (lib/api.ts), so
    // the fake-timer advance must be awaited for its microtasks to flush.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    state = useChatStore.getState();
    expect(state.messages).toHaveLength(2);
    expect(state.messages[1]?.role).toBe("assistant");
    expect(state.messages[1]?.sources?.length).toBeGreaterThan(0);
    expect(state.isResponding).toBe(false);
  });

  it("records feedback on a message and mirrors it into the history store", async () => {
    act(() => {
      useChatStore.getState().sendMessage("Question ?");
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    const assistantMessage = useChatStore.getState().messages[1];
    if (!assistantMessage) throw new Error("expected an assistant reply");
    act(() => {
      useChatStore.getState().setFeedback(assistantMessage.id, "up");
    });

    expect(useChatStore.getState().messages[1]?.feedback).toBe("up");

    const historyEntry = useHistoryStore
      .getState()
      .entries.find((entry) => entry.id === assistantMessage.id);
    expect(historyEntry?.feedback).toBe("up");
  });

  it("routes out-of-scope questions to a refused reply with no sources", async () => {
    act(() => {
      useChatStore.getState().sendMessage("Quelle est la météo demain ?");
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    const reply = useChatStore.getState().messages[1];
    if (!reply) throw new Error("expected an assistant reply");
    expect(reply.refused).toBe(true);
    expect(reply.sources).toHaveLength(0);
  });
});
