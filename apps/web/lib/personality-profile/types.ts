export type TraitKey = "INI" | "RES" | "COL" | "ADP" | "REF";

export type AnswerKey = "A" | "B" | "C" | "D";

export type Lang = "ru" | "en";

export type ScoringRule = Partial<Record<TraitKey, number>>;

export type QuestionOption = {
  key: AnswerKey;
  text: Record<Lang, string>;
};

export type Question = {
  /** Stable UUID string (seeded into DB). */
  id: string;
  index: number; // 1..40
  text: Record<Lang, string>;
  options: QuestionOption[];
  scoring: Record<AnswerKey, ScoringRule>;
};

export type UserAnswer = {
  questionId: string;
  answer: AnswerKey;
};

export type TraitScores = Record<TraitKey, number>;

export type RankedTrait = {
  trait: TraitKey;
  score: number;
};

export type ProfileType =
  | "INITIATOR"
  | "ARCHITECT"
  | "INTEGRATOR"
  | "ADAPTER"
  | "ANALYST"
  | "BALANCED";

export type ProfileResult = {
  rawScores: TraitScores;
  totalScore: number;
  percentages: Record<TraitKey, number>;
  ranking: RankedTrait[];
  dominantTrait: TraitKey;
  secondaryTrait: TraitKey;
  weakestTrait: TraitKey;
  profileType: ProfileType;
  profileTitle: string;
  summary: string;
  detailedInterpretation: string[];
  explainability: {
    topTraitsWhy: string[];
    answerContributions: Array<{
      questionId: string;
      answer: AnswerKey;
      addedTo: ScoringRule;
    }>;
    lessExpressed: string;
  };
  flags: {
    isBalancedProfile: boolean;
    hasStrongDominance: boolean;
    shouldReviewForSocialDesirability: boolean;
    consistencyWarning: boolean;
  };
};

