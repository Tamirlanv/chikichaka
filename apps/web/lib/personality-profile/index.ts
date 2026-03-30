export type {
  TraitKey,
  AnswerKey,
  Lang,
  ScoringRule,
  QuestionOption,
  Question,
  UserAnswer,
  TraitScores,
  RankedTrait,
  ProfileType,
  ProfileResult,
} from "./types";

export { PERSONALITY_QUESTIONS, PERSONALITY_QUESTION_IDS } from "./questions";
export { calculateProfile, rankTraits, getTraitPercentages, detectProfileType } from "./calculateProfile";
export { TRAITS, PROFILE_TEXTS, TRAIT_LABELS } from "./constants";

