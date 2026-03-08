// ============================================================================
// Adviesrapport — Narrative text blocks (conditional, data-driven)
// ============================================================================

import type { ComputedFields, NarrativeBlock, ReportBuilderInput } from "./types";

const block = (key: string, text: string): NarrativeBlock => ({ key, text });

// --- Summary ---------------------------------------------------------------

export const buildSummaryNarratives = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): NarrativeBlock[] => {
  const blocks: NarrativeBlock[] = [];

  blocks.push(
    block(
      "summary-intro",
      `U wilt een hypotheek afsluiten voor ${computed.objectiveLabel.toLowerCase()}` +
        `${computed.propertyAddressLine ? ` aan ${computed.propertyAddressLine}` : ""}.`,
    ),
  );

  if (computed.grossMonthlyPaymentTotal > 0 || computed.netMonthlyPaymentTotal > 0) {
    blocks.push(
      block(
        "summary-monthly-costs",
        "Op basis van uw financiële situatie, uw wensen en de geldende leennormen " +
          "hebben wij beoordeeld dat de geadviseerde financiering passend is binnen uw situatie.",
      ),
    );
  }

  const priority = input.adviceProfile.customerPriority?.trim();
  if (priority) {
    blocks.push(
      block(
        "summary-priority",
        `Bij het advies hebben wij nadrukkelijk rekening gehouden met uw prioriteit: ${priority.toLowerCase()}.`,
      ),
    );
  }

  if (input.financingSetup.nhg.selected) {
    blocks.push(
      block(
        "summary-nhg",
        "De hypotheek wordt aangevraagd met Nationale Hypotheek Garantie.",
      ),
    );
  }

  return blocks;
};

// --- Affordability ---------------------------------------------------------

export const buildAffordabilityNarratives = (
  _input: ReportBuilderInput,
  _computed: ComputedFields,
): NarrativeBlock[] => [
  block(
    "affordability-1",
    "De maximale hypotheek is beoordeeld op basis van de geldende leennormen, " +
      "het toetsinkomen en uw financiële verplichtingen.",
  ),
  block(
    "affordability-2",
    "De geadviseerde maandlasten zijn getoetst aan uw situatie en passen " +
      "binnen de gehanteerde normen.",
  ),
];

// --- Loan parts ------------------------------------------------------------

export const buildLoanPartNarratives = (
  _input: ReportBuilderInput,
  computed: ComputedFields,
): NarrativeBlock[] => {
  const blocks: NarrativeBlock[] = [];

  if (computed.hasAnnuityPart) {
    blocks.push(
      block(
        "loan-annuity",
        "Een annuïtaire hypotheek kent een maandlast die bestaat uit rente en aflossing. " +
          "Binnen de looptijd wordt de lening volledig afgelost.",
      ),
    );
  }

  if (computed.hasLinearPart) {
    blocks.push(
      block(
        "loan-linear",
        "Bij een lineaire hypotheek lost u iedere maand een vast bedrag af. " +
          "Daardoor daalt de schuld sneller en nemen de maandlasten in de tijd af.",
      ),
    );
  }

  if (computed.hasInterestOnlyPart) {
    blocks.push(
      block(
        "loan-interest-only",
        "Bij een aflossingsvrij leningdeel betaalt u gedurende de looptijd " +
          "in beginsel alleen rente en blijft de hoofdsom openstaan.",
      ),
    );
  }

  if (computed.hasBox3Part) {
    blocks.push(
      block(
        "loan-box3",
        "Voor zover sprake is van een leningdeel in box 3 is de rente " +
          "daarop fiscaal niet aftrekbaar als eigenwoningrente.",
      ),
    );
  }

  return blocks;
};

// --- Tax -------------------------------------------------------------------

export const buildTaxNarratives = (
  _input: ReportBuilderInput,
  computed: ComputedFields,
): NarrativeBlock[] => {
  const blocks: NarrativeBlock[] = [];

  if (computed.qualifiesForInterestDeduction) {
    blocks.push(
      block(
        "tax-box1",
        "De leningdelen die kwalificeren als eigenwoningschuld vallen in box 1. " +
          "De betaalde hypotheekrente kan fiscaal aftrekbaar zijn, voor zover " +
          "aan de wettelijke voorwaarden wordt voldaan.",
      ),
    );
  }

  if (computed.interestDeductionEndYear) {
    blocks.push(
      block(
        "tax-duration",
        `Op basis van het bekende eigenwoningverleden loopt de renteaftrek ` +
          `tot en met ${computed.interestDeductionEndYear}.`,
      ),
    );
  }

  if (
    computed.hasEquityReserve &&
    computed.equityReserveAmount &&
    computed.equityReserveAmount > 0
  ) {
    blocks.push(
      block(
        "tax-equity-reserve",
        "Bij het advies is rekening gehouden met een bestaande eigenwoningreserve " +
          "en de mogelijke gevolgen van de bijleenregeling.",
      ),
    );
  }

  if (computed.hasBox3Part) {
    blocks.push(
      block(
        "tax-box3",
        "Voor zover een leningdeel niet kwalificeert als eigenwoningschuld, " +
          "valt dit fiscaal in box 3.",
      ),
    );
  }

  return blocks;
};

// --- Risks: death ----------------------------------------------------------

export const buildDeathRiskNarratives = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): NarrativeBlock[] => {
  // ORV already in place
  if (computed.hasOrv) {
    return [
      block(
        "death-orv-present",
        "Bij overlijden kan het huishoudinkomen dalen. U beschikt over een " +
          "overlijdensrisicoverzekering die bedoeld is om dit risico gedeeltelijk op te vangen.",
      ),
    ];
  }

  // Partner present, no ORV
  if (input.applicants.hasPartner) {
    const blocks: NarrativeBlock[] = [
      block(
        "death-orv-advice",
        "Bij overlijden van één van de aanvragers kan het inkomen van het huishouden dalen. " +
          "Een overlijdensrisicoverzekering kan dit risico beperken doordat bij overlijden " +
          "een verzekerd bedrag beschikbaar komt.",
      ),
    ];

    if (input.adviceProfile.customerRejectedOrv) {
      blocks.push(
        block(
          "death-orv-rejected",
          "U heeft ervoor gekozen om op dit moment geen overlijdensrisicoverzekering af te sluiten.",
        ),
      );
    } else {
      blocks.push(
        block(
          "death-orv-open",
          "Het afsluiten van een overlijdensrisicoverzekering verdient aandacht " +
            "binnen uw financiële planning.",
        ),
      );
    }

    return blocks;
  }

  // Single applicant
  return [
    block(
      "death-single",
      "Bij overlijden ontstaat geen financieel risico voor een partner, " +
        "maar het blijft van belang dat eventuele nabestaanden of erfgenamen " +
        "zich bewust zijn van de gevolgen voor de woningfinanciering.",
    ),
  ];
};

// --- Risks: disability (awareness only) ------------------------------------

export const buildDisabilityRiskNarratives = (): NarrativeBlock[] => [
  block(
    "disability-1",
    "Wanneer u arbeidsongeschikt raakt, kan uw inkomen dalen. " +
      "Hierdoor kan het lastiger worden om de hypotheeklasten te blijven betalen.",
  ),
  block(
    "disability-2",
    "In dit rapport is geen afzonderlijke productoplossing voor " +
      "arbeidsongeschiktheid opgenomen. Het doel van dit onderdeel is " +
      "bewustwording van dit risico.",
  ),
];

// --- Risks: unemployment (awareness only) ----------------------------------

export const buildUnemploymentRiskNarratives = (): NarrativeBlock[] => [
  block(
    "unemployment-1",
    "Bij werkloosheid kan uw inkomen tijdelijk lager zijn. " +
      "Hierdoor kunnen de maandlasten moeilijker betaalbaar worden.",
  ),
  block(
    "unemployment-2",
    "Het is daarom belangrijk om voldoende financiële reserves aan te houden " +
      "om een periode van inkomensdaling op te kunnen vangen.",
  ),
];

// --- Retirement (inventory only) -------------------------------------------

export const buildRetirementNarratives = (
  _input: ReportBuilderInput,
  computed: ComputedFields,
): NarrativeBlock[] => {
  const blocks: NarrativeBlock[] = [
    block(
      "retirement-1",
      "Wij hebben gekeken naar uw verwachte inkomenssituatie na pensionering " +
        "op basis van de bij ons bekende pensioeninformatie.",
    ),
  ];

  if (computed.retirementScenarioRequired) {
    blocks.push(
      block(
        "retirement-2",
        "Op basis van deze gegevens is beoordeeld of de hypotheeklasten " +
          "ook na pensionering passend blijven.",
      ),
    );
  }

  return blocks;
};

// --- Attention points ------------------------------------------------------

export const buildAttentionPoints = (
  input: ReportBuilderInput,
  computed: ComputedFields,
): string[] => {
  const items: string[] = [];

  if (input.newMortgage.loanParts.some((p) => !!p.rentevastePeriode)) {
    items.push(
      "Na afloop van de rentevaste periode kan de rente wijzigen, " +
        "waardoor de maandlasten kunnen stijgen of dalen.",
    );
  }

  if (computed.hasBox3Part) {
    items.push(
      "Voor zover sprake is van een leningdeel in box 3, is de rente daarop " +
        "niet aftrekbaar als eigenwoningrente.",
    );
  }

  if (input.adviceProfile.customerRejectedOrv) {
    items.push(
      "U heeft ervoor gekozen om geen overlijdensrisicoverzekering af te sluiten. " +
        "Dit betekent dat het financiële risico bij overlijden niet afzonderlijk is afgedekt.",
    );
  }

  items.push(
    "Veranderingen in uw persoonlijke of financiële situatie kunnen invloed " +
      "hebben op de betaalbaarheid van de hypotheek.",
  );

  return items;
};

// --- Disclaimer ------------------------------------------------------------

export const buildDisclaimerNarratives = (): NarrativeBlock[] => [
  block(
    "disclaimer-1",
    "Dit adviesrapport is opgesteld op basis van de door u verstrekte informatie. " +
      "Wij gaan ervan uit dat deze gegevens juist en volledig zijn.",
  ),
  block(
    "disclaimer-2",
    "Het advies is een momentopname en gebaseerd op de huidige wet- en regelgeving " +
      "en de op het moment van opstellen bekende uitgangspunten.",
  ),
  block(
    "disclaimer-3",
    "De definitieve acceptatie van de hypotheek is afhankelijk van de beoordeling " +
      "door de geldverstrekker.",
  ),
];
