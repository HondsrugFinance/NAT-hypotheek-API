// ============================================================================
// Adviesrapport — Computed fields (pure derivations from raw input)
// ============================================================================

import type {
  Address,
  AssetItem,
  ComputedFields,
  CreditObligation,
  Money,
  NewLoanPart,
  PartnerAlimonyPaid,
  PersonIncome,
  PrivateLeaseObligation,
  ReportBuilderInput,
  StudyLoanObligation,
} from "./types";

// --- Internal helpers ------------------------------------------------------

/** Safe number coercion: null/undefined/NaN → 0. */
const n = (value: number | null | undefined): number => {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  return value;
};

const safeArray = <T>(value: T[] | null | undefined): T[] => value ?? [];

const sum = (values: Array<number | null | undefined>): number =>
  values.reduce((acc, v) => acc + n(v), 0);

const sumBy = <T>(
  items: Array<T | null | undefined>,
  getter: (item: T) => number | null | undefined,
): number => items.reduce((acc, item) => acc + (item ? n(getter(item)) : 0), 0);

const joinNonEmpty = (
  parts: Array<string | null | undefined>,
  separator = " ",
): string =>
  parts
    .map((p) => (p ?? "").trim())
    .filter(Boolean)
    .join(separator)
    .trim();

// --- Exported utilities (also used by builders.ts) -------------------------

/** Format an Address as a single inline string. */
export const formatAddressInline = (address?: Address | null): string => {
  if (!address) return "";
  const street = joinNonEmpty(
    [address.straat, address.huisnummer, address.huisnummerToevoeging],
    " ",
  );
  const city = joinNonEmpty([address.postcode, address.woonplaats], " ");
  return joinNonEmpty([street, city], ", ");
};

/** Build a display name from name parts. */
export const buildFullName = (person: {
  voornamen?: string | null;
  roepnaam?: string | null;
  tussenvoegsel?: string | null;
  achternaam?: string | null;
}): string => {
  const first = person.roepnaam || person.voornamen || "";
  return joinNonEmpty([first, person.tussenvoegsel, person.achternaam], " ");
};

// --- Income aggregation ----------------------------------------------------

const sumEmployment = (pi?: PersonIncome | null): Money =>
  sumBy(safeArray(pi?.employment), (i) => i.jaarbedrag);

const sumPension = (pi?: PersonIncome | null): Money =>
  sumBy(safeArray(pi?.pension), (i) => i.jaarbedrag);

const sumAnnuity = (pi?: PersonIncome | null): Money =>
  sumBy(safeArray(pi?.annuity), (i) => i.jaarbedrag);

const sumRental = (pi?: PersonIncome | null): Money =>
  sumBy(safeArray(pi?.rental), (i) => i.jaarbedrag);

const sumAlimonyReceived = (pi?: PersonIncome | null): Money =>
  sumBy(safeArray(pi?.partnerAlimonyReceived), (i) => n(i.maandbedrag) * 12);

const sumOther = (pi?: PersonIncome | null): Money =>
  sumBy(safeArray(pi?.other), (i) => i.jaarbedrag);

const sumGrossIncome = (pi?: PersonIncome | null): Money =>
  sum([
    sumEmployment(pi),
    sumPension(pi),
    sumAnnuity(pi),
    sumRental(pi),
    sumAlimonyReceived(pi),
    sumOther(pi),
  ]);

// --- Obligation aggregation ------------------------------------------------

const sumAssetItems = (items?: AssetItem[] | null): Money =>
  sumBy(safeArray(items), (i) => i.bedrag);

const sumCreditMonthly = (items?: CreditObligation[] | null): Money =>
  sumBy(safeArray(items), (i) => {
    if (i.maandlast != null) return i.maandlast;
    if (i.limiet != null) return i.limiet * 0.02;
    return 0;
  });

const sumPrivateLeaseMonthly = (items?: PrivateLeaseObligation[] | null): Money =>
  sumBy(safeArray(items), (i) => i.maandbedrag);

const sumStudyLoanMonthly = (items?: StudyLoanObligation[] | null): Money =>
  sumBy(safeArray(items), (i) => i.maandlast);

const sumAlimonyPaidMonthly = (items?: PartnerAlimonyPaid[] | null): Money =>
  sumBy(safeArray(items), (i) => i.maandbedrag);

// --- Loan helpers ----------------------------------------------------------

const loanPartTotal = (part: NewLoanPart): Money =>
  n(part.bedragBox1) + n(part.bedragBox3);

// --- Label helpers ---------------------------------------------------------

const determineObjectiveLabel = (type?: string | null): string => {
  switch (type) {
    case "aankoop-bestaande-bouw":
      return "Aankoop bestaande woning";
    case "aankoop-nieuwbouw":
      return "Aankoop nieuwbouwwoning";
    case "aankoop-eigen-beheer":
      return "Aankoop in eigen beheer";
    case "hypotheek-verhogen":
      return "Hypotheek verhogen";
    case "hypotheek-oversluiten":
      return "Hypotheek oversluiten";
    case "partner-uitkopen":
      return "Partner uitkopen";
    default:
      return "Hypotheekaanvraag";
  }
};

const buildHouseholdText = (input: ReportBuilderInput): string => {
  const detail = joinNonEmpty(
    [input.household.burgerlijkeStaat, input.household.samenlevingsvorm],
    ", ",
  );
  if (input.applicants.hasPartner) {
    return detail
      ? `Aanvraag met partner, ${detail}.`
      : "Aanvraag met partner.";
  }
  return "Aanvraag zonder partner.";
};

// --- Main builder ----------------------------------------------------------

/** Derive all computed fields from raw dossier input. */
export const buildComputedFields = (input: ReportBuilderInput): ComputedFields => {
  const applicantFullName = buildFullName(input.applicants.primary);
  const partnerFullName = input.applicants.hasPartner
    ? buildFullName(input.applicants.partner ?? {})
    : "";
  const customerDisplayName =
    input.applicants.hasPartner && partnerFullName
      ? `${applicantFullName} en ${partnerFullName}`
      : applicantFullName;

  const propertyAddressLine = formatAddressInline(input.property.address);

  // Income
  const grossIncomeApplicantTotal = sumGrossIncome(input.income.primary);
  const grossIncomePartnerTotal = sumGrossIncome(input.income.partner);
  const grossIncomeHouseholdTotal = grossIncomeApplicantTotal + grossIncomePartnerTotal;
  const pensionIncomeApplicantTotal = sumPension(input.income.primary);
  const pensionIncomePartnerTotal = sumPension(input.income.partner);

  // Assets
  const totalSavings = sumAssetItems(input.assets.savings);
  const totalInvestments = sumAssetItems(input.assets.investments);
  const totalOtherAssets = sumAssetItems(input.assets.otherAssets);
  const totalAssets = totalSavings + totalInvestments + totalOtherAssets;

  // Obligations
  const totalBkrMonthly = sumCreditMonthly(input.obligations.bkr);
  const totalNonBkrMonthly = sumCreditMonthly(input.obligations.nonBkr);
  const totalPrivateLeaseMonthly = sumPrivateLeaseMonthly(input.obligations.privateLease);
  const totalStudyLoanMonthly = sumStudyLoanMonthly(input.obligations.studyLoans);
  const totalAlimonyPaidMonthly = sumAlimonyPaidMonthly(input.obligations.partnerAlimonyPaid);
  const totalObligationsMonthly =
    totalBkrMonthly +
    totalNonBkrMonthly +
    totalPrivateLeaseMonthly +
    totalStudyLoanMonthly +
    totalAlimonyPaidMonthly;

  // Property & mortgage
  const effectiveMarketValue =
    n(input.property.marketValueAfterRenovation) || n(input.property.marketValue);
  const totalMortgageAmount = sumBy(input.newMortgage.loanParts, loanPartTotal);
  const ltvPercentage =
    effectiveMarketValue > 0
      ? (totalMortgageAmount / effectiveMarketValue) * 100
      : null;

  // Financing
  const totalInvestment =
    n(input.financingSetup.totalInvestment) ||
    n(input.objective.purchasePrice) + n(input.financingSetup.totalCosts);
  const totalOwnFunds =
    n(input.financingSetup.totalEquity) ||
    n(input.financingSetup.equity.savingsContribution) +
      n(input.financingSetup.equity.gift) +
      n(input.financingSetup.equity.starterLoan);
  const requiredMortgageAmount =
    n(input.financingSetup.requiredMortgageAmount) || totalMortgageAmount;

  // Monthly costs
  const grossMonthlyPaymentTotal = n(input.calculations.monthlyCosts?.brutoMaandlast);
  const taxBenefitMonthly = n(input.calculations.monthlyCosts?.renteaftrek);
  const netMonthlyPaymentTotal = n(input.calculations.monthlyCosts?.nettoMaandlast);

  // Loan part flags
  const parts = input.newMortgage.loanParts;
  const hasAnnuityPart = parts.some((p) => p.aflosvorm === "annuiteit");
  const hasLinearPart = parts.some((p) => p.aflosvorm === "lineair");
  const hasInterestOnlyPart = parts.some((p) => p.aflosvorm === "aflossingsvrij");
  const hasBridgeLoanPart = parts.some((p) => p.aflosvorm === "overbrugging");
  const hasSavingsMortgagePart = parts.some((p) => p.aflosvorm === "spaarhypotheek");

  const totalBox1Loan = sumBy(parts, (p) => p.bedragBox1);
  const totalBox3Loan = sumBy(parts, (p) => p.bedragBox3);
  const hasBox1Part = totalBox1Loan > 0;
  const hasBox3Part = totalBox3Loan > 0 || n(input.fiscalHistory.box3LoanAmount) > 0;

  // Fiscal
  const qualifiesForInterestDeduction = hasBox1Part;
  const remainingInterestDeductionYears =
    input.fiscalHistory.remainingInterestDeductionMonths != null
      ? Math.floor(input.fiscalHistory.remainingInterestDeductionMonths / 12)
      : null;
  const hasEquityReserve = Boolean(input.fiscalHistory.hasEquityReserve);
  const equityReserveAmount = input.fiscalHistory.equityReserveAmount ?? null;

  // Protections
  const hasOrv = input.protections.orv.length > 0;
  const totalOrvCoverage = sumBy(input.protections.orv, (i) => i.verzekerdBedrag);
  const hasAov = input.protections.aov.length > 0;
  const hasLifeInsurance = input.protections.lifeInsurance.length > 0;
  const hasAnnuityIncome =
    sumAnnuity(input.income.primary) > 0 ||
    sumAnnuity(input.income.partner) > 0;
  const hasPartnerIncome =
    input.applicants.hasPartner && sumGrossIncome(input.income.partner) > 0;

  // Buffer
  const liquidBuffer = totalSavings;
  const bufferMonthsEstimate =
    netMonthlyPaymentTotal > 0
      ? Math.floor(liquidBuffer / netMonthlyPaymentTotal)
      : null;

  const retirementScenarioRequired = Boolean(input.calculations.maxMortgageRetirement);

  return {
    applicantFullName,
    partnerFullName,
    customerDisplayName,
    propertyAddressLine,
    householdCompositionText: buildHouseholdText(input),
    grossIncomeApplicantTotal,
    grossIncomePartnerTotal,
    grossIncomeHouseholdTotal,
    pensionIncomeApplicantTotal,
    pensionIncomePartnerTotal,
    totalSavings,
    totalInvestments,
    totalOtherAssets,
    totalAssets,
    totalBkrMonthly,
    totalNonBkrMonthly,
    totalPrivateLeaseMonthly,
    totalStudyLoanMonthly,
    totalAlimonyPaidMonthly,
    totalObligationsMonthly,
    effectiveMarketValue,
    totalMortgageAmount,
    ltvPercentage,
    totalInvestment,
    totalOwnFunds,
    requiredMortgageAmount,
    grossMonthlyPaymentTotal,
    taxBenefitMonthly,
    netMonthlyPaymentTotal,
    hasAnnuityPart,
    hasLinearPart,
    hasInterestOnlyPart,
    hasBridgeLoanPart,
    hasSavingsMortgagePart,
    hasBox1Part,
    hasBox3Part,
    totalBox1Loan,
    totalBox3Loan,
    qualifiesForInterestDeduction,
    remainingInterestDeductionYears,
    interestDeductionEndYear: input.fiscalHistory.interestDeductionEndYear ?? null,
    hasEquityReserve,
    equityReserveAmount,
    hasOrv,
    totalOrvCoverage,
    hasAov,
    hasLifeInsurance,
    hasAnnuityIncome,
    hasPartnerIncome,
    liquidBuffer,
    bufferMonthsEstimate,
    retirementScenarioRequired,
    objectiveLabel: determineObjectiveLabel(input.objective.type),
  };
};
