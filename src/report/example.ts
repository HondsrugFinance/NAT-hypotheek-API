// ============================================================================
// Example: build a report from sample dossier data
// ============================================================================

import { buildReport, mapToPdf } from "./index";
import type { ReportBuilderInput } from "./index";

const input: ReportBuilderInput = {
  dossier: {
    id: "1",
    dossierNummer: "HF-2026-001",
    adviesDatum: "2026-02-12",
    adviseurNaam: "Alex Kuijper CFP\u00ae",
    kantoorNaam: "Hondsrug Finance",
  },
  applicants: {
    hasPartner: false,
    primary: {
      voornamen: "Harry",
      achternaam: "Slinger",
      geboortedatum: "1986-01-15",
      telefoon: "06-12345678",
      email: "harry@example.nl",
      adres: {
        straat: "Kerkstraat",
        huisnummer: "12",
        postcode: "9471 AB",
        woonplaats: "Zuidlaren",
      },
    },
  },
  household: {
    burgerlijkeStaat: "Ongehuwd",
    samenlevingsvorm: "Alleenstaand",
    dependents: 0,
  },
  currentSituation: {
    residences: [],
    mortgages: [],
  },
  income: {
    primary: {
      employment: [
        {
          jaarbedrag: 80000,
          soortDienstverband: "Loondienst \u2013 vast",
          beroep: "Software engineer",
          urenPerWeek: 40,
        },
      ],
      pension: [],
      annuity: [],
      rental: [],
      partnerAlimonyReceived: [],
      other: [],
    },
    partner: null,
  },
  obligations: {
    bkr: [],
    nonBkr: [],
    privateLease: [],
    studyLoans: [],
    partnerAlimonyPaid: [],
  },
  protections: {
    aov: [],
    orv: [],
    lifeInsurance: [],
    annuityPolicies: [],
  },
  assets: {
    savings: [{ naam: "Spaarrekening", bedrag: 25000 }],
    investments: [],
    otherAssets: [],
  },
  objective: {
    type: "aankoop-bestaande-bouw",
    purchasePrice: 350000,
  },
  property: {
    address: {
      straat: "Voorbeeldstraat",
      huisnummer: "12",
      postcode: "1234 AB",
      woonplaats: "Emmen",
    },
    propertyType: "Woning",
    marketValue: 350000,
    constructionYear: 1998,
    energyLabel: "A",
  },
  financingSetup: {
    costs: {
      transferTaxAmount: 7000,
      valuationCost: 750,
      adviceCost: 2500,
      notaryCost: 1500,
      brokerCost: 0,
      penaltyInterest: 0,
      otherCosts: 0,
    },
    equity: {
      savingsContribution: 25000,
      gift: 0,
      starterLoan: 0,
    },
    nhg: {
      selected: true,
      feeAmount: 1422.95,
    },
    totalCosts: 13172.95,
    totalEquity: 25000,
    totalInvestment: 363172.95,
    requiredMortgageAmount: 338172.95,
  },
  newMortgage: {
    lender: "ING",
    productLine: "Annu\u00eftair Hypotheek",
    passDate: "2026-03-01",
    registrationAmount: 380000,
    loanParts: [
      {
        id: "lp-1",
        aflosvorm: "annuiteit",
        bedragBox1: 338172.95,
        bedragBox3: 0,
        looptijdMaanden: 360,
        rentepercentage: 4.5,
        rentevastePeriode: "10 jaar",
      },
    ],
  },
  calculations: {
    maxMortgageNow: {
      maximaleHypotheekBox1: 326250,
      toetsinkomen: 80000,
      toetsrente: 5,
    },
    maxMortgageRetirement: null,
    monthlyCosts: {
      brutoMaandlast: 1855,
      renteaftrek: 588,
      nettoMaandlast: 1267,
    },
    tax: {
      ewf: 1225,
      hypotheekrenteaftrek: 588,
    },
  },
  fiscalHistory: {
    hasPreviousOwnerOccupiedHome: false,
    interestDeductionStartYear: 2026,
    interestDeductionEndYear: 2056,
    remainingInterestDeductionMonths: 360,
    hasEquityReserve: false,
    equityReserveAmount: 0,
    box3LoanAmount: 0,
  },
  adviceProfile: {
    customerPriority: "Stabiele maandlast",
    riskAppetite: "Gemiddeld",
    wantsStablePayments: true,
    wantsFlexibility: false,
    customerRejectedOrv: false,
  },
};

// Build the report viewmodel
const report = buildReport(input);

// Map to PDF-ready structure
const pdf = mapToPdf(report);

// Output
console.log("=== REPORT VIEWMODEL ===");
console.log(JSON.stringify(report, null, 2));

console.log("\n=== PDF SECTIONS ===");
for (const section of pdf.sections) {
  if (!section.visible) continue;
  console.log(`\n--- ${section.title} ---`);
  for (const narrative of section.narratives) {
    console.log(`  ${narrative}`);
  }
  if (section.rows) {
    for (const row of section.rows) {
      if (row.label) console.log(`  ${row.label}: ${row.value}`);
    }
  }
}

console.log("\n=== VISIBILITY ===");
console.log(JSON.stringify(report.visibility, null, 2));
