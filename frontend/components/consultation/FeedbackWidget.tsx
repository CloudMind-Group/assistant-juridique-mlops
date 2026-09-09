"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/lib/store";

export default function FeedbackWidget({
  messageId,
  feedback,
}: {
  messageId: string;
  feedback: "up" | "down" | null | undefined;
}) {
  const { t } = useTranslation();
  const setFeedback = useChatStore((s) => s.setFeedback);
  const [showComment, setShowComment] = useState(false);
  const [sent, setSent] = useState(false);

  function choose(value: "up" | "down") {
    setFeedback(messageId, value);
    setShowComment(true);
  }

  return (
    <div className="mt-3 border-t border-sand-200 pt-3 dark:border-forest-800">
      {!sent ? (
        <>
          <div className="flex items-center gap-3 text-sm text-ink-500 dark:text-sand-400">
            <span>{t("consultation.feedbackPrompt")}</span>
            <button
              type="button"
              onClick={() => choose("up")}
              aria-pressed={feedback === "up"}
              aria-label={t("common.feedbackPositive") ?? undefined}
              className={cn(
                "rounded-lg p-1.5 hover:bg-sand-100 dark:hover:bg-forest-800",
                feedback === "up" && "bg-forest-100 text-forest-700 dark:bg-forest-800"
              )}
            >
              <ThumbsUp size={15} />
            </button>
            <button
              type="button"
              onClick={() => choose("down")}
              aria-pressed={feedback === "down"}
              aria-label={t("common.feedbackNegative") ?? undefined}
              className={cn(
                "rounded-lg p-1.5 hover:bg-sand-100 dark:hover:bg-forest-800",
                feedback === "down" && "bg-clay-400/15 text-clay-600"
              )}
            >
              <ThumbsDown size={15} />
            </button>
          </div>
          {showComment && (
            <form
              className="mt-2 flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                setSent(true);
              }}
            >
              <input
                type="text"
                placeholder={t("consultation.feedbackPlaceholder") ?? undefined}
                className="h-9 flex-1 rounded-lg border border-sand-300 bg-white px-3 text-sm outline-none focus:border-forest-500 dark:border-forest-700 dark:bg-forest-900"
              />
              <button
                type="submit"
                className="rounded-lg bg-forest-800 px-3 text-sm font-medium text-white hover:bg-forest-700"
              >
                {t("consultation.feedbackSend")}
              </button>
            </form>
          )}
        </>
      ) : (
        <p className="text-sm text-forest-600 dark:text-forest-300">
          {t("consultation.feedbackSent")}
        </p>
      )}
    </div>
  );
}
