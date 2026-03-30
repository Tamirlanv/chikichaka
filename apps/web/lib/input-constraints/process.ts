import { DATE_RAW_LENGTH, IIN_LENGTH, PHONE_RAW_LENGTH, getInputConstraints } from "./config";
import type { InputFieldType, ProcessInputResult, ProcessPhase } from "./types";
import {
  formatDate,
  formatIIN,
  formatPhone,
  isDateRangePotentiallyValid,
  keepOnlyDigits,
  limitLength,
  normalizeKzPhoneRaw,
  sanitizeText,
  sanitizeLatinUsername,
} from "./utils";

export function validateRawInput(fieldType: InputFieldType, rawValue: string): boolean {
  switch (fieldType) {
    case "phone":
      return /^\d*$/.test(rawValue) && rawValue.length <= PHONE_RAW_LENGTH;
    case "iin":
      return /^\d*$/.test(rawValue) && rawValue.length <= IIN_LENGTH;
    case "date":
      return /^\d*$/.test(rawValue) && rawValue.length <= DATE_RAW_LENGTH && isDateRangePotentiallyValid(rawValue);
    case "latin_username":
      return /^@?[A-Za-z0-9._]*$/.test(rawValue) && rawValue.length <= getInputConstraints("latin_username").maxLength;
    case "text":
    default:
      return rawValue.length <= getInputConstraints("text").maxLength;
  }
}

export function validateFormattedInput(fieldType: InputFieldType, formattedValue: string): boolean {
  switch (fieldType) {
    case "phone":
      return /^\+7(?: \d{0,3})?(?: \d{0,3})?(?: \d{0,2})?(?: \d{0,2})?$/.test(formattedValue);
    case "iin":
      return /^\d{0,12}$/.test(formattedValue);
    case "date":
      return /^\d{0,2}(?:\.\d{0,2})?(?:\.\d{0,4})?$/.test(formattedValue);
    case "latin_username":
      return /^@?[A-Za-z0-9._]*$/.test(formattedValue);
    case "text":
    default:
      return formattedValue.length <= getInputConstraints("text").maxLength;
  }
}

export function processInputValue(
  fieldType: InputFieldType,
  inputValue: string,
  options?: { phase?: ProcessPhase },
): ProcessInputResult {
  const phase = options?.phase ?? "input";
  const constraint = getInputConstraints(fieldType);

  if (fieldType === "phone") {
    const rawValue = normalizeKzPhoneRaw(inputValue);
    const formattedValue = formatPhone(rawValue);
    return {
      formattedValue,
      rawValue,
      isComplete: rawValue.length === PHONE_RAW_LENGTH,
      isPotentiallyValid: validateRawInput(fieldType, rawValue) && validateFormattedInput(fieldType, formattedValue),
    };
  }

  if (fieldType === "iin") {
    const rawValue = formatIIN(inputValue);
    return {
      formattedValue: rawValue,
      rawValue,
      isComplete: rawValue.length === IIN_LENGTH,
      isPotentiallyValid: validateRawInput(fieldType, rawValue) && validateFormattedInput(fieldType, rawValue),
    };
  }

  if (fieldType === "date") {
    const rawValue = limitLength(keepOnlyDigits(inputValue), DATE_RAW_LENGTH);
    const formattedValue = formatDate(rawValue);
    const complete = rawValue.length === DATE_RAW_LENGTH;
    const rangeValid = isDateRangePotentiallyValid(rawValue);
    return {
      formattedValue,
      rawValue,
      isComplete: complete,
      isPotentiallyValid: phase === "blur" ? complete && rangeValid : rangeValid,
    };
  }

  if (fieldType === "latin_username") {
    const username = sanitizeLatinUsername(inputValue, constraint.maxLength);
    return {
      formattedValue: username,
      rawValue: username,
      isComplete: username.length > 0,
      isPotentiallyValid: /^@?[A-Za-z0-9._]*$/.test(username),
    };
  }

  const textValue = sanitizeText(inputValue, constraint.maxLength);
  return {
    formattedValue: textValue,
    rawValue: textValue,
    isComplete: textValue.length > 0,
    isPotentiallyValid: validateRawInput("text", textValue),
  };
}
