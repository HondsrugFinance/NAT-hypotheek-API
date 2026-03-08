// ============================================================================
// Adviesrapport — Report viewmodel builder
//
// Assembles ReportBuilderInput → ReportViewModel by combining computed fields,
// narrative text blocks and visibility flags into renderable sections.
// ============================================================================

import type {
  AffordabilitySection,
  Applicant,
  ClientProfileSection,
  ComputedFields,
  DisclaimerSection,
  FinancingSection,
  LabelValueRow,
  LoanPartRow,
  LoanPartsSection,
  MoneyRow,
  NewLoanPart,
  PropertySection,
  RepaymentType,
  ReportBuilderInput,
  ReportMetaSection,
  ReportVisibility,
  ReportViewModel,
  RetirementSection,
  RisksSection,
  SummarySection,
  TaxSection,
} from "./types";
import { buildComputedFields, buildFullName, formatAddressInline } from "./computed";
import {
  buildAffordabilityNarratives,
  buildAttentionPoints,
  buildDeathRiskNarratives,
  buildDisabilityRiskNarratives,
  buildDisclaimerNarratives,
  buildLoanPartNarratives,
  buildRetirementNarratives,
  buildSummaryNarratives,
  buildTaxNarratives,
  buildUnemploymentRiskNarratives,
} from "./texts";

// --- Internal helpers ------------------------------------------------------

/** Safe number coercion: null/undefined/NaN → 0. */
const num = (v: number | null | undefined): number =>
  typeof v === "number" && !Number.isNaN(v) ? v : 0;

/** Push a MoneyRow only when amount > 0. */
const addIfPositive = (
  rows: MoneyRow[],
  label: string,
  amount: number | null | undefined,
): void => {
  if (amount && amount > 0) rows.push({ label, amount });
};

// --- Exported helpers (unit-testable) --------------------------------------

/** Display label for repayment type. */
export const repaymentLabel = (type?: RepaymentType | null): string => {
  switch (type) {
    case "annuiteit":
      return "Annuïteit";
    case "lineair":
      return "Lineair";
    case "aflossingsvrij":
      return "Aflossingsvrij";
    case "overbrugging":
      return "Overbrugging";
    case "spaarhypotheek":
      return "Spaarhypotheek";
    default:
      return type ?? "Onbekend";
  }
};

/** Determine fiscal box from box1/box3 amounts on a loan part. */
export const determineFiscalBox = (
  part: NewLoanPart,
): "box1" | "box3" | "gemengd" => {
  const hasBox1 = num(part.bedragBox1) > 0;
  const hasBox3 = num(part.bedragBox3) > 0;
  if (hasBox1 && hasBox3) return "gemengd";
  if (hasBox3) return "box3";
  return "box1";
};

/** Build a human-readable tax qualification description. */
export const buildTaxQualificationText = (computed: ComputedFields): string => {
  if (computed.hasBox1Part && computed.hasBox3Part) {
    return (
      "De hypotheek bevat zowel een eigenwoningschuld (box 1) " +
      "als een leningdeel in box 3."
    );
  }
  if (computed.hasBox3Part) {
    return (
      "De hypotheek valt fiscaal in box 3. " +
      "De betaalde rente is niet aftrekbaar als eigenwoningrente."
    );
  }
  return "De hypotheek kwalificeert als eigenwoningschuld (box 1).";
};

// --- Row builders ----------------------------------------------------------

/** Build LabelValueRow[] from an Applicant's personal data. */
const buildPersonRows = (
  person: Applicant,
  prefix: string,
): LabelValueRow[] => {
  const rows: LabelValueRow[] = [];
  const name = buildFullName(person);
  if (name) rows.push({ label: `${prefix} \u2014 Naam`, value: name });
  if (person.geboortedatum)
    rows.push({ label: `${prefix} \u2014 Geboortedatum`, value: person.geboortedatum });
  if (person.adres) {
    const addr = formatAddressInline(person.adres);
    if (addr) rows.push({ label: `${prefix} \u2014 Adres`, value: addr });
  }
  if (person.telefoon)
    rows.push({ label: `${prefix} \u2014 Telefoon`, value: person.telefoon });
  if (person.email)
    rows.push({ label: `${prefix} \u2014 E-mail`, value: person.email });
  return rows;
};

const buildApplicantRows = (input: ReportBuilderInput): LabelValueRow[] => {
  const rows = buildPersonRows(input.applicants.primary, "Aanvrager");
  if (input.applicants.hasPartner && input.applicants.partner) {
    rows.push(...buildPersonRows(input.applicants.partner, "Partner"));
  }
  return rows;
};

const buildIncomeRows = (
  computed: ComputedFields,
  hasPartner: boolean,
): MoneyRow[] => {
  const rows: MoneyRow[] = [
    { label: "Bruto jaarinkomen aanvrager", amount: computed.grossIncomeApplicantTotal },
  ];
  if (hasPartner) {
    rows.push({
      label: "Bruto jaarinkomen partner",
      amount: computed.grossIncomePartnerTotal,
    });
  }
  rows.push({
    label: "Totaal huishoudinkomen",
    amount: computed.grossIncomeHouseholdTotal,
  });
  return rows;
};

const buildAssetRows = (computed: ComputedFields): MoneyRow[] => {
  const rows: MoneyRow[] = [];
  addIfPositive(rows, "Spaargeld", computed.totalSavings);
  addIfPositive(rows, "Beleggingen", computed.totalInvestments);
  addIfPositive(rows, "Overige activa", computed.totalOtherAssets);
  rows.push({ label: "Totaal vermogen", amount: computed.totalAssets });
  return rows;
};

const buildObligationRows = (computed: ComputedFields): MoneyRow[] => {
  const rows: MoneyRow[] = [];
  addIfPositive(rows, "BKR-verplichtingen (per maand)", computed.totalBkrMonthly);
  addIfPositive(rows, "Overige kredieten (per maand)", computed.totalNonBkrMonthly);
  addIfPositive(rows, "Private lease (per maand)", computed.totalPrivateLeaseMonthly);
  addIfPositive(rows, "Studieschuld (per maand)", computed.totalStudyLoanMonthly);
  addIfPositive(rows, "Partneralimentatie (per maand)", computed.totalAlimonyPaidMonthly);
  if (computed.totalObligationsMonthly > 0) {
    rows.push({
      label: "Totaal maandlasten verplichtingen",
      amount: computed.totalObligationsMonthly,
    });
  }
  return rows;
};

const buildCostRows = (input: ReportBuilderInput): MoneyRow[] => {
  const rows: MoneyRow[] = [];
  const costs = input.financingSetup.costs;

  addIfPositive(rows, "Koopsom", input.objective.purchasePrice);
  addIfPositive(rows, "Overdrachtsbelasting", costs.transferTaxAmount);
  addIfPositive(rows, "Taxatiekosten", costs.valuationCost);
  addIfPositive(rows, "Advies- en bemiddelingskosten", costs.adviceCost);
  addIfPositive(rows, "Notariskosten", costs.notaryCost);
  addIfPositive(rows, "Makelaarskosten", costs.brokerCost);
  addIfPositive(rows, "Boeterente", costs.penaltyInterest);
  addIfPositive(rows, "Overige kosten", costs.otherCosts);

  if (input.financingSetup.nhg.selected) {
    addIfPositive(rows, "NHG-borgtochtprovisie", input.financingSetup.nhg.feeAmount);
  }

  return rows;
};

const buildEquityRows = (input: ReportBuilderInput): MoneyRow[] => {
  const rows: MoneyRow[] = [];
  const equity = input.financingSetup.equity;

  addIfPositive(rows, "Eigen spaargeld", equity.savingsContribution);
  addIfPositive(rows, "Schenking", equity.gift);
  addIfPositive(rows, "Starterslening", equity.starterLoan);

  return rows;
};

const buildLoanPartRowData = (
  part: NewLoanPart,
  index: number,
): LoanPartRow => ({
  leningdeel: part.id || `Deel ${index + 1}`,
  bedrag: num(part.bedragBox1) + num(part.bedragBox3),
  aflosvorm: repaymentLabel(part.aflosvorm),
  rentepercentage: part.rentepercentage ?? null,
  rentevastePeriode: part.rentevastePeriode ?? null,
  looptijdMaanden: part.looptijdMaanden ?? null,
  fiscaleBox: determineFiscalBox(part),
});

// --- Visibility builder ----------------------------------------------------

/** Derive which sections and subsections should be rendered. */
export const buildVisibility = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): ReportVisibility => ({
  showPartner: input.applicants.hasPartner,
  showRetirement:
    computed.retirementScenarioRequired ||
    computed.pensionIncomeApplicantTotal > 0 ||
    computed.pensionIncomePartnerTotal > 0,
  showBox3: computed.hasBox3Part,
  showEquityReserve:
    computed.hasEquityReserve && num(computed.equityReserveAmount) > 0,
  showOrvAdvice: !computed.hasOrv && input.applicants.hasPartner,
  showNhg: Boolean(input.financingSetup.nhg.selected),
  showGroundLease: num(input.property.groundLeaseAnnual) > 0,
  showRenovationValue:
    num(input.property.marketValueAfterRenovation) > 0 &&
    num(input.property.marketValueAfterRenovation) !==
      num(input.property.marketValue),
  showMaxMortgageRetirement: computed.retirementScenarioRequired,
});

// --- Section builders ------------------------------------------------------

const buildMetaSection = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): ReportMetaSection => ({
  title: "Adviesrapport Hypotheek",
  date: input.dossier.adviesDatum,
  dossierNumber: input.dossier.dossierNummer,
  advisor: input.dossier.adviseurNaam,
  customerName: computed.customerDisplayName,
  propertyAddress: computed.propertyAddressLine,
});

const buildSummarySection = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): SummarySection => ({
  objectiveLabel: computed.objectiveLabel,
  mortgageAmount: computed.requiredMortgageAmount,
  lender: input.newMortgage.lender ?? "",
  productLine: input.newMortgage.productLine ?? "",
  grossMonthly: computed.grossMonthlyPaymentTotal,
  netMonthly: computed.netMonthlyPaymentTotal,
  equityContribution: computed.totalOwnFunds,
  narrativeBlocks: buildSummaryNarratives(input, computed),
});

const buildClientProfileSection = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): ClientProfileSection => ({
  householdText: computed.householdCompositionText,
  applicants: buildApplicantRows(input),
  incomeRows: buildIncomeRows(computed, input.applicants.hasPartner),
  assetRows: buildAssetRows(computed),
  obligationRows: buildObligationRows(computed),
});

const buildPropertySection = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): PropertySection => ({
  address: computed.propertyAddressLine,
  propertyType: input.property.propertyType ?? "",
  marketValue: computed.effectiveMarketValue,
  marketValueAfterRenovation: input.property.marketValueAfterRenovation ?? null,
  constructionYear: input.property.constructionYear ?? null,
  energyLabel: input.property.energyLabel ?? "",
  groundLeaseAnnual: input.property.groundLeaseAnnual ?? null,
  ltvPercentage: computed.ltvPercentage,
});

const buildAffordabilitySection = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): AffordabilitySection => ({
  testIncome: num(input.calculations.maxMortgageNow?.toetsinkomen),
  maxMortgageNow: num(input.calculations.maxMortgageNow?.maximaleHypotheekBox1),
  maxMortgageRetirement:
    input.calculations.maxMortgageRetirement?.maximaleHypotheekBox1 ?? null,
  advisedMortgage: computed.requiredMortgageAmount,
  grossMonthly: computed.grossMonthlyPaymentTotal,
  taxBenefitMonthly: computed.taxBenefitMonthly,
  netMonthly: computed.netMonthlyPaymentTotal,
  narrativeBlocks: buildAffordabilityNarratives(input, computed),
});

const buildFinancingSection = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): FinancingSection => ({
  costRows: buildCostRows(input),
  equityRows: buildEquityRows(input),
  totalInvestment: computed.totalInvestment,
  totalEquity: computed.totalOwnFunds,
  requiredMortgage: computed.requiredMortgageAmount,
});

const buildLoanPartsSection = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): LoanPartsSection => ({
  lender: input.newMortgage.lender ?? "",
  productLine: input.newMortgage.productLine ?? "",
  rows: input.newMortgage.loanParts.map(buildLoanPartRowData),
  narrativeBlocks: buildLoanPartNarratives(input, computed),
});

const buildTaxSection = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): TaxSection => ({
  qualificationText: buildTaxQualificationText(computed),
  interestDeductionEndYear: computed.interestDeductionEndYear,
  hasEquityReserve: computed.hasEquityReserve,
  equityReserveAmount: computed.equityReserveAmount,
  hasBox3Part: computed.hasBox3Part,
  narrativeBlocks: buildTaxNarratives(input, computed),
});

const buildRisksSection = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): RisksSection => ({
  death: {
    hasOrv: computed.hasOrv,
    coverageAmount: computed.totalOrvCoverage,
    narrativeBlocks: buildDeathRiskNarratives(input, computed),
  },
  disability: {
    hasAov: computed.hasAov,
    narrativeBlocks: buildDisabilityRiskNarratives(),
  },
  unemployment: {
    liquidBuffer: computed.liquidBuffer,
    narrativeBlocks: buildUnemploymentRiskNarratives(),
  },
});

const buildRetirementSection = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): RetirementSection => ({
  show:
    computed.retirementScenarioRequired ||
    computed.pensionIncomeApplicantTotal > 0 ||
    computed.pensionIncomePartnerTotal > 0,
  expectedIncome:
    computed.pensionIncomeApplicantTotal + computed.pensionIncomePartnerTotal,
  narrativeBlocks: buildRetirementNarratives(input, computed),
});

const buildDisclaimerSection = (): DisclaimerSection => ({
  narrativeBlocks: buildDisclaimerNarratives(),
});

// --- Main entry point ------------------------------------------------------

/**
 * Build a complete ReportViewModel from raw dossier input.
 *
 * This is the single entry point for report generation. It:
 * 1. Derives all computed fields from the raw input
 * 2. Generates conditional narrative text blocks
 * 3. Determines section visibility
 * 4. Assembles each section into a flat, renderable viewmodel
 *
 * The viewmodel contains raw numbers (Money, Percentage) — formatting
 * is the responsibility of the rendering layer (see pdf-mapper.ts).
 */
export const buildReport = (
  input: ReportBuilderInput,
): ReportViewModel => {
  const computed = buildComputedFields(input);

  return {
    meta: buildMetaSection(input, computed),
    summary: buildSummarySection(input, computed),
    clientProfile: buildClientProfileSection(input, computed),
    property: buildPropertySection(input, computed),
    affordability: buildAffordabilitySection(input, computed),
    financing: buildFinancingSection(input, computed),
    loanParts: buildLoanPartsSection(input, computed),
    tax: buildTaxSection(input, computed),
    risks: buildRisksSection(input, computed),
    retirement: buildRetirementSection(input, computed),
    attentionPoints: { items: buildAttentionPoints(input, computed) },
    disclaimer: buildDisclaimerSection(),
    visibility: buildVisibility(input, computed),
  };
};
