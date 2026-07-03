import UploadDropzone from "@/components/upload-dropzone";

export default function UploadPage() {
  return (
    <div>
      <p className="eyebrow">pas 1</p>
      <h1>Încarcă o declarație</h1>
      <p className="lede">
        PDF sau imagine (PNG/JPG). Documentul urcă direct și securizat în
        stocare; extracția și verificările pornesc automat.
      </p>
      <UploadDropzone />
    </div>
  );
}
