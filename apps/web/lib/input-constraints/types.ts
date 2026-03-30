export type InputFieldType = "text" | "phone" | "iin" | "date" | "latin_username";

export type ProcessPhase = "input" | "blur";

export type InputConstraint = {
  maxLength: number;
  maxRawLength?: number;
  trim: boolean;
  collapseSpaces: boolean;
  digitsOnly: boolean;
};

export type ProcessInputResult = {
  formattedValue: string;
  rawValue: string;
  isComplete: boolean;
  isPotentiallyValid: boolean;
};
