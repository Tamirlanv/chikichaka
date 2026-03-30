import type { InputConstraint, InputFieldType } from "./types";

export const DEFAULT_TEXT_MAX_LENGTH = 30;
export const PHONE_RAW_LENGTH = 11;
export const IIN_LENGTH = 12;
export const DATE_RAW_LENGTH = 8;
export const DATE_FORMATTED_LENGTH = 10;
export const PHONE_FORMATTED_LENGTH = 16;

export const INPUT_CONSTRAINTS: Record<InputFieldType, InputConstraint> = {
  text: {
    maxLength: DEFAULT_TEXT_MAX_LENGTH,
    trim: true,
    collapseSpaces: true,
    digitsOnly: false,
  },
  phone: {
    maxLength: PHONE_FORMATTED_LENGTH,
    maxRawLength: PHONE_RAW_LENGTH,
    trim: true,
    collapseSpaces: true,
    digitsOnly: true,
  },
  iin: {
    maxLength: IIN_LENGTH,
    maxRawLength: IIN_LENGTH,
    trim: true,
    collapseSpaces: true,
    digitsOnly: true,
  },
  date: {
    maxLength: DATE_FORMATTED_LENGTH,
    maxRawLength: DATE_RAW_LENGTH,
    trim: true,
    collapseSpaces: true,
    digitsOnly: true,
  },
  latin_username: {
    maxLength: DEFAULT_TEXT_MAX_LENGTH,
    trim: true,
    collapseSpaces: false,
    digitsOnly: false,
  },
};

export function getInputConstraints(fieldType: InputFieldType): InputConstraint {
  return INPUT_CONSTRAINTS[fieldType];
}
