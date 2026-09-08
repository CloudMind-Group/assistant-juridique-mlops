"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Send } from "lucide-react";
import { useChatStore } from "@/lib/store";

export default function ChatComposer() {
  const { t } = useTranslation();
  const [value, setValue] = useState("");
  const sendMessage = useChatStore((s) => s.sendMessage);
  const isResponding = useChatStore((s) => s.isResponding);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || isResponding) return;
    sendMessage(trimmed);
    setValue("");
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-2 border-t border-sand-200 bg-white p-4 dark:border-forest-800 dark:bg-forest-900"
    >
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
          }
        }}
        rows={1}
        placeholder={t("consultation.placeholder") ?? undefined}
        className="max-h-32 flex-1 resize-none rounded-xl border border-sand-300 bg-sand-25 px-4 py-2.5 text-sm outline-none focus:border-forest-500 dark:border-forest-700 dark:bg-forest-950 dark:text-sand-100"
      />
      <button
        type="submit"
        disabled={!value.trim() || isResponding}
        aria-label={t("consultation.send") ?? "Envoyer"}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-forest-800 text-white transition-colors hover:bg-forest-700 disabled:cursor-not-allowed disabled:bg-forest-300"
      >
        <Send size={16} aria-hidden="true" />
      </button>
    </form>
  );
}
