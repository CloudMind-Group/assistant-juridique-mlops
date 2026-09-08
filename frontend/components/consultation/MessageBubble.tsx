import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types";
import SourceCitations from "./SourceCitations";
import FeedbackWidget from "./FeedbackWidget";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex animate-fade-in", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed sm:max-w-[70%]",
          isUser
            ? "bg-forest-800 text-white"
            : "border border-sand-200 bg-white text-ink-800 dark:border-forest-800 dark:bg-forest-900 dark:text-sand-100"
        )}
      >
        <p>{message.content}</p>
        {!isUser && message.sources && <SourceCitations sources={message.sources} />}
        {!isUser && message.sources && (
          <FeedbackWidget messageId={message.id} feedback={message.feedback} />
        )}
      </div>
    </div>
  );
}
