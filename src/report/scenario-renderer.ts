// ============================================================================
// Adviesrapport — Generic scenario renderers
//
// Pure functions that assemble paragraph arrays from centralized text blocks.
// Returns plain strings — the caller wraps them in NarrativeBlock if needed.
// ============================================================================

import type {
  RelationshipOverallStatus,
  RelationshipPersonStatus,
  RelationshipTextBlock,
  StandardAdviceType,
  StandardScenarioStatus,
  StandardScenarioTextBlock,
} from "./types";

// --- Helpers ---------------------------------------------------------------

/**
 * Keep only the keys whose associated condition is truthy.
 * @example compactKeys(["existing_orv", true], ["savings_used", false]) → ["existing_orv"]
 */
export const compactKeys = (
  ...entries: Array<[string, unknown]>
): string[] => entries.filter(([, v]) => !!v).map(([k]) => k);

// --- Standard scenario renderer --------------------------------------------

export const renderStandardScenario = (input: {
  text: StandardScenarioTextBlock;
  status: StandardScenarioStatus;
  adviceType?: StandardAdviceType;
  nuanceKeys?: string[];
}): string[] => {
  const { text, status, adviceType, nuanceKeys } = input;
  const paragraphs: string[] = [];

  // 1. Intro
  paragraphs.push(text.intro);

  // 2. Outcome
  paragraphs.push(text.outcome[status]);

  // 3. Advice (if type provided and text exists)
  if (adviceType && text.advice[adviceType]) {
    paragraphs.push(text.advice[adviceType]!);
  }

  // 4. Nuance texts in supplied order
  if (nuanceKeys && text.nuance) {
    for (const key of nuanceKeys) {
      if (text.nuance[key]) {
        paragraphs.push(text.nuance[key]);
      }
    }
  }

  // 5. Disclaimer
  if (text.disclaimer) {
    paragraphs.push(text.disclaimer);
  }

  return paragraphs;
};

// --- Relationship scenario renderer ----------------------------------------

export const renderRelationshipScenario = (input: {
  text: RelationshipTextBlock;
  overallStatus: RelationshipOverallStatus;
  applicantStatus: RelationshipPersonStatus;
  partnerStatus: RelationshipPersonStatus;
}): string[] => {
  const { text, overallStatus, applicantStatus, partnerStatus } = input;
  const paragraphs: string[] = [];

  // 1. Intro
  paragraphs.push(text.intro);

  // 2. Overall outcome
  paragraphs.push(text.overallOutcome[overallStatus]);

  // 3. Applicant person status
  paragraphs.push(text.personStatus[applicantStatus]);

  // 4. Partner person status
  paragraphs.push(text.personStatus[partnerStatus]);

  // 5. Advice
  paragraphs.push(text.advice.awareness_only);

  // 6. Disclaimer
  paragraphs.push(text.disclaimer);

  return paragraphs;
};
