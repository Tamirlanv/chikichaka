import type { Lang, ProfileType, TraitKey } from "./types";

export const TRAITS: readonly TraitKey[] = ["INI", "RES", "COL", "ADP", "REF"] as const;

export const PROFILE_TEXTS: Record<
  ProfileType,
  { title: Record<Lang, string>; summary: Record<Lang, string>; interpretation: Record<Lang, string[]> }
> = {
  INITIATOR: {
    title: { ru: "Инициатор", en: "Initiator" },
    summary: {
      ru: "Склонен быстро переходить к действию, охотно берет первый шаг и комфортно чувствует себя в ситуациях, где нужно запускать движение.",
      en: "Tends to move into action quickly, willingly takes the first step, and feels comfortable initiating momentum in ambiguous situations.",
    },
    interpretation: {
      ru: [
        "Чаще выбирает подход «сначала попробовать», а затем уточнять курс по ходу.",
        "Лучше всего проявляется в задачах запуска, пилотирования и быстрого тестирования гипотез.",
        "Может усиливать результат, если дополняет инициативу структурой и проверкой рисков.",
      ],
      en: [
        'Often prefers a "try first" approach and then adjusts course as information emerges.',
        "Shows strength in kick-off tasks, piloting, and rapid hypothesis testing.",
        "Performs best when initiative is complemented with structure and risk checks.",
      ],
    },
  },
  ARCHITECT: {
    title: { ru: "Архитектор", en: "Architect" },
    summary: {
      ru: "Силен в структуре, ответственности и последовательности. Чаще опирается на системность, надежность и способность удерживать обязательства.",
      en: "Strong in structure, reliability, and follow-through. Typically relies on systems thinking, responsibility, and keeping commitments.",
    },
    interpretation: {
      ru: [
        "Склонен разбивать большие задачи на понятные этапы и критерии качества.",
        "Уверенно работает там, где важны сроки, ответственность и устойчивый процесс.",
        "Может выигрывать, если оставляет место для проб и адаптации при изменении условий.",
      ],
      en: [
        "Tends to break large problems into clear steps and quality criteria.",
        "Performs well where deadlines, responsibility, and stable processes matter.",
        "Benefits from leaving room for experimentation and adaptation when conditions change.",
      ],
    },
  },
  INTEGRATOR: {
    title: { ru: "Интегратор", en: "Integrator" },
    summary: {
      ru: "Хорошо чувствует людей и групповую динамику. Силен в объединении позиций, координации взаимодействия и поддержании конструктивной среды.",
      en: "Sensitive to people and team dynamics. Strong at aligning viewpoints, coordinating collaboration, and maintaining a constructive environment.",
    },
    interpretation: {
      ru: [
        "Чаще выбирает варианты, где учитываются позиции участников и качество коммуникации.",
        "Эффективен в задачах согласования, фасилитации и снятия напряжения.",
        "Может усиливать результат, сохраняя ясность решений и ответственности.",
      ],
      en: [
        "Often prefers options that consider stakeholders' needs and communication quality.",
        "Effective in alignment, facilitation, and de-escalation situations.",
        "Performs best when collaboration is paired with decision clarity and ownership.",
      ],
    },
  },
  ADAPTER: {
    title: { ru: "Адаптер", en: "Adapter" },
    summary: {
      ru: "Быстро перестраивается в новых обстоятельствах, устойчив к неопределенности и склонен искать рабочие решения в меняющихся условиях.",
      en: "Adapts quickly to new circumstances, tolerates uncertainty well, and seeks workable solutions as conditions change.",
    },
    interpretation: {
      ru: [
        "Склонен действовать в неполной ясности и уточнять по мере появления данных.",
        "Хорошо проявляется в динамичных проектах и ситуациях, где нужен «план Б».",
        "Может усиливать результат, добавляя структурные опоры и фиксацию договоренностей.",
      ],
      en: [
        "Tends to act with incomplete information and refine decisions as new data appears.",
        "Strong in fast-changing projects and situations requiring contingency planning.",
        "Benefits from adding structure and explicit agreements to maintain alignment.",
      ],
    },
  },
  ANALYST: {
    title: { ru: "Аналитик", en: "Analyst" },
    summary: {
      ru: "Склонен к осмыслению, анализу и вниманию к нюансам. Чаще стремится сначала понять контекст, а затем действовать.",
      en: "Leans toward reflection, analysis, and nuance. Typically aims to understand context first and then act.",
    },
    interpretation: {
      ru: [
        "Склонен проверять гипотезы, уточнять критерии и искать внутреннюю логику ситуации.",
        "Эффективен в задачах, где важна точность, объяснимость и качество решений.",
        "Может усиливать результат, быстрее переходя к «малому шагу» и проверке на практике.",
      ],
      en: [
        "Tends to test hypotheses, clarify criteria, and look for underlying logic.",
        "Effective when precision, explainability, and decision quality matter.",
        "Benefits from moving sooner into a small action step and validating in practice.",
      ],
    },
  },
  BALANCED: {
    title: { ru: "Сбалансированный профиль", en: "Balanced profile" },
    summary: {
      ru: "Не имеет одного жестко доминирующего стиля. Может гибко переключаться между разными способами реагирования в зависимости от ситуации.",
      en: "Does not have a single strongly dominant style. Can flexibly switch between approaches depending on the situation.",
    },
    interpretation: {
      ru: [
        "Скорее выбирает поведенческие стратегии под контекст, а не по одному устойчивому шаблону.",
        "В разных задачах может проявлять и инициативу, и структурность, и командность.",
        "Полезно уточнять, в каких условиях работает лучше всего — в динамике или в стабильности.",
      ],
      en: [
        "Tends to choose strategies based on context rather than a single fixed pattern.",
        "May show initiative, structure, and collaboration depending on the task.",
        "Useful to clarify which conditions bring out the best performance—dynamic or stable environments.",
      ],
    },
  },
};

export const TRAIT_LABELS: Record<TraitKey, Record<Lang, string>> = {
  INI: { ru: "Инициативность", en: "Initiative" },
  RES: { ru: "Ответственность", en: "Reliability" },
  COL: { ru: "Командность", en: "Collaboration" },
  ADP: { ru: "Адаптивность", en: "Adaptability" },
  REF: { ru: "Рефлексивность", en: "Reflectiveness" },
};

