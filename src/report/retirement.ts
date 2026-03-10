// ============================================================================
// Adviesrapport — Retirement scenario analysis
//
// Pure functions that analyze retirement moments (AOW dates) and determine
// whether the advised mortgage remains affordable after pension.
//
// Shortfall threshold: ≤ 5% of advisedMortgage = "limited", > 5% = "material".
// ============================================================================

import type {
  Money,
  NarrativeBlock,
  RetirementAnalysisInput,
  RetirementMomentAnalysis,
  RetirementScenarioAnalysis,
  RetirementScenarioKind,
  RetirementShortfallSeverity,
} from "./types";

// --- Shortfall threshold (percentage of advised mortgage) ------------------

const SHORTFALL_THRESHOLD_PCT = 5;

// --- Helpers ---------------------------------------------------------------

const block = (key: string, text: string): NarrativeBlock => ({ key, text });

// --- Pure calculation functions --------------------------------------------

/**
 * Calculate shortfall between max mortgage at a retirement moment and advised mortgage.
 * Returns shortfall = 0 when maxMortgage >= advisedMortgage.
 */
export const calculateRetirementShortfall = (
  maxMortgage: Money,
  advisedMortgage: Money,
): { shortfall: Money; shortfallPercentage: number } => {
  const shortfall = Math.max(0, advisedMortgage - maxMortgage);
  const shortfallPercentage =
    advisedMortgage > 0 ? (shortfall / advisedMortgage) * 100 : 0;
  return { shortfall, shortfallPercentage };
};

/**
 * Classify shortfall severity based on percentage of advised mortgage.
 * - none: no shortfall
 * - limited: ≤ 5% (minor, mitigated by ongoing repayment)
 * - material: > 5% (requires attention in financial planning)
 */
export const getRetirementShortfallSeverity = (
  shortfallPercentage: number,
): RetirementShortfallSeverity => {
  if (shortfallPercentage <= 0) return "none";
  if (shortfallPercentage <= SHORTFALL_THRESHOLD_PCT) return "limited";
  return "material";
};

// --- Scenario classification -----------------------------------------------

const classifyScenario = (
  moments: RetirementMomentAnalysis[],
): RetirementScenarioKind => {
  if (moments.length <= 1) {
    const m = moments[0];
    if (!m || m.severity === "none") return "single-no-shortfall";
    if (m.severity === "limited") return "single-limited-shortfall";
    return "single-material-shortfall";
  }

  const [first, second] = moments;
  const firstHasShortfall = first.severity !== "none";
  const secondHasShortfall = second.severity !== "none";

  if (!firstHasShortfall && !secondHasShortfall) return "couple-none-both";
  if (!firstHasShortfall && secondHasShortfall) return "couple-none-then-shortfall";
  if (firstHasShortfall && !secondHasShortfall) return "couple-shortfall-then-none";

  // Both have shortfall — determine if increasing or stable
  // "Increasing" when second shortfall exceeds first by more than 10%
  if (first.shortfall > 0 && second.shortfall > first.shortfall * 1.1) {
    return "couple-shortfall-increasing";
  }
  return "couple-shortfall-stable";
};

// --- Main analysis function ------------------------------------------------

/**
 * Analyze retirement scenario: compute shortfall per moment and classify overall.
 *
 * Expects moments sorted chronologically (earliest AOW date first).
 * For a single applicant: 1 moment. For a couple: 2 moments.
 */
export const analyzeRetirementScenario = (
  input: RetirementAnalysisInput,
): RetirementScenarioAnalysis => {
  if (input.moments.length === 0) {
    return {
      kind: "single-no-shortfall",
      moments: [],
      advisedMortgage: input.advisedMortgage,
      hasShortfall: false,
      worstShortfall: 0,
      worstShortfallPercentage: 0,
    };
  }

  const moments: RetirementMomentAnalysis[] = input.moments.map((m) => {
    const { shortfall, shortfallPercentage } = calculateRetirementShortfall(
      m.maxMortgage,
      input.advisedMortgage,
    );
    return {
      label: m.label,
      year: m.year,
      personName: m.personName,
      maxMortgage: m.maxMortgage,
      restschuld: m.restschuld ?? null,
      shortfall,
      shortfallPercentage,
      severity: getRetirementShortfallSeverity(shortfallPercentage),
      incomeComponents: m.incomeComponents,
    };
  });

  const hasShortfall = moments.some((m) => m.severity !== "none");
  const worstMoment = moments.reduce(
    (worst, m) => (m.shortfall > worst.shortfall ? m : worst),
    moments[0],
  );

  return {
    kind: classifyScenario(moments),
    moments,
    advisedMortgage: input.advisedMortgage,
    hasShortfall,
    worstShortfall: worstMoment.shortfall,
    worstShortfallPercentage: worstMoment.shortfallPercentage,
  };
};

// --- Narrative builder -----------------------------------------------------

/**
 * Build Dutch narrative text blocks for the retirement section based on
 * the classified scenario.
 *
 * Always starts with a standard intro block, followed by a scenario-specific
 * assessment block.
 */
export const buildRetirementAnalysisNarratives = (
  analysis: RetirementScenarioAnalysis,
): NarrativeBlock[] => {
  const blocks: NarrativeBlock[] = [
    block(
      "retirement-intro",
      "Wij hebben gekeken naar uw verwachte inkomenssituatie na pensionering " +
        "op basis van de bij ons bekende pensioeninformatie.",
    ),
  ];

  switch (analysis.kind) {
    case "single-no-shortfall":
      blocks.push(
        block(
          "retirement-scenario",
          "Na pensionering blijft de maximale hypotheek boven het geadviseerde " +
            "hypotheekbedrag. De hypotheeklasten blijven daarmee naar verwachting " +
            "passend na pensionering.",
        ),
      );
      break;

    case "single-limited-shortfall":
      blocks.push(
        block(
          "retirement-scenario",
          "Na pensionering daalt de maximale hypotheek licht onder het geadviseerde " +
            "hypotheekbedrag. Het verschil is beperkt (minder dan 5% van de hypotheek). " +
            "De hypotheeklasten blijven naar verwachting verantwoord, mede gelet op de " +
            "aflossing die gedurende de looptijd plaatsvindt.",
        ),
      );
      break;

    case "single-material-shortfall":
      blocks.push(
        block(
          "retirement-scenario",
          "Na pensionering daalt de maximale hypotheek onder het geadviseerde " +
            "hypotheekbedrag. Wij adviseren om de gevolgen hiervan bewust mee te " +
            "nemen in uw financiële planning.",
        ),
      );
      break;

    case "couple-none-both": {
      const [first, second] = analysis.moments;
      blocks.push(
        block(
          "retirement-scenario",
          `Bij pensionering van zowel ${first.personName} als ${second.personName} ` +
            "blijft de maximale hypotheek boven het geadviseerde hypotheekbedrag. " +
            "De hypotheeklasten blijven daarmee naar verwachting passend.",
        ),
      );
      break;
    }

    case "couple-shortfall-increasing": {
      const [first, second] = analysis.moments;
      blocks.push(
        block(
          "retirement-scenario",
          `Bij pensionering van ${first.personName} daalt de maximale hypotheek ` +
            "onder het geadviseerde hypotheekbedrag. Bij pensionering van " +
            `${second.personName} neemt dit tekort verder toe. Wij adviseren om de ` +
            "gevolgen hiervan bewust mee te nemen in uw financiële planning.",
        ),
      );
      break;
    }

    case "couple-none-then-shortfall": {
      const [first, second] = analysis.moments;
      blocks.push(
        block(
          "retirement-scenario",
          `Bij pensionering van ${first.personName} blijft de maximale hypotheek ` +
            "boven het geadviseerde hypotheekbedrag. Na pensionering van " +
            `${second.personName} daalt de maximale hypotheek echter onder het ` +
            "geadviseerde bedrag. Wij adviseren om dit bij uw financiële planning " +
            "mee te nemen.",
        ),
      );
      break;
    }

    case "couple-shortfall-then-none": {
      const [first, second] = analysis.moments;
      blocks.push(
        block(
          "retirement-scenario",
          `Bij pensionering van ${first.personName} daalt de maximale hypotheek ` +
            "tijdelijk onder het geadviseerde hypotheekbedrag. Na pensionering van " +
            `${second.personName} herstelt de situatie en is de hypotheek weer ` +
            "passend binnen de normen.",
        ),
      );
      break;
    }

    case "couple-shortfall-stable":
      blocks.push(
        block(
          "retirement-scenario",
          "Bij pensionering daalt de maximale hypotheek onder het geadviseerde " +
            "hypotheekbedrag. Dit tekort blijft in grote lijnen stabiel na " +
            "pensionering van beide aanvragers. Wij adviseren om dit bij uw " +
            "financiële planning mee te nemen.",
        ),
      );
      break;
  }

  return blocks;
};

// ============================================================================
// Test examples (verify expected output)
// ============================================================================
//
// --- Example 1: Single, no shortfall ---
//
//   const result1 = analyzeRetirementScenario({
//     advisedMortgage: 300_000,
//     moments: [{
//       label: "AOW Harry (2047)",
//       year: 2047,
//       personName: "Harry",
//       maxMortgage: 320_000,
//       incomeComponents: [
//         { label: "AOW", person: "Harry", amount: 14_000 },
//         { label: "Pensioen", person: "Harry", amount: 24_000 },
//       ],
//     }],
//   });
//   // result1.kind === "single-no-shortfall"
//   // result1.hasShortfall === false
//   // result1.moments[0].shortfall === 0
//   // result1.moments[0].severity === "none"
//   // Narrative: "...passend na pensionering."
//
// --- Example 2: Single, material shortfall ---
//
//   const result2 = analyzeRetirementScenario({
//     advisedMortgage: 338_173,
//     moments: [{
//       label: "AOW Harry (2047)",
//       year: 2047,
//       personName: "Harry",
//       maxMortgage: 280_412,
//       incomeComponents: [
//         { label: "AOW", person: "Harry", amount: 14_000 },
//         { label: "Pensioen", person: "Harry", amount: 18_000 },
//       ],
//     }],
//   });
//   // result2.kind === "single-material-shortfall"
//   // result2.hasShortfall === true
//   // result2.moments[0].shortfall === 57_761
//   // result2.moments[0].shortfallPercentage ≈ 17.08%
//   // result2.moments[0].severity === "material"
//   // Narrative: "...bewust mee te nemen in uw financiële planning."
//
// --- Example 3: Couple, no shortfall first, shortfall second ---
//
//   const result3 = analyzeRetirementScenario({
//     advisedMortgage: 450_000,
//     moments: [
//       {
//         label: "AOW Harry (2047)",
//         year: 2047,
//         personName: "Harry",
//         maxMortgage: 460_000,
//         incomeComponents: [
//           { label: "AOW", person: "Harry", amount: 14_000 },
//           { label: "Pensioen", person: "Harry", amount: 30_000 },
//           { label: "Loondienst", person: "Harriette", amount: 45_000 },
//         ],
//       },
//       {
//         label: "AOW Harriette (2052)",
//         year: 2052,
//         personName: "Harriette",
//         maxMortgage: 385_000,
//         incomeComponents: [
//           { label: "AOW", person: "Harry", amount: 14_000 },
//           { label: "Pensioen", person: "Harry", amount: 30_000 },
//           { label: "AOW", person: "Harriette", amount: 14_000 },
//           { label: "Pensioen", person: "Harriette", amount: 18_000 },
//         ],
//       },
//     ],
//   });
//   // result3.kind === "couple-none-then-shortfall"
//   // result3.hasShortfall === true
//   // result3.moments[0].severity === "none"
//   // result3.moments[1].severity === "material"
//   // result3.moments[1].shortfall === 65_000
//   // Narrative: "Bij pensionering van Harry blijft...Na pensionering van
//   //   Harriette daalt..."
//
// --- Example 4: Couple, shortfall at both, increasing ---
//
//   const result4 = analyzeRetirementScenario({
//     advisedMortgage: 450_000,
//     moments: [
//       {
//         label: "AOW Harry (2047)",
//         year: 2047,
//         personName: "Harry",
//         maxMortgage: 420_000,
//         incomeComponents: [
//           { label: "AOW", person: "Harry", amount: 14_000 },
//           { label: "Pensioen", person: "Harry", amount: 30_000 },
//           { label: "Loondienst", person: "Harriette", amount: 45_000 },
//         ],
//       },
//       {
//         label: "AOW Harriette (2052)",
//         year: 2052,
//         personName: "Harriette",
//         maxMortgage: 385_000,
//         incomeComponents: [
//           { label: "AOW", person: "Harry", amount: 14_000 },
//           { label: "Pensioen", person: "Harry", amount: 30_000 },
//           { label: "AOW", person: "Harriette", amount: 14_000 },
//           { label: "Pensioen", person: "Harriette", amount: 18_000 },
//         ],
//       },
//     ],
//   });
//   // result4.kind === "couple-shortfall-increasing"
//   // result4.hasShortfall === true
//   // result4.moments[0].shortfall === 30_000
//   // result4.moments[1].shortfall === 65_000
//   // result4.worstShortfall === 65_000
//   // Narrative: "Bij pensionering van Harry daalt...Bij pensionering van
//   //   Harriette neemt dit tekort verder toe..."
