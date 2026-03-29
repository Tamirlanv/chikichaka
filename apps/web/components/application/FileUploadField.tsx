"use client";

import Image from "next/image";
import { useId, useRef, useState } from "react";
import { formatFileSize, validateUploadFile } from "@/lib/file-upload";
import styles from "./form-ui.module.css";

export type UploadedFileDisplay = {
  name: string;
  sizeBytes: number;
};

type Props = {
  label: string;
  hint?: string;
  accept?: string;
  /** Вызов после успешной проверки; `null` — сброс (удаление) */
  onFile?: (file: File | null) => void;
  /** Карточка загруженного файла (имя и размер с сервера или после выбора) */
  uploadedFile?: UploadedFileDisplay | null;
  /** Идёт отправка на сервер */
  isUploading?: boolean;
  /** Показать кнопку «Удалить» (если сброс на сервере не поддержан — false) */
  allowRemove?: boolean;
};

export function FileUploadField({
  label,
  hint = "Разрешенные форматы: .PDF .JPEG .PNG .HEIC до 10MB",
  accept = ".pdf,.jpg,.jpeg,.png,.heic,.heif",
  onFile,
  uploadedFile,
  isUploading = false,
  allowRemove = true,
}: Props) {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  function processFile(file: File | null) {
    setLocalError(null);
    if (!file) {
      if (inputRef.current) inputRef.current.value = "";
      onFile?.(null);
      return;
    }
    const v = validateUploadFile(file);
    if (!v.ok) {
      setLocalError(v.message);
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    onFile?.(file);
    if (inputRef.current) inputRef.current.value = "";
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0] ?? null;
    processFile(file);
  }

  const showCard = Boolean(uploadedFile);
  const removeDisabled = isUploading;

  return (
    <div className={styles.uploadRoot}>
      <span className={styles.label} id={`${id}-label`}>
        {label}
      </span>
      <label
        className={`${styles.uploadArea} ${dragOver ? styles.uploadAreaDrag : ""}`}
        htmlFor={id}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          id={id}
          type="file"
          className={styles.visuallyHidden}
          accept={accept}
          aria-labelledby={`${id}-label`}
          onChange={(e) => processFile(e.target.files?.[0] ?? null)}
        />
        <Image
          className={styles.uploadIcon}
          src="/assets/icons/material-symbols_upload-rounded.svg"
          alt=""
          width={36}
          height={36}
          unoptimized
        />
        <p className={styles.uploadTitle}>Нажмите чтобы загрузить или перетащите файл</p>
        <p className={styles.uploadHint}>{hint}</p>
      </label>
      {localError ? <p className={styles.uploadError}>{localError}</p> : null}
      {showCard && uploadedFile ? (
        <div className={styles.uploadFileCard}>
          <Image
            src="/assets/icons/solar_file-bold.svg"
            alt=""
            width={36}
            height={36}
            className={styles.uploadFileCardIcon}
            unoptimized
          />
          <div className={styles.uploadFileCardBody}>
            <p className={styles.uploadFileCardName}>{uploadedFile.name}</p>
            <p className={styles.uploadFileCardSize}>{formatFileSize(uploadedFile.sizeBytes)}</p>
            {isUploading ? (
              <p className={styles.uploadFileCardStatus}>Загрузка на сервер…</p>
            ) : null}
          </div>
          {allowRemove ? (
            <button
              type="button"
              className={styles.uploadFileDelete}
              disabled={removeDisabled}
              onClick={() => processFile(null)}
            >
              <Image
                src="/assets/icons/iconoir_trash-solid.svg"
                alt=""
                width={14}
                height={14}
                unoptimized
                aria-hidden
              />
              <span>Удалить</span>
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
