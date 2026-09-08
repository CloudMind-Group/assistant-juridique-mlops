"use client";

import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { FileUp } from "lucide-react";
import Button from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import { useUploadStore } from "@/lib/store";

export default function UploadDropzone() {
  const { t } = useTranslation();
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const addFiles = useUploadStore((s) => s.addFiles);

  function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    addFiles(Array.from(fileList));
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-12 text-center transition-colors",
        dragging
          ? "border-forest-500 bg-forest-50 dark:bg-forest-900/40"
          : "border-sand-300 bg-white dark:border-forest-700 dark:bg-forest-900"
      )}
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-sand-100 text-ink-400 dark:bg-forest-800 dark:text-sand-400">
        <FileUp size={26} aria-hidden="true" />
      </span>
      <h2 className="font-display text-xl font-semibold text-ink-800 dark:text-sand-50">
        {t("analysis.dropTitle")}
      </h2>
      <p className="text-sm text-ink-500 dark:text-sand-400">
        {t("analysis.dropSubtitle")}
      </p>
      <Button
        type="button"
        variant="secondary"
        onClick={() => inputRef.current?.click()}
        className="mt-2"
      >
        {t("analysis.browse")}
      </Button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}
