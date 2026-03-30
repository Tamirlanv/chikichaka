export type MotivationPasteMeta = {
  wasPasted: boolean;
  pasteCount: number;
  lastPastedAt: string | null;
};

export type MotivationValidationResult = {
  isValid: boolean;
  errors: string[];
};

export type MotivationLetterState = {
  text: string;
  charCount: number;
  isValid: boolean;
  errors: string[];
  meta: MotivationPasteMeta;
};
