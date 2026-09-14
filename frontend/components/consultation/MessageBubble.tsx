"use client";

import { useTranslation } from "react-i18next";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types";
import SourceCitations from "./SourceCitations";
import FeedbackWidget from "./FeedbackWidget";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const { t } = useTranslation();
  const isUser = message.role === "user";
  const isRefused = !isUser && message.refused;

  return (
    <div className={cn("flex animate-fade-in", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed sm:max-w-[70%]",
          isUser &&
            "bg-forest-800 text-white",
          !isUser &&
            !isRefused &&
            "border border-sand-200 bg-white text-ink-800 dark:border-forest-800 dark:bg-forest-900 dark:text-sand-100",
          // A refused answer must never look like a normal grounded reply —
          // distinct border/background/icon instead of a plain bubble.
          isRefused &&
            "border-2 border-gold-500 bg-gold-300/20 text-ink-800 dark:bg-gold-500/10 dark:text-sand-100"
        )}
      >
        {isRefused && (
          <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-gold-600 dark:text-gold-300">
            <AlertTriangle size={14} aria-hidden="true" />
            {t("consultation.refusedLabel")}
          </div>
        )}
        <p>{message.content}</p>
        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceCitations sources={message.sources} />
        )}
        {!isUser && message.sources && (
          <FeedbackWidget messageId={message.id} feedback={message.feedback} />
        )}
      </div>
    </div>
  );
}
