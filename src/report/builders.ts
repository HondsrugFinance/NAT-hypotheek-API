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
  NarrativeBlock,
  NewLoanPart,
  PropertySection,
  RelationshipRiskSection,
  RepaymentType,
  ReportBuilderInput,
  ReportMetaSection,
  ReportVisibility,
  ReportViewModel,
  RetirementSection,
  RisksSection,
  StandardAdviceType,
  StandardScenarioStatus,
  SummarySection,
  TaxSection,
} from "./types";
import { buildComputedFields, buildFullName, formatAddressInline } from "./computed";
import {
  buildAffordabilityNarratives,
  buildAttentionPoints,
  DEATH_SINGLE_TEXT,
  DEATH_TEXT,
  buildDisclaimerNarratives,
  DISABILITY_TEXT,
  buildLoanPartNarratives,
  RELATIONSHIP_TEXT,
  RETIREMENT_TEXT,
  buildSummaryNarratives,
  buildTaxNarratives,
  UNEMPLOYMENT_TEXT,
  ADVICE_RISK_LABELS,
} from "./texts";
import { analyzeRetirementScenario } from "./retirement";
import { compactKeys, renderRelationshipScenario, renderStandardScenario } from "./scenario-renderer";

// --- Internal helpers ------------------------------------------------------

/** Safe number coercion: null/undefined/NaN → 0. */
const num = (v: number | null | undefined): number =>
  typeof v === "number" && !Number.isNaN(v) ? v : 0;

/** Wrap plain strings from a renderer into NarrativeBlock[]. */
const toNarrativeBlocks = (prefix: string, texts: string[]): NarrativeBlock[] =>
  texts.map((text, i) => ({ key: `${prefix}-${i}`, text }));

/** Format a number as Dutch currency for inline text (whole euros only). */
const fmtMoney = (amount: number): string => {
  const whole = Math.round(Math.abs(amount)).toString();
  const thousands = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return amount < 0 ? `\u20ac -${thousands}` : `\u20ac ${thousands}`;
};

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
  showRelationship: input.applicants.hasPartner,
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

// --- Advice text builder (Samenvatting — Advies en onderbouwing) -----------

const summariseRepaymentTypes = (parts: ReportBuilderInput["newMortgage"]["loanParts"]): string => {
  const types = [...new Set(parts.map((p) => repaymentLabel(p.aflosvorm).toLowerCase()))];
  if (types.length === 1) return `een ${types[0]}e`;
  return `een combinatie van ${types.slice(0, -1).join(", ")} en ${types[types.length - 1]}`;
};

const longestRvp = (parts: ReportBuilderInput["newMortgage"]["loanParts"]): string => {
  const periods = parts
    .map((p) => p.rentevastePeriode)
    .filter((v): v is string => !!v);
  if (periods.length === 0) return "";
  // Sort descending by numeric prefix (e.g. "20 jaar" > "10 jaar")
  periods.sort((a, b) => {
    const na = parseInt(a, 10) || 0;
    const nb = parseInt(b, 10) || 0;
    return nb - na;
  });
  return periods[0];
};

const buildAdviceText = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): string[] => {
  const paragraphs: string[] = [];

  // Alinea 1 — Hypotheekadvies
  const lender = input.newMortgage.lender ?? "de geldverstrekker";
  const repayment = summariseRepaymentTypes(input.newMortgage.loanParts);
  const rvp = longestRvp(input.newMortgage.loanParts);
  let p1 = `Wij adviseren een hypotheek van ${fmtMoney(computed.requiredMortgageAmount)} bij ${lender}` +
    `, met ${repayment} aflossingsvorm` +
    (rvp ? ` en een rentevaste periode van ${rvp}` : "") +
    ".";
  if (input.financingSetup.nhg.selected) {
    p1 += " De hypotheek wordt aangevraagd met Nationale Hypotheek Garantie.";
  }
  paragraphs.push(p1);

  // Alinea 2 — Betaalbaarheid
  const maxNow = num(input.calculations.maxMortgageNow?.maximaleHypotheekBox1);
  const marge = maxNow > 0 && computed.requiredMortgageAmount <= maxNow * 0.9 ? "ruim " : "";
  paragraphs.push(
    `De bruto maandlast bedraagt ${fmtMoney(computed.grossMonthlyPaymentTotal)}, ` +
    `wat na belastingvoordeel neerkomt op een netto maandlast van ${fmtMoney(computed.netMonthlyPaymentTotal)}. ` +
    `Het geadviseerde hypotheekbedrag past ${marge}binnen de maximaal toegestane hypotheek van ${fmtMoney(maxNow)}.`,
  );

  // Alinea 3 — Risico-overzicht
  const riskParts: string[] = [];

  // Overlijden
  if (!input.applicants.hasPartner) {
    riskParts.push("Overlijden: niet van toepassing (alleenstaand)");
  } else {
    const death = deriveDeathStatus(input, computed);
    riskParts.push(`Overlijden: ${ADVICE_RISK_LABELS[death.status] ?? death.status}`);
  }

  // AO
  const disability = deriveDisabilityStatus(computed);
  const aoLabel = ADVICE_RISK_LABELS[disability.status] ?? disability.status;
  riskParts.push(
    disability.adviceType === "refer_to_specialist"
      ? `Arbeidsongeschiktheid: ${aoLabel}, verwijzing naar specialist`
      : `Arbeidsongeschiktheid: ${aoLabel}`,
  );

  // WW
  const unemployment = deriveUnemploymentStatus(computed);
  const wwLabel = ADVICE_RISK_LABELS[unemployment.status] ?? unemployment.status;
  if (unemployment.status === "affordable") {
    riskParts.push("Werkloosheid: voldoende buffer");
  } else {
    riskParts.push(`Werkloosheid: ${wwLabel}`);
  }

  // Pensioen
  riskParts.push("Pensionering: afgedekt");

  paragraphs.push(riskParts.join(". ") + ".");

  // Alinea 4 — Klantprioriteit (conditioneel)
  const priority = input.adviceProfile.customerPriority?.trim();
  if (priority) {
    paragraphs.push(
      `Bij dit advies is rekening gehouden met uw prioriteit: ${priority.toLowerCase()}.`,
    );
  }

  return paragraphs;
};

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
  adviceText: buildAdviceText(input, computed),
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

// --- Scenario status derivation --------------------------------------------

const deriveDeathStatus = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): { status: StandardScenarioStatus; adviceType: StandardAdviceType } => {
  if (!input.applicants.hasPartner) return { status: "affordable", adviceType: "no_action" };
  if (computed.hasOrv) return { status: "resolved", adviceType: "no_action" };
  if (input.adviceProfile.customerRejectedOrv) return { status: "attention", adviceType: "awareness_only" };
  return { status: "attention", adviceType: "consider_solution" };
};

const deriveDisabilityStatus = (
  computed: ComputedFields,
): { status: StandardScenarioStatus; adviceType: StandardAdviceType } => {
  if (computed.hasAov) return { status: "resolved", adviceType: "no_action" };
  return { status: "attention", adviceType: "refer_to_specialist" };
};

const deriveUnemploymentStatus = (
  computed: ComputedFields,
): { status: StandardScenarioStatus; adviceType: StandardAdviceType } => {
  const months = computed.bufferMonthsEstimate;
  if (months != null && months >= 6) return { status: "affordable", adviceType: "no_action" };
  if (months != null && months >= 3) return { status: "attention", adviceType: "consider_solution" };
  return { status: "attention", adviceType: "consider_solution" };
};

// --- Risks section builder -------------------------------------------------

const buildDeathRiskNarratives = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): NarrativeBlock[] => {
  // Single applicant: centralised texts assume couple, use fallback
  if (!input.applicants.hasPartner) {
    return [{ key: "death-single", text: DEATH_SINGLE_TEXT }];
  }

  const { status, adviceType } = deriveDeathStatus(input, computed);
  const nuanceKeys = compactKeys(
    ["existing_orv", computed.hasOrv],
    ["existing_life_insurance", computed.hasLifeInsurance],
    ["savings_used", false], // no savings-buffer calculation yet
    ["employer_provisions_unknown", true], // always include
  );

  return toNarrativeBlocks("death", renderStandardScenario({
    text: DEATH_TEXT,
    status,
    adviceType,
    nuanceKeys,
  }));
};

const buildDisabilityRiskNarratives = (
  computed: ComputedFields,
): NarrativeBlock[] => {
  const { status, adviceType } = deriveDisabilityStatus(computed);
  const nuanceKeys = compactKeys(
    ["aov_used", computed.hasAov],
    ["partner_income_used", computed.hasPartnerIncome],
  );

  return toNarrativeBlocks("disability", renderStandardScenario({
    text: DISABILITY_TEXT,
    status,
    adviceType,
    nuanceKeys,
  }));
};

const buildUnemploymentRiskNarratives = (
  computed: ComputedFields,
): NarrativeBlock[] => {
  const { status, adviceType } = deriveUnemploymentStatus(computed);
  const nuanceKeys = compactKeys(
    ["woonlastenverzekering_used", false], // no woonlastenverzekering data yet
    ["partner_income_used", computed.hasPartnerIncome],
  );

  return toNarrativeBlocks("unemployment", renderStandardScenario({
    text: UNEMPLOYMENT_TEXT,
    status,
    adviceType,
    nuanceKeys,
  }));
};

const buildRelationshipRiskSection = (
  input: ReportBuilderInput,
  _computed: ComputedFields,
): RelationshipRiskSection | null => {
  if (!input.applicants.hasPartner) return null;

  // Default to 'attention' for both — refined when calculations are added
  const applicantStatus = "attention" as const;
  const partnerStatus = "attention" as const;
  const overallStatus = "affordable_for_none" as const;

  const paragraphs = renderRelationshipScenario({
    text: RELATIONSHIP_TEXT,
    overallStatus,
    applicantStatus,
    partnerStatus,
  });

  return {
    overallStatus,
    applicantStatus,
    partnerStatus,
    narrativeBlocks: toNarrativeBlocks("relationship", paragraphs),
  };
};

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
    narrativeBlocks: buildDisabilityRiskNarratives(computed),
  },
  unemployment: {
    liquidBuffer: computed.liquidBuffer,
    narrativeBlocks: buildUnemploymentRiskNarratives(computed),
  },
  relationship: buildRelationshipRiskSection(input, computed),
});

const buildRetirementSection = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): RetirementSection => {
  const show =
    computed.retirementScenarioRequired ||
    computed.pensionIncomeApplicantTotal > 0 ||
    computed.pensionIncomePartnerTotal > 0;
  const expectedIncome =
    computed.pensionIncomeApplicantTotal + computed.pensionIncomePartnerTotal;

  // When retirement analysis input is provided, run the full scenario analysis
  if (input.retirementAnalysis && input.retirementAnalysis.moments.length > 0) {
    const analysis = analyzeRetirementScenario(input.retirementAnalysis);

    // Map analysis severity → standard status
    let status: StandardScenarioStatus = "affordable";
    let adviceType: StandardAdviceType = "no_action";
    if (analysis.hasShortfall) {
      const allLimited = analysis.moments.every(
        (m) => m.severity === "limited" || m.severity === "none",
      );
      status = allLimited ? "attention" : "shortfall";
      adviceType = allLimited ? "awareness_only" : "advise_extra_repayment";
    }

    // Determine retirement change pattern from scenario kind
    const isLaterShortfall =
      analysis.kind === "couple-shortfall-increasing" ||
      analysis.kind === "couple-none-then-shortfall";
    const isImproving = analysis.kind === "couple-shortfall-then-none";

    const nuanceKeys = compactKeys(
      ["couple_two_aow", input.applicants.hasPartner],
      ["income_decrease", expectedIncome < computed.grossIncomeHouseholdTotal],
      ["later_shortfall", isLaterShortfall],
      ["income_improves", isImproving],
      ["annuity_income_used", computed.hasAnnuityIncome],
    );

    return {
      show: true,
      expectedIncome,
      narrativeBlocks: toNarrativeBlocks("retirement", renderStandardScenario({
        text: RETIREMENT_TEXT,
        status,
        adviceType,
        nuanceKeys,
      })),
      analysis,
      advisorNote: input.retirementAnalysis.advisorNote ?? null,
    };
  }

  // Fallback: generic narratives without scenario analysis
  return {
    show,
    expectedIncome,
    narrativeBlocks: toNarrativeBlocks("retirement", renderStandardScenario({
      text: RETIREMENT_TEXT,
      status: "affordable",
      adviceType: "no_action",
    })),
    analysis: null,
    advisorNote: null,
  };
};

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
