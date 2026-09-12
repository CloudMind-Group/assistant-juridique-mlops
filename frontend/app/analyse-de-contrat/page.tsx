import UploadDropzone from "@/components/analyse/UploadDropzone";
import ProcessingStatusList from "@/components/analyse/ProcessingStatusList";

export default function AnalyseDeContratPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <UploadDropzone />
      <ProcessingStatusList />
    </div>
  );
}
