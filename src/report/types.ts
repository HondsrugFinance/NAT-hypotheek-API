// ============================================================================
// Adviesrapport — Type definitions
// ============================================================================

// --- Primitives & utilities ------------------------------------------------

export type Nullable<T> = T | null;
export type Money = number;
export type Percentage = number;

// --- Dossier & personal data -----------------------------------------------

export interface Dossier {
  id: string;
  dossierNummer: string;
  adviesDatum: string;
  adviseurNaam: string;
  kantoorNaam: string;
}

export interface PersonName {
  voorletters?: string | null;
  voornamen?: string | null;
  roepnaam?: string | null;
  tussenvoegsel?: string | null;
  achternaam?: string | null;
}

export interface Address {
  straat?: string | null;
  huisnummer?: string | null;
  huisnummerToevoeging?: string | null;
  postcode?: string | null;
  woonplaats?: string | null;
  land?: string | null;
}

export interface Applicant extends PersonName {
  geslacht?: string | null;
  geboortedatum?: string | null;
  geboorteplaats?: string | null;
  geboorteland?: string | null;
  nationaliteit?: string | null;
  telefoon?: string | null;
  email?: string | null;
  adres?: Address | null;
}

export interface Applicants {
  hasPartner: boolean;
  primary: Applicant;
  partner?: Applicant | null;
}

export interface Household {
  burgerlijkeStaat?: string | null;
  samenlevingsvorm?: string | null;
  dependents?: number | null;
}

// --- Current situation -----------------------------------------------------

export interface Residence {
  adres?: Address | null;
  woningtype?: string | null;
  woontoepassing?: string | null;
  marktwaarde?: Money | null;
  bouwjaar?: number | null;
}

export type RepaymentType =
  | "annuiteit"
  | "lineair"
  | "aflossingsvrij"
  | "overbrugging"
  | "spaarhypotheek"
  | string;

export interface ExistingLoanPart {
  aflosvorm?: RepaymentType | null;
  hoofdsomBox1?: Money | null;
  hoofdsomBox3?: Money | null;
  looptijdMaanden?: number | null;
  rentepercentage?: Percentage | null;
  rentevastePeriode?: string | null;
  inlegOverig?: Money | null;
}

export interface ExistingMortgage {
  geldverstrekker?: string | null;
  hypotheeknummer?: string | null;
  ingangsdatum?: string | null;
  einddatum?: string | null;
  leningdelen?: ExistingLoanPart[] | null;
}

export interface CurrentSituation {
  residences: Residence[];
  mortgages: ExistingMortgage[];
}

// --- Income ----------------------------------------------------------------

export interface EmploymentIncome {
  soortDienstverband?: string | null;
  beroep?: string | null;
  jaarbedrag?: Money | null;
  urenPerWeek?: number | null;
  aantalWerkgevers?: number | null;
  arbeidsmarktscanFase?: string | null;
  ingangsdatum?: string | null;
  einddatum?: string | null;
}

export interface PensionIncome {
  jaarbedrag?: Money | null;
  ingangsdatum?: string | null;
}

export interface AnnuityIncome {
  jaarbedrag?: Money | null;
  ingangsdatum?: string | null;
  einddatum?: string | null;
}

export interface RentalIncome {
  jaarbedrag?: Money | null;
}

export interface PartnerAlimonyReceived {
  maandbedrag?: Money | null;
}

export interface OtherIncome {
  jaarbedrag?: Money | null;
}

export interface PersonIncome {
  employment: EmploymentIncome[];
  pension: PensionIncome[];
  annuity: AnnuityIncome[];
  rental: RentalIncome[];
  partnerAlimonyReceived: PartnerAlimonyReceived[];
  other: OtherIncome[];
}

export interface Income {
  primary: PersonIncome;
  partner?: PersonIncome | null;
}

// --- Obligations -----------------------------------------------------------

export interface CreditObligation {
  type?: string | null;
  maandlast?: Money | null;
  limiet?: Money | null;
  looptijdMaanden?: number | null;
}

export interface PrivateLeaseObligation {
  maandbedrag?: Money | null;
  looptijdMaanden?: number | null;
}

export interface StudyLoanObligation {
  maandlast?: Money | null;
  restschuld?: Money | null;
}

export interface PartnerAlimonyPaid {
  maandbedrag?: Money | null;
  ingangsdatum?: string | null;
  einddatum?: string | null;
}

export interface Obligations {
  bkr: CreditObligation[];
  nonBkr: CreditObligation[];
  privateLease: PrivateLeaseObligation[];
  studyLoans: StudyLoanObligation[];
  partnerAlimonyPaid: PartnerAlimonyPaid[];
}

// --- Protections (insurance) -----------------------------------------------

export interface AovPolicy {
  verzekeraar?: string | null;
  premie?: Money | null;
  type?: string | null;
}

export interface OrvPolicy {
  verzekeraar?: string | null;
  premie?: Money | null;
  verzekerdBedrag?: Money | null;
}

export interface LifeInsurancePolicy {
  verzekeraar?: string | null;
  premie?: Money | null;
}

export interface AnnuityPolicy {
  verzekeraar?: string | null;
  uitkeringswijze?: string | null;
}

export interface Protections {
  aov: AovPolicy[];
  orv: OrvPolicy[];
  lifeInsurance: LifeInsurancePolicy[];
  annuityPolicies: AnnuityPolicy[];
}

// --- Assets ----------------------------------------------------------------

export interface AssetItem {
  naam?: string | null;
  bedrag?: Money | null;
}

export interface Assets {
  savings: AssetItem[];
  investments: AssetItem[];
  otherAssets: AssetItem[];
}

// --- Objective & property --------------------------------------------------

export type ObjectiveType =
  | "aankoop-bestaande-bouw"
  | "aankoop-nieuwbouw"
  | "aankoop-eigen-beheer"
  | "hypotheek-verhogen"
  | "hypotheek-oversluiten"
  | "partner-uitkopen"
  | string;

export interface Objective {
  type?: ObjectiveType | null;
  purchasePrice?: Money | null;
  targetDescription?: string | null;
  buyoutCurrentShareApplicant?: number | null;
  buyoutCurrentSharePartner?: number | null;
  buyoutNewShareApplicant?: number | null;
  buyoutNewSharePartner?: number | null;
}

export interface Property {
  address?: Address | null;
  propertyType?: string | null;
  marketValue?: Money | null;
  marketValueAfterRenovation?: Money | null;
  constructionYear?: number | null;
  energyLabel?: string | null;
  energySavingBudget?: Money | null;
  groundLeaseAnnual?: Money | null;
}

// --- Financing setup -------------------------------------------------------

export interface FinancingCosts {
  transferTaxAmount?: Money | null;
  transferTaxRate?: Percentage | null;
  valuationCost?: Money | null;
  adviceCost?: Money | null;
  notaryCost?: Money | null;
  brokerCost?: Money | null;
  penaltyInterest?: Money | null;
  otherCosts?: Money | null;
}

export interface FinancingEquity {
  savingsContribution?: Money | null;
  gift?: Money | null;
  starterLoan?: Money | null;
}

export interface FinancingNhg {
  selected?: boolean | null;
  feeAmount?: Money | null;
}

export interface FinancingSetup {
  costs: FinancingCosts;
  equity: FinancingEquity;
  nhg: FinancingNhg;
  wozValue?: Money | null;
  requiredMortgageAmount?: Money | null;
  totalCosts?: Money | null;
  totalEquity?: Money | null;
  totalInvestment?: Money | null;
}

// --- New mortgage ----------------------------------------------------------

export interface NewLoanPart {
  id?: string | null;
  aflosvorm?: RepaymentType | null;
  bedragBox1?: Money | null;
  bedragBox3?: Money | null;
  looptijdMaanden?: number | null;
  rentepercentage?: Percentage | null;
  rentevastePeriode?: string | null;
}

export interface NewMortgage {
  lender?: string | null;
  productLine?: string | null;
  passDate?: string | null;
  registrationAmount?: Money | null;
  loanParts: NewLoanPart[];
}

// --- Calculations ----------------------------------------------------------

export interface MaxMortgageScenario {
  maximaleHypotheekBox1?: Money | null;
  maximaleHypotheekBox3?: Money | null;
  beschikbareRuimte?: Money | null;
  toetsinkomen?: Money | null;
  toetsrente?: Percentage | null;
  woonquoteBox1?: Percentage | null;
  woonquoteBox3?: Percentage | null;
  gewogenWerkelijkeRente?: Percentage | null;
  energielabelBonus?: Money | null;
}

export interface MonthlyCostsCalculation {
  brutoMaandlast?: Money | null;
  renteaftrek?: Money | null;
  nettoMaandlast?: Money | null;
}

export interface TaxCalculation {
  ewf?: Money | null;
  hypotheekrenteaftrek?: Money | null;
  hillenCorrectie?: Money | null;
}

export interface Calculations {
  maxMortgageNow?: MaxMortgageScenario | null;
  maxMortgageRetirement?: MaxMortgageScenario | null;
  monthlyCosts?: MonthlyCostsCalculation | null;
  tax?: TaxCalculation | null;
}

// --- Fiscal history & advice profile ---------------------------------------

export interface FiscalHistory {
  hasPreviousOwnerOccupiedHome?: boolean | null;
  interestDeductionStartYear?: number | null;
  interestDeductionEndYear?: number | null;
  remainingInterestDeductionMonths?: number | null;
  hasEquityReserve?: boolean | null;
  equityReserveAmount?: Money | null;
  box3LoanAmount?: Money | null;
}

export interface AdviceProfile {
  customerPriority?: string | null;
  riskAppetite?: string | null;
  wantsStablePayments?: boolean | null;
  wantsFlexibility?: boolean | null;
  customerRejectedOrv?: boolean | null;
}

// --- Top-level input -------------------------------------------------------

export interface ReportBuilderInput {
  dossier: Dossier;
  applicants: Applicants;
  household: Household;
  currentSituation: CurrentSituation;
  income: Income;
  obligations: Obligations;
  protections: Protections;
  assets: Assets;
  objective: Objective;
  property: Property;
  financingSetup: FinancingSetup;
  newMortgage: NewMortgage;
  calculations: Calculations;
  fiscalHistory: FiscalHistory;
  adviceProfile: AdviceProfile;
}

// --- Viewmodel row types ---------------------------------------------------

export interface LabelValueRow {
  label: string;
  value: string | number | null;
}

export interface MoneyRow {
  label: string;
  amount: Money;
}

export interface LoanPartRow {
  leningdeel: string;
  bedrag: Money;
  aflosvorm: string;
  rentepercentage: Percentage | null;
  rentevastePeriode: string | null;
  looptijdMaanden: number | null;
  fiscaleBox: "box1" | "box3" | "gemengd";
}

export interface NarrativeBlock {
  key: string;
  text: string;
}

// --- Report viewmodel sections ---------------------------------------------

export interface ReportMetaSection {
  title: string;
  date: string;
  dossierNumber: string;
  advisor: string;
  customerName: string;
  propertyAddress: string;
}

export interface SummarySection {
  objectiveLabel: string;
  mortgageAmount: Money;
  lender: string;
  productLine: string;
  grossMonthly: Money;
  netMonthly: Money;
  equityContribution: Money;
  narrativeBlocks: NarrativeBlock[];
}

export interface ClientProfileSection {
  householdText: string;
  applicants: LabelValueRow[];
  incomeRows: MoneyRow[];
  assetRows: MoneyRow[];
  obligationRows: MoneyRow[];
}

export interface PropertySection {
  address: string;
  propertyType: string;
  marketValue: Money;
  marketValueAfterRenovation: Money | null;
  constructionYear: number | null;
  energyLabel: string;
  groundLeaseAnnual: Money | null;
  ltvPercentage: number | null;
}

export interface AffordabilitySection {
  testIncome: Money;
  maxMortgageNow: Money;
  maxMortgageRetirement: Money | null;
  advisedMortgage: Money;
  grossMonthly: Money;
  taxBenefitMonthly: Money;
  netMonthly: Money;
  narrativeBlocks: NarrativeBlock[];
}

export interface FinancingSection {
  costRows: MoneyRow[];
  equityRows: MoneyRow[];
  totalInvestment: Money;
  totalEquity: Money;
  requiredMortgage: Money;
}

export interface LoanPartsSection {
  lender: string;
  productLine: string;
  rows: LoanPartRow[];
  narrativeBlocks: NarrativeBlock[];
}

export interface TaxSection {
  qualificationText: string;
  interestDeductionEndYear: number | null;
  hasEquityReserve: boolean;
  equityReserveAmount: Money | null;
  hasBox3Part: boolean;
  narrativeBlocks: NarrativeBlock[];
}

export interface RiskSubSection {
  narrativeBlocks: NarrativeBlock[];
}

export interface DeathRiskSection extends RiskSubSection {
  hasOrv: boolean;
  coverageAmount: Money;
}

export interface DisabilityRiskSection extends RiskSubSection {
  hasAov: boolean;
}

export interface UnemploymentRiskSection extends RiskSubSection {
  liquidBuffer: Money;
}

export interface RisksSection {
  death: DeathRiskSection;
  disability: DisabilityRiskSection;
  unemployment: UnemploymentRiskSection;
}

export interface RetirementSection {
  show: boolean;
  expectedIncome: Money;
  narrativeBlocks: NarrativeBlock[];
}

export interface AttentionPointsSection {
  items: string[];
}

export interface DisclaimerSection {
  narrativeBlocks: NarrativeBlock[];
}

// --- Visibility flags (which sections/subsections to render) ---------------

export interface ReportVisibility {
  showPartner: boolean;
  showRetirement: boolean;
  showBox3: boolean;
  showEquityReserve: boolean;
  showOrvAdvice: boolean;
  showNhg: boolean;
  showGroundLease: boolean;
  showRenovationValue: boolean;
  showMaxMortgageRetirement: boolean;
}

export interface ReportViewModel {
  meta: ReportMetaSection;
  summary: SummarySection;
  clientProfile: ClientProfileSection;
  property: PropertySection;
  affordability: AffordabilitySection;
  financing: FinancingSection;
  loanParts: LoanPartsSection;
  tax: TaxSection;
  risks: RisksSection;
  retirement: RetirementSection;
  attentionPoints: AttentionPointsSection;
  disclaimer: DisclaimerSection;
  visibility: ReportVisibility;
}

// --- Computed fields -------------------------------------------------------

export interface ComputedFields {
  applicantFullName: string;
  partnerFullName: string;
  customerDisplayName: string;
  propertyAddressLine: string;
  householdCompositionText: string;

  grossIncomeApplicantTotal: Money;
  grossIncomePartnerTotal: Money;
  grossIncomeHouseholdTotal: Money;
  pensionIncomeApplicantTotal: Money;
  pensionIncomePartnerTotal: Money;

  totalSavings: Money;
  totalInvestments: Money;
  totalOtherAssets: Money;
  totalAssets: Money;

  totalBkrMonthly: Money;
  totalNonBkrMonthly: Money;
  totalPrivateLeaseMonthly: Money;
  totalStudyLoanMonthly: Money;
  totalAlimonyPaidMonthly: Money;
  totalObligationsMonthly: Money;

  effectiveMarketValue: Money;
  totalMortgageAmount: Money;
  ltvPercentage: number | null;

  totalInvestment: Money;
  totalOwnFunds: Money;
  requiredMortgageAmount: Money;

  grossMonthlyPaymentTotal: Money;
  taxBenefitMonthly: Money;
  netMonthlyPaymentTotal: Money;

  hasAnnuityPart: boolean;
  hasLinearPart: boolean;
  hasInterestOnlyPart: boolean;
  hasBridgeLoanPart: boolean;
  hasSavingsMortgagePart: boolean;
  hasBox1Part: boolean;
  hasBox3Part: boolean;
  totalBox1Loan: Money;
  totalBox3Loan: Money;

  qualifiesForInterestDeduction: boolean;
  remainingInterestDeductionYears: number | null;
  interestDeductionEndYear: number | null;
  hasEquityReserve: boolean;
  equityReserveAmount: Money | null;

  hasOrv: boolean;
  totalOrvCoverage: Money;
  hasAov: boolean;
  liquidBuffer: Money;
  bufferMonthsEstimate: number | null;

  retirementScenarioRequired: boolean;
  objectiveLabel: string;
}
