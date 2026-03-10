// ============================================================================
// Adviesrapport — Narrative text blocks (conditional, data-driven)
// ============================================================================

import type {
  ComputedFields,
  NarrativeBlock,
  RelationshipTextBlock,
  ReportBuilderInput,
  StandardScenarioTextBlock,
} from "./types";

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

// --- Centralized scenario text definitions ---------------------------------

export const DEATH_TEXT: StandardScenarioTextBlock = {
  intro:
    "Wij hebben berekend wat de gevolgen zijn voor de betaalbaarheid van de hypotheek " +
    "wanneer een van u overlijdt. Daarbij is gekeken of de achterblijvende partner de " +
    "woonlasten zelfstandig kan blijven dragen.",
  outcome: {
    affordable:
      "Wanneer een van u overlijdt blijft de hypotheek op basis van deze berekening " +
      "betaalbaar voor de achterblijvende partner.",
    resolved:
      "Wanneer een van u overlijdt ontstaat er op basis van de berekening een financieel " +
      "tekort. De bestaande voorzieningen zijn echter voldoende om dit tekort op te vangen.",
    attention:
      "Wanneer een van u overlijdt ontstaat er op basis van deze berekening een beperkt " +
      "financieel tekort voor de achterblijvende partner. Dit vraagt aandacht.",
    shortfall:
      "Wanneer een van u overlijdt ontstaat er op basis van deze berekening een financieel " +
      "tekort voor de achterblijvende partner dat niet volledig kan worden opgevangen met " +
      "de huidige voorzieningen.",
  },
  advice: {
    no_action:
      "Op basis van deze berekening achten wij aanvullende maatregelen op dit moment niet noodzakelijk.",
    awareness_only:
      "U heeft aangegeven dit risico te willen accepteren. Het is belangrijk dat u zich " +
      "bewust bent van de mogelijke financiële gevolgen.",
    consider_solution:
      "Om dit risico te beperken kan een overlijdensrisicoverzekering passend zijn.",
    advise_solution:
      "Wij adviseren om maatregelen te treffen om dit risico te beperken, bijvoorbeeld door " +
      "een overlijdensrisicoverzekering af te sluiten of te verhogen.",
  },
  nuance: {
    existing_orv:
      "Bij deze berekening is rekening gehouden met de bestaande overlijdensrisicoverzekering(en).",
    existing_life_insurance:
      "Bij deze berekening is rekening gehouden met aanwezige levensverzekeringen.",
    savings_used:
      "Bij deze berekening is rekening gehouden met een deel van het beschikbare spaargeld.",
    employer_provisions_unknown:
      "Mogelijke voorzieningen via een werkgever, zoals aanvullende verzekeringen of " +
      "regelingen bij overlijden, zijn niet in deze berekening meegenomen omdat deze niet " +
      "altijd volledig bij ons bekend zijn.",
  },
  disclaimer:
    "De berekening is gebaseerd op de gegevens die bij ons bekend zijn op het moment van advies.",
};

export const RETIREMENT_TEXT: StandardScenarioTextBlock = {
  intro:
    "Wij hebben berekend hoe de betaalbaarheid van de hypotheek zich ontwikkelt wanneer u " +
    "met pensioen gaat. Daarbij is gekeken naar het verwachte inkomen na pensionering en de " +
    "maximale hypotheek die daarbij past.",
  outcome: {
    affordable:
      "Op basis van deze berekening blijft de geadviseerde hypotheek ook na pensionering " +
      "passend bij het verwachte inkomen.",
    resolved:
      "Na pensionering ontstaat er op basis van de berekening een verschil tussen de " +
      "geadviseerde hypotheek en de maximale hypotheek die past bij het inkomen op dat moment. " +
      "De bestaande voorzieningen zijn echter voldoende om dit verschil op te vangen.",
    attention:
      "Na pensionering ontstaat er op basis van deze berekening een beperkt verschil tussen " +
      "de geadviseerde hypotheek en de maximale hypotheek die past bij het verwachte inkomen. " +
      "Dit vraagt aandacht.",
    shortfall:
      "Na pensionering ontstaat er op basis van deze berekening een verschil tussen de " +
      "geadviseerde hypotheek en de maximale hypotheek die past bij het verwachte inkomen dat " +
      "niet volledig kan worden opgevangen met de huidige voorzieningen.",
  },
  advice: {
    no_action:
      "Op basis van deze berekening achten wij aanvullende maatregelen op dit moment niet noodzakelijk.",
    awareness_only:
      "U heeft aangegeven dit risico te willen accepteren. Het is belangrijk dat u zich " +
      "bewust bent van de mogelijke financiële gevolgen.",
    consider_solution:
      "Om dit risico te beperken kan het passend zijn om aanvullende maatregelen te treffen, " +
      "bijvoorbeeld door extra af te lossen op de hypotheek.",
    advise_extra_repayment:
      "Wij adviseren om maatregelen te treffen om dit risico te beperken, bijvoorbeeld door " +
      "extra af te lossen op de hypotheek voor pensionering.",
  },
  nuance: {
    couple_two_aow:
      "Bij deze berekening is rekening gehouden met de verschillende momenten waarop u beiden " +
      "de AOW-leeftijd bereikt.",
    income_decrease:
      "Na pensionering daalt het huishoudinkomen ten opzichte van de huidige situatie.",
    later_shortfall:
      "Wanneer ook de partner met pensioen gaat verandert de inkomenssituatie waardoor het " +
      "tekort kan toenemen.",
    income_improves:
      "Wanneer ook de partner de AOW-leeftijd bereikt verandert de inkomenssituatie waardoor " +
      "de betaalbaarheid kan verbeteren.",
    annuity_income_used:
      "Bij deze berekening is rekening gehouden met inkomen uit lijfrenteverzekeringen.",
  },
  disclaimer:
    "De berekening is gebaseerd op de pensioeninformatie en fiscale regels zoals die op dit " +
    "moment bekend zijn.",
};

export const DISABILITY_TEXT: StandardScenarioTextBlock = {
  intro:
    "Wij hebben berekend wat de gevolgen zijn voor de betaalbaarheid van de hypotheek " +
    "wanneer het inkomen daalt door arbeidsongeschiktheid.",
  outcome: {
    affordable:
      "Op basis van deze berekening blijven de woonlasten ook bij arbeidsongeschiktheid betaalbaar.",
    resolved:
      "Bij arbeidsongeschiktheid ontstaat er op basis van de berekening een financieel tekort. " +
      "De bestaande voorzieningen zijn echter voldoende om dit tekort op te vangen.",
    attention:
      "Bij arbeidsongeschiktheid ontstaat er op basis van deze berekening een beperkt " +
      "financieel tekort. Dit vraagt aandacht.",
    shortfall:
      "Bij arbeidsongeschiktheid ontstaat er op basis van deze berekening een financieel " +
      "tekort dat niet volledig kan worden opgevangen met de huidige voorzieningen.",
  },
  advice: {
    no_action:
      "Op basis van deze berekening achten wij aanvullende maatregelen op dit moment niet noodzakelijk.",
    awareness_only:
      "U heeft aangegeven dit risico te willen accepteren. Het is belangrijk dat u zich " +
      "bewust bent van de mogelijke financiële gevolgen.",
    consider_solution:
      "Om dit risico te beperken kan het passend zijn om aanvullende maatregelen te treffen.",
    refer_to_specialist:
      "Wij adviseren om te onderzoeken of aanvullende voorzieningen wenselijk zijn. Hiervoor " +
      "kan het passend zijn om een specialist te raadplegen.",
  },
  nuance: {
    aov_used:
      "Bij deze berekening is rekening gehouden met de bestaande arbeidsongeschiktheidsverzekering.",
    partner_income_used:
      "Bij deze berekening is rekening gehouden met het inkomen van de partner.",
  },
  disclaimer:
    "De berekening is gebaseerd op een indicatief scenario bij langdurige arbeidsongeschiktheid.",
};

export const UNEMPLOYMENT_TEXT: StandardScenarioTextBlock = {
  intro:
    "Wij hebben berekend wat de gevolgen zijn voor de betaalbaarheid van de hypotheek " +
    "wanneer het inkomen tijdelijk daalt door werkloosheid.",
  outcome: {
    affordable:
      "Op basis van deze berekening blijven de woonlasten ook bij werkloosheid betaalbaar.",
    resolved:
      "Bij werkloosheid ontstaat er op basis van de berekening een financieel tekort. " +
      "De bestaande voorzieningen zijn echter voldoende om dit tekort op te vangen.",
    attention:
      "Bij werkloosheid ontstaat er op basis van deze berekening een beperkt financieel " +
      "tekort. Dit vraagt aandacht.",
    shortfall:
      "Bij werkloosheid ontstaat er op basis van deze berekening een financieel tekort dat " +
      "niet volledig kan worden opgevangen met de huidige voorzieningen.",
  },
  advice: {
    no_action:
      "Op basis van deze berekening achten wij aanvullende maatregelen op dit moment niet noodzakelijk.",
    awareness_only:
      "U heeft aangegeven dit risico te willen accepteren. Het is belangrijk dat u zich " +
      "bewust bent van de mogelijke financiële gevolgen.",
    consider_solution:
      "Om dit risico te beperken kan het passend zijn om aanvullende maatregelen te treffen.",
    refer_to_specialist:
      "Wij adviseren om te onderzoeken of aanvullende voorzieningen wenselijk zijn. Hiervoor " +
      "kan het passend zijn om een specialist te raadplegen.",
  },
  nuance: {
    woonlastenverzekering_used:
      "Bij deze berekening is rekening gehouden met de bestaande woonlastenverzekering.",
    partner_income_used:
      "Bij deze berekening is rekening gehouden met het inkomen van de partner.",
  },
  disclaimer:
    "De berekening is gebaseerd op een indicatief scenario bij werkloosheid. De werkelijke " +
    "duur van werkloosheid kan afwijken.",
};

export const RELATIONSHIP_TEXT: RelationshipTextBlock = {
  intro:
    "Wij hebben indicatief berekend of de hypotheek door ieder van u afzonderlijk gedragen " +
    "kan worden wanneer de relatie eindigt.",
  overallOutcome: {
    affordable_for_both:
      "Op basis van deze berekening lijkt de hypotheek door ieder van u afzonderlijk betaalbaar.",
    affordable_for_one:
      "Op basis van deze berekening lijkt de hypotheek door een van u afzonderlijk betaalbaar.",
    affordable_for_none:
      "Op basis van deze berekening lijkt de hypotheek door geen van u afzonderlijk betaalbaar.",
  },
  personStatus: {
    affordable:
      "De hypotheek blijft op basis van deze berekening betaalbaar.",
    attention:
      "Op basis van deze berekening ontstaat een beperkt financieel tekort. Dit vraagt aandacht.",
    shortfall:
      "Op basis van deze berekening ontstaat een financieel tekort waardoor de hypotheek niet " +
      "zonder meer betaalbaar is.",
  },
  advice: {
    awareness_only:
      "Dit scenario is bedoeld om inzicht te geven in de mogelijke gevolgen voor de " +
      "betaalbaarheid van de hypotheek.",
  },
  disclaimer:
    "Deze berekening is indicatief. Er is geen rekening gehouden met mogelijke uitkoop, " +
    "alimentatie, verkoop van de woning of verdeling van vermogen.",
};

// --- Single-person death fallback (centralized texts assume couple) --------

export const DEATH_SINGLE_TEXT =
  "Bij overlijden ontstaat geen financieel risico voor een partner, " +
  "maar het blijft van belang dat eventuele nabestaanden of erfgenamen " +
  "zich bewust zijn van de gevolgen voor de woningfinanciering.";

// --- Advice text templates (Samenvatting — Advies en onderbouwing) ----------

export const ADVICE_RISK_LABELS: Record<string, string> = {
  affordable: "afgedekt",
  resolved: "afgedekt",
  attention: "aandachtspunt",
  shortfall: "tekort aanwezig",
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
