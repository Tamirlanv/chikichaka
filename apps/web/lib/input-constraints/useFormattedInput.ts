"use client";

import { useMemo, useState } from "react";
import type { InputFieldType, ProcessInputResult } from "./types";
import { processInputValue } from "./process";

type UseFormattedInputResult = {
  value: string;
  rawValue: string;
  isComplete: boolean;
  isPotentiallyValid: boolean;
  onChangeValue: (next: string) => ProcessInputResult;
};

export function useFormattedInput(fieldType: InputFieldType, initialValue = ""): UseFormattedInputResult {
  const initial = useMemo(() => processInputValue(fieldType, initialValue), [fieldType, initialValue]);
  const [state, setState] = useState<ProcessInputResult>(initial);

  function onChangeValue(next: string): ProcessInputResult {
    const processed = processInputValue(fieldType, next, { phase: "input" });
    setState(processed);
    return processed;
  }

  return {
    value: state.formattedValue,
    rawValue: state.rawValue,
    isComplete: state.isComplete,
    isPotentiallyValid: state.isPotentiallyValid,
    onChangeValue,
  };
}
