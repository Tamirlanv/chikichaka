import { PROFILE_TEXTS, TRAIT_LABELS, TRAITS } from "./constants";
import type {
  AnswerKey,
  Lang,
  ProfileResult,
  ProfileType,
  Question,
  RankedTrait,
  ScoringRule,
  TraitKey,
  TraitScores,
  UserAnswer,
} from "./types";

export function emptyScores(): TraitScores {
  return { INI: 0, RES: 0, COL: 0, ADP: 0, REF: 0 };
}

export function rankTraits(scores: TraitScores): RankedTrait[] {
  return [...TRAITS]
    .map((t) => ({ trait: t, score: scores[t] }))
    .sort((a, b) => b.score - a.score || TRAITS.indexOf(a.trait) - TRAITS.indexOf(b.trait));
}

export function getTraitPercentages(scores: TraitScores): Record<TraitKey, number> {
  const total = Object.values(scores).reduce((a, b) => a + b, 0);
  if (!total) return { INI: 0, RES: 0, COL: 0, ADP: 0, REF: 0 };
  return {
    INI: (scores.INI / total) * 100,
    RES: (scores.RES / total) * 100,
    COL: (scores.COL / total) * 100,
    ADP: (scores.ADP / total) * 100,
    REF: (scores.REF / total) * 100,
  };
}

export function detectProfileType(
  dominant: TraitKey,
  secondary: TraitKey,
  isBalancedProfile: boolean,
): ProfileType {
  if (isBalancedProfile) return "BALANCED";
  if (dominant === "INI" && (secondary === "ADP" || secondary === "RES")) return "INITIATOR";
  if (dominant === "RES" && (secondary === "REF" || secondary === "INI")) return "ARCHITECT";
  if (dominant === "COL" && (secondary === "REF" || secondary === "RES")) return "INTEGRATOR";
  if (dominant === "ADP" && (secondary === "INI" || secondary === "REF")) return "ADAPTER";
  if (dominant === "REF" && (secondary === "RES" || secondary === "COL")) return "ANALYST";

  // Fallback mapping by dominant trait
  switch (dominant) {
    case "INI":
      return "INITIATOR";
    case "RES":
      return "ARCHITECT";
    case "COL":
      return "INTEGRATOR";
    case "ADP":
      return "ADAPTER";
    case "REF":
      return "ANALYST";
  }
}

export function detectQualityFlags(
  ranking: RankedTrait[],
  answerKeys: AnswerKey[],
): {
  isBalancedProfile: boolean;
  hasStrongDominance: boolean;
  shouldReviewForSocialDesirability: boolean;
  consistencyWarning: boolean;
} {
  const top1 = ranking[0]?.score ?? 0;
  const top2 = ranking[1]?.score ?? 0;
  const top3 = ranking[2]?.score ?? 0;
  const isBalancedProfile = Math.abs(top1 - top3) <= 3;
  const hasStrongDominance = top1 - top2 >= 5;

  // Social desirability heuristic (soft): too-even + very low answer variety
  const uniqueAnswers = new Set(answerKeys);
  const tooEven = !hasStrongDominance && isBalancedProfile;
  const veryLowVariety = uniqueAnswers.size <= 2 && answerKeys.length >= 30;
  const shouldReviewForSocialDesirability = Boolean(tooEven && veryLowVariety);

  // Consistency heuristic (soft): answers look random-ish (high variety) with very low dominance
  const consistencyWarning = Boolean(!hasStrongDominance && uniqueAnswers.size === 4 && answerKeys.length >= 30);

  return { isBalancedProfile, hasStrongDominance, shouldReviewForSocialDesirability, consistencyWarning };
}

export function buildExplainability(params: {
  lang: Lang;
  questionsById: Map<string, Question>;
  answers: UserAnswer[];
  dominantTrait: TraitKey;
  secondaryTrait: TraitKey;
  weakestTrait: TraitKey;
}): ProfileResult["explainability"] {
  const { lang, questionsById, answers, dominantTrait, secondaryTrait, weakestTrait } = params;

  const topWhy: string[] = [
    lang === "ru"
      ? `Высокий вклад в «${TRAIT_LABELS[dominantTrait].ru}» сформировался за счёт вариантов, где вы выбирали соответствующий стиль поведения.`
      : `A higher score in "${TRAIT_LABELS[dominantTrait].en}" emerged from choices that reflect this behavioral style.`,
    lang === "ru"
      ? `Вторая ведущая шкала — «${TRAIT_LABELS[secondaryTrait].ru}»: её усиливали ответы, где вы предпочитали этот способ действовать в ситуации.`
      : `The second leading dimension is "${TRAIT_LABELS[secondaryTrait].en}", strengthened by answers that favor this way of acting.`,
  ];

  const contributions = answers.map((a) => {
    const q = questionsById.get(a.questionId);
    const addedTo: ScoringRule = q ? q.scoring[a.answer] : {};
    return { questionId: a.questionId, answer: a.answer, addedTo };
  });

  const lessExpressed =
    lang === "ru"
      ? `Менее выраженная зона в текущем ответном стиле — «${TRAIT_LABELS[weakestTrait].ru}». Это не «минус», а просто то, что проявлялось реже в выбранных вариантах.`
      : `A less expressed area in the current response style is "${TRAIT_LABELS[weakestTrait].en}". This is not a negative label—just a pattern that appeared less often in choices.`;

  return { topTraitsWhy: topWhy, answerContributions: contributions, lessExpressed };
}

export function calculateProfile(
  userAnswers: UserAnswer[],
  questionsConfig: readonly Question[],
  lang: Lang = "ru",
): ProfileResult {
  const byId = new Map<string, Question>(questionsConfig.map((q) => [q.id, q]));

  const rawScores = emptyScores();
  const answerKeys: AnswerKey[] = [];
  const normalizedAnswers: UserAnswer[] = [];

  for (const a of userAnswers) {
    const q = byId.get(a.questionId);
    if (!q) continue;
    const rule = q.scoring[a.answer];
    normalizedAnswers.push(a);
    answerKeys.push(a.answer);
    for (const [trait, delta] of Object.entries(rule) as Array<[TraitKey, number]>) {
      rawScores[trait] += delta;
    }
  }

  const totalScore = Object.values(rawScores).reduce((s, v) => s + v, 0);
  const ranking = rankTraits(rawScores);
  const dominantTrait = ranking[0]?.trait ?? "INI";
  const secondaryTrait = ranking[1]?.trait ?? "RES";
  const weakestTrait = ranking[ranking.length - 1]?.trait ?? "REF";
  const percentages = getTraitPercentages(rawScores);

  const flags = detectQualityFlags(ranking, answerKeys);
  const profileType = detectProfileType(dominantTrait, secondaryTrait, flags.isBalancedProfile);
  const texts = PROFILE_TEXTS[profileType];

  return {
    rawScores,
    totalScore,
    percentages,
    ranking,
    dominantTrait,
    secondaryTrait,
    weakestTrait,
    profileType,
    profileTitle: texts.title[lang],
    summary: texts.summary[lang],
    detailedInterpretation: texts.interpretation[lang],
    explainability: buildExplainability({
      lang,
      questionsById: byId,
      answers: normalizedAnswers,
      dominantTrait,
      secondaryTrait,
      weakestTrait,
    }),
    flags,
  };
}

