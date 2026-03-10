// ============================================================================
// Adviesrapport — Public API
// ============================================================================

// --- Types -----------------------------------------------------------------

export type {
  // Input
  ReportBuilderInput,
  ComputedFields,
  // Scenario text engine
  StandardScenarioStatus,
  StandardAdviceType,
  StandardScenarioTextBlock,
  RelationshipOverallStatus,
  RelationshipPersonStatus,
  RelationshipTextBlock,
  // Retirement analysis
  RetirementAnalysisInput,
  RetirementMoment,
  RetirementIncomeComponent,
  RetirementShortfallSeverity,
  RetirementScenarioKind,
  RetirementMomentAnalysis,
  RetirementScenarioAnalysis,
  // Viewmodel
  ReportViewModel,
  ReportVisibility,
  ReportMetaSection,
  SummarySection,
  ClientProfileSection,
  PropertySection,
  AffordabilitySection,
  FinancingSection,
  LoanPartsSection,
  TaxSection,
  RisksSection,
  RelationshipRiskSection,
  RetirementSection,
  AttentionPointsSection,
  DisclaimerSection,
  // Row types
  LabelValueRow,
  MoneyRow,
  LoanPartRow,
  NarrativeBlock,
  // Domain types
  Money,
  Percentage,
} from "./types";

// --- Builders --------------------------------------------------------------

export { buildComputedFields, buildFullName, formatAddressInline } from "./computed";
export {
  buildReport,
  buildVisibility,
  repaymentLabel,
  determineFiscalBox,
  buildTaxQualificationText,
} from "./builders";

// --- Scenario text engine --------------------------------------------------

export {
  DEATH_TEXT,
  RETIREMENT_TEXT,
  DISABILITY_TEXT,
  UNEMPLOYMENT_TEXT,
  RELATIONSHIP_TEXT,
  DEATH_SINGLE_TEXT,
} from "./texts";

export { compactKeys, renderStandardScenario, renderRelationshipScenario } from "./scenario-renderer";

// --- Retirement analysis ---------------------------------------------------

export {
  analyzeRetirementScenario,
  buildRetirementAnalysisNarratives,
  calculateRetirementShortfall,
  getRetirementShortfallSeverity,
} from "./retirement";

// --- PDF mapper ------------------------------------------------------------

export { mapToPdf, formatMoney, formatPercentage, formatTermMonths } from "./pdf-mapper";
export type { PdfReport, PdfSection, PdfRow, PdfTable, PdfHighlight } from "./pdf-mapper";
