"use client";

import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { MessageSquare } from "lucide-react";
import Card from "@/components/ui/Card";
import { useChatStore } from "@/lib/store";
import MessageBubble from "./MessageBubble";
import ChatComposer from "./ChatComposer";

export default function ChatWindow() {
  const { t } = useTranslation();
  const messages = useChatStore((s) => s.messages);
  const isResponding = useChatStore((s) => s.isResponding);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isResponding]);

  return (
    <Card className="mx-auto flex h-[calc(100dvh-9.5rem)] max-w-3xl flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-sand-100 text-ink-400 dark:bg-forest-800 dark:text-sand-400">
              <MessageSquare size={26} aria-hidden="true" />
            </span>
            <h2 className="font-display text-xl font-semibold text-ink-800 dark:text-sand-50">
              {t("consultation.emptyTitle")}
            </h2>
            <p className="mt-1 text-sm text-ink-500 dark:text-sand-400">
              {t("consultation.emptySubtitle")}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {isResponding && (
              <div className="flex items-center gap-1.5 rounded-2xl border border-sand-200 bg-white px-4 py-3 text-ink-400 dark:border-forest-800 dark:bg-forest-900 w-fit">
                <span className="sr-only">{t("consultation.thinking")}</span>
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-ink-400"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      <ChatComposer />
      <p className="border-t border-sand-100 px-6 py-2 text-center text-xs text-ink-400 dark:border-forest-800 dark:text-sand-500">
        {t("consultation.disclaimer")}
      </p>
    </Card>
  );
}
