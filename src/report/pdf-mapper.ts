// ============================================================================
// Adviesrapport — PDF rendering mapper
//
// Transforms a ReportViewModel into a flat, framework-independent structure
// ready for any PDF template engine (WeasyPrint/Jinja2, Puppeteer, etc.).
//
// All Money and Percentage values are formatted as display strings here.
// ============================================================================

import type {
  LoanPartRow,
  Money,
  MoneyRow,
  NarrativeBlock,
  Percentage,
  ReportViewModel,
} from "./types";

// --- Formatters (exported for unit testing) --------------------------------

/**
 * Format a number as Dutch currency.
 * @example formatMoney(350000)    → "€ 350.000"
 * @example formatMoney(1267.48)   → "€ 1.267"
 * @example formatMoney(1267.48,2) → "€ 1.267,48"
 */
export const formatMoney = (
  amount: Money | null | undefined,
  decimals = 0,
): string => {
  if (amount == null || isNaN(amount)) return "\u20ac 0";
  const abs = Math.abs(amount);
  const fixed = abs.toFixed(decimals);
  const [whole, frac] = fixed.split(".");
  const thousands = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const formatted = frac ? `${thousands},${frac}` : thousands;
  return amount < 0 ? `\u20ac -${formatted}` : `\u20ac ${formatted}`;
};

/**
 * Format a percentage with Dutch comma notation.
 * @example formatPercentage(4.5)    → "4,50%"
 * @example formatPercentage(36.97)  → "36,97%"
 * @example formatPercentage(0.263, 1) → "0,3%"
 */
export const formatPercentage = (
  pct: Percentage | null | undefined,
  decimals = 2,
): string => {
  if (pct == null || isNaN(pct)) return "0,00%";
  return pct.toFixed(decimals).replace(".", ",") + "%";
};

/**
 * Format months as a readable Dutch term description.
 * @example formatTermMonths(360) → "30 jaar"
 * @example formatTermMonths(366) → "30 jaar en 6 maanden"
 * @example formatTermMonths(6)   → "6 maanden"
 */
export const formatTermMonths = (
  months: number | null | undefined,
): string => {
  if (!months || months <= 0) return "";
  const years = Math.floor(months / 12);
  const rem = months % 12;
  if (rem === 0) return `${years} jaar`;
  if (years === 0) return `${rem} maanden`;
  return `${years} jaar en ${rem} maanden`;
};

// --- PDF output types ------------------------------------------------------

export interface PdfRow {
  label: string;
  value: string;
  bold?: boolean;
}

export interface PdfTable {
  headers: string[];
  rows: string[][];
}

export interface PdfHighlight {
  label: string;
  value: string;
  note?: string;
}

export interface PdfSection {
  id: string;
  title: string;
  visible: boolean;
  narratives: string[];
  rows?: PdfRow[];
  tables?: PdfTable[];
  highlights?: PdfHighlight[];
}

export interface PdfReportMeta {
  title: string;
  date: string;
  dossierNumber: string;
  advisor: string;
  customerName: string;
  propertyAddress: string;
}

export interface PdfReport {
  meta: PdfReportMeta;
  sections: PdfSection[];
}

// --- Internal helpers ------------------------------------------------------

const narrativesToStrings = (blocks: NarrativeBlock[]): string[] =>
  blocks.map((b) => b.text);

const moneyRowsToPdfRows = (
  rows: MoneyRow[],
  opts?: { boldLast?: boolean },
): PdfRow[] =>
  rows.map((r, i) => ({
    label: r.label,
    value: formatMoney(r.amount),
    bold: opts?.boldLast && i === rows.length - 1,
  }));

const loanPartsToTable = (rows: LoanPartRow[]): PdfTable => ({
  headers: ["Leningdeel", "Bedrag", "Aflosvorm", "Rente", "RVP", "Looptijd", "Box"],
  rows: rows.map((r) => [
    r.leningdeel,
    formatMoney(r.bedrag),
    r.aflosvorm,
    r.rentepercentage != null ? formatPercentage(r.rentepercentage) : "",
    r.rentevastePeriode ?? "",
    r.looptijdMaanden != null ? formatTermMonths(r.looptijdMaanden) : "",
    r.fiscaleBox,
  ]),
});

// --- Section mappers -------------------------------------------------------

const mapSummary = (vm: ReportViewModel): PdfSection => ({
  id: "summary",
  title: "Samenvatting advies",
  visible: true,
  narratives: narrativesToStrings(vm.summary.narrativeBlocks),
  highlights: [
    {
      label: "Hypotheekbedrag",
      value: formatMoney(vm.summary.mortgageAmount),
      note: `${vm.summary.lender}${vm.summary.productLine ? ` \u2014 ${vm.summary.productLine}` : ""}`,
    },
    {
      label: "Netto maandlast",
      value: formatMoney(vm.summary.netMonthly),
    },
  ],
  rows: [
    { label: "Bruto maandlast", value: formatMoney(vm.summary.grossMonthly) },
    { label: "Netto maandlast", value: formatMoney(vm.summary.netMonthly), bold: true },
    { label: "Eigen inbreng", value: formatMoney(vm.summary.equityContribution) },
  ],
});

const mapClientProfile = (vm: ReportViewModel): PdfSection => ({
  id: "client-profile",
  title: "Klantprofiel",
  visible: true,
  narratives: [vm.clientProfile.householdText],
  rows: [
    ...vm.clientProfile.applicants.map((r) => ({
      label: r.label,
      value: String(r.value ?? ""),
    })),
    { label: "", value: "", bold: false }, // spacer
    ...moneyRowsToPdfRows(vm.clientProfile.incomeRows, { boldLast: true }),
    { label: "", value: "", bold: false },
    ...moneyRowsToPdfRows(vm.clientProfile.assetRows, { boldLast: true }),
    ...(vm.clientProfile.obligationRows.length > 0
      ? [
          { label: "", value: "", bold: false as boolean },
          ...moneyRowsToPdfRows(vm.clientProfile.obligationRows, { boldLast: true }),
        ]
      : []),
  ],
});

const mapProperty = (vm: ReportViewModel): PdfSection => {
  const rows: PdfRow[] = [
    { label: "Adres", value: vm.property.address },
    { label: "Woningtype", value: vm.property.propertyType },
    { label: "Marktwaarde", value: formatMoney(vm.property.marketValue) },
  ];

  if (vm.visibility.showRenovationValue && vm.property.marketValueAfterRenovation) {
    rows.push({
      label: "Marktwaarde na verbouwing",
      value: formatMoney(vm.property.marketValueAfterRenovation),
    });
  }

  if (vm.property.constructionYear) {
    rows.push({ label: "Bouwjaar", value: String(vm.property.constructionYear) });
  }

  if (vm.property.energyLabel) {
    rows.push({ label: "Energielabel", value: vm.property.energyLabel });
  }

  if (vm.visibility.showGroundLease && vm.property.groundLeaseAnnual) {
    rows.push({
      label: "Erfpachtcanon (per jaar)",
      value: formatMoney(vm.property.groundLeaseAnnual),
    });
  }

  if (vm.property.ltvPercentage != null) {
    rows.push({
      label: "Loan-to-Value",
      value: formatPercentage(vm.property.ltvPercentage, 1),
    });
  }

  return {
    id: "property",
    title: "Onderpand",
    visible: true,
    narratives: [],
    rows,
  };
};

const mapAffordability = (vm: ReportViewModel): PdfSection => {
  const rows: PdfRow[] = [
    { label: "Toetsinkomen", value: formatMoney(vm.affordability.testIncome) },
    {
      label: "Maximale hypotheek (huidige situatie)",
      value: formatMoney(vm.affordability.maxMortgageNow),
    },
  ];

  if (vm.visibility.showMaxMortgageRetirement && vm.affordability.maxMortgageRetirement != null) {
    rows.push({
      label: "Maximale hypotheek (na pensionering)",
      value: formatMoney(vm.affordability.maxMortgageRetirement),
    });
  }

  rows.push(
    { label: "Geadviseerd hypotheekbedrag", value: formatMoney(vm.affordability.advisedMortgage), bold: true },
    { label: "Bruto maandlast", value: formatMoney(vm.affordability.grossMonthly) },
    { label: "Fiscaal voordeel", value: formatMoney(vm.affordability.taxBenefitMonthly) },
    { label: "Netto maandlast", value: formatMoney(vm.affordability.netMonthly), bold: true },
  );

  return {
    id: "affordability",
    title: "Betaalbaarheid",
    visible: true,
    narratives: narrativesToStrings(vm.affordability.narrativeBlocks),
    rows,
  };
};

const mapFinancing = (vm: ReportViewModel): PdfSection => ({
  id: "financing",
  title: "Financieringsopzet",
  visible: true,
  narratives: [],
  rows: [
    ...moneyRowsToPdfRows(vm.financing.costRows),
    { label: "Totale investering", value: formatMoney(vm.financing.totalInvestment), bold: true },
    { label: "", value: "" },
    ...moneyRowsToPdfRows(vm.financing.equityRows),
    { label: "Totaal eigen middelen", value: formatMoney(vm.financing.totalEquity), bold: true },
    { label: "", value: "" },
    { label: "Benodigd hypotheekbedrag", value: formatMoney(vm.financing.requiredMortgage), bold: true },
  ],
});

const mapLoanParts = (vm: ReportViewModel): PdfSection => ({
  id: "loan-parts",
  title: "Hypotheekonderdelen",
  visible: true,
  narratives: narrativesToStrings(vm.loanParts.narrativeBlocks),
  rows: [
    { label: "Geldverstrekker", value: vm.loanParts.lender },
    { label: "Productlijn", value: vm.loanParts.productLine },
  ],
  tables: [loanPartsToTable(vm.loanParts.rows)],
});

const mapTax = (vm: ReportViewModel): PdfSection => {
  const rows: PdfRow[] = [
    { label: "Fiscale kwalificatie", value: vm.tax.qualificationText },
  ];

  if (vm.tax.interestDeductionEndYear) {
    rows.push({
      label: "Renteaftrek tot en met",
      value: String(vm.tax.interestDeductionEndYear),
    });
  }

  if (vm.visibility.showEquityReserve && vm.tax.equityReserveAmount) {
    rows.push({
      label: "Eigenwoningreserve",
      value: formatMoney(vm.tax.equityReserveAmount),
    });
  }

  return {
    id: "tax",
    title: "Fiscale aspecten",
    visible: true,
    narratives: narrativesToStrings(vm.tax.narrativeBlocks),
    rows,
  };
};

const mapDeathRisk = (vm: ReportViewModel): PdfSection => {
  const rows: PdfRow[] = [];
  if (vm.risks.death.hasOrv) {
    rows.push({
      label: "ORV-dekking",
      value: formatMoney(vm.risks.death.coverageAmount),
    });
  }

  return {
    id: "risk-death",
    title: "Risico bij overlijden",
    visible: true,
    narratives: narrativesToStrings(vm.risks.death.narrativeBlocks),
    rows: rows.length > 0 ? rows : undefined,
  };
};

const mapDisabilityRisk = (vm: ReportViewModel): PdfSection => ({
  id: "risk-disability",
  title: "Risico bij arbeidsongeschiktheid",
  visible: true,
  narratives: narrativesToStrings(vm.risks.disability.narrativeBlocks),
  rows: vm.risks.disability.hasAov
    ? [{ label: "AOV aanwezig", value: "Ja" }]
    : undefined,
});

const mapUnemploymentRisk = (vm: ReportViewModel): PdfSection => ({
  id: "risk-unemployment",
  title: "Risico bij werkloosheid",
  visible: true,
  narratives: narrativesToStrings(vm.risks.unemployment.narrativeBlocks),
  rows: [
    { label: "Beschikbare buffer (spaargeld)", value: formatMoney(vm.risks.unemployment.liquidBuffer) },
  ],
});

const mapRetirement = (vm: ReportViewModel): PdfSection => ({
  id: "retirement",
  title: "Pensionering",
  visible: vm.visibility.showRetirement,
  narratives: narrativesToStrings(vm.retirement.narrativeBlocks),
  rows: vm.retirement.expectedIncome > 0
    ? [{ label: "Verwacht pensioeninkomen (per jaar)", value: formatMoney(vm.retirement.expectedIncome) }]
    : undefined,
});

const mapAttentionPoints = (vm: ReportViewModel): PdfSection => ({
  id: "attention-points",
  title: "Aandachtspunten",
  visible: vm.attentionPoints.items.length > 0,
  narratives: vm.attentionPoints.items,
});

const mapDisclaimer = (vm: ReportViewModel): PdfSection => ({
  id: "disclaimer",
  title: "Disclaimer",
  visible: true,
  narratives: narrativesToStrings(vm.disclaimer.narrativeBlocks),
});

// --- Main entry point ------------------------------------------------------

/**
 * Map a ReportViewModel to a flat PDF-ready structure.
 *
 * All Money/Percentage values are formatted as display strings.
 * Sections have a `visible` flag — the PDF template can skip invisible sections.
 *
 * @example
 * const vm = buildReport(input);
 * const pdf = mapToPdf(vm);
 * // Pass pdf.sections to your template engine
 */
export const mapToPdf = (vm: ReportViewModel): PdfReport => ({
  meta: {
    title: vm.meta.title,
    date: vm.meta.date,
    dossierNumber: vm.meta.dossierNumber,
    advisor: vm.meta.advisor,
    customerName: vm.meta.customerName,
    propertyAddress: vm.meta.propertyAddress,
  },
  sections: [
    mapSummary(vm),
    mapClientProfile(vm),
    mapProperty(vm),
    mapAffordability(vm),
    mapFinancing(vm),
    mapLoanParts(vm),
    mapTax(vm),
    mapDeathRisk(vm),
    mapDisabilityRisk(vm),
    mapUnemploymentRisk(vm),
    mapRetirement(vm),
    mapAttentionPoints(vm),
    mapDisclaimer(vm),
  ],
});
