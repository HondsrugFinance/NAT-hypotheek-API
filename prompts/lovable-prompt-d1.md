# Lovable Prompt D1: Download PDF knop in Samenvatting

## Doel

Voeg een "Download PDF" knop toe aan de Samenvatting stap (stap 6) die een POST
doet naar de NAT API en een professionele PDF download triggert.

---

## Stap 1: PDF download functie

Maak een nieuw bestand `src/utils/pdfDownload.ts`:

```typescript
import { API_BASE_URL, getApiHeaders } from '@/config/apiConfig';
import { formatBedrag, formatBedragDecimaal } from '@/utils/berekeningen';
import type { AankoopInvoer, Scenario, NatResultaat, MaandlastenResultaat } from '@/types/hypotheek';

interface WijzigingBerekening {
  id: string;
  naam: string;
  aanpassingType: 'verhogen' | 'oversluiten' | 'uitkopen';
  huidigeHypotheek: number;
  verbouwing: number;
  uitkoopPartner: number;
  adviesBemiddeling: number;
  hypotheekakte: number;
  taxatiekosten: number;
  boeterente: number;
  nhgToepassen: boolean;
  nhgKosten: number;
  eigenGeld: number;
  extraPostenInvestering: { label: string; value: number }[];
  extraPostenKosten: { label: string; value: number }[];
  extraPostenEigenMiddelen: { label: string; value: number }[];
  wozWaarde: number;
}

// Energielabel display mapping
const energieLabelDisplay: Record<string, string> = {
  'geen_label': 'Geen label',
  'E_F_G': 'E, F of G',
  'C_D': 'C of D',
  'A_B': 'A of B',
  'A+_A++': 'A+ of A++',
  'A+++': 'A+++',
  'A++++': 'A++++',
  'A++++_garantie': 'A++++ met garantie',
};

function buildHaalbaarheidData(
  invoer: AankoopInvoer,
  natResultaten: (NatResultaat | null)[]
) {
  return invoer.haalbaarheidsBerekeningen.map((ber, index) => {
    const inkomen = ber.inkomenGegevens;
    const natResultaat = natResultaten[index];
    const hasPartner = !invoer.klantGegevens.alleenstaand;
    const totaalInkomen = (inkomen.hoofdinkomenAanvrager || 0) + (inkomen.hoofdinkomenPartner || 0);

    // Inkomen items
    const inkomen_items: { label: string; waarde: string; is_totaal?: boolean }[] = [
      { label: 'Aanvrager', waarde: formatBedrag(inkomen.hoofdinkomenAanvrager || 0) },
    ];
    if (hasPartner) {
      inkomen_items.push({ label: 'Partner', waarde: formatBedrag(inkomen.hoofdinkomenPartner || 0) });
    }
    inkomen_items.push({ label: 'Totaal inkomen', waarde: formatBedrag(totaalInkomen), is_totaal: true });

    // Energie items
    const energie_items: { label: string; waarde: string }[] = [];
    if (ber.onderpand.energielabel !== 'geen_label') {
      energie_items.push({
        label: 'Energielabel',
        waarde: energieLabelDisplay[ber.onderpand.energielabel] || ber.onderpand.energielabel,
      });
    }
    if (ber.onderpand.bedragEbvEbb > 0) {
      energie_items.push({ label: 'EBV/EBB bedrag', waarde: formatBedrag(ber.onderpand.bedragEbvEbb) });
    }

    // Verplichtingen items
    const verplichtingen_items: { label: string; waarde: string }[] = [];
    if (inkomen.limieten > 0) verplichtingen_items.push({ label: 'Limieten', waarde: formatBedrag(inkomen.limieten) });
    if (inkomen.maandlastLeningen > 0) verplichtingen_items.push({ label: 'Leningen (maandlast)', waarde: formatBedrag(inkomen.maandlastLeningen) });
    if (inkomen.studielening > 0) verplichtingen_items.push({ label: 'Studielening', waarde: formatBedrag(inkomen.studielening) });
    if (inkomen.erfpachtcanon > 0) verplichtingen_items.push({ label: 'Erfpachtcanon (maandlast)', waarde: formatBedrag(inkomen.erfpachtcanon) });
    if (inkomen.partneralimentatieBetalen > 0) verplichtingen_items.push({ label: 'Partneralimentatie', waarde: formatBedrag(inkomen.partneralimentatieBetalen) });

    return {
      naam: ber.naam,
      inkomen_items,
      energie_items,
      verplichtingen_items,
      max_annuitair: natResultaat ? formatBedrag(natResultaat.maxHypAnnuitairBox1) : '',
      max_werkelijk: natResultaat ? formatBedrag(natResultaat.maxHypNietAnnuitairBox1) : '',
    };
  });
}

function buildFinancieringData(invoer: AankoopInvoer, wijzigingBerekeningen?: WijzigingBerekening[]) {
  const result: any[] = [];

  // Aankoop-berekeningen
  if (invoer.berekeningen) {
    for (const ber of invoer.berekeningen) {
      const woningTypeLabel = ber.woningType === 'bestaande_bouw' ? 'Bestaande bouw'
        : ber.woningType === 'nieuwbouw_project' ? 'Nieuwbouw - project'
        : 'Nieuwbouw - eigen beheer';

      const posten: { label: string; waarde: string }[] = [];

      // Woningtype-specifieke posten (zelfde logica als SamenvattingStep)
      if (ber.woningType === 'bestaande_bouw') {
        if (ber.aankoopsomWoning > 0) posten.push({ label: 'Aankoopsom', waarde: formatBedrag(ber.aankoopsomWoning) });
        if (ber.overdrachtsbelasting > 0) posten.push({ label: 'Overdrachtsbelasting', waarde: formatBedrag(ber.overdrachtsbelasting) });
        if (ber.verbouwing > 0) posten.push({ label: 'Verbouwing', waarde: formatBedrag(ber.verbouwing) });
        if (ber.aankoopmakelaar > 0) posten.push({ label: 'Aankoopmakelaar', waarde: formatBedrag(ber.aankoopmakelaar) });
      } else if (ber.woningType === 'nieuwbouw_project') {
        if ((ber.koopsomGrond || 0) > 0) posten.push({ label: 'Koopsom grond', waarde: formatBedrag(ber.koopsomGrond || 0) });
        if ((ber.aanneemsom || 0) > 0) posten.push({ label: 'Aanneemsom', waarde: formatBedrag(ber.aanneemsom || 0) });
        if ((ber.meerwerkOpties || 0) > 0) posten.push({ label: 'Meerwerk – aannemer', waarde: formatBedrag(ber.meerwerkOpties || 0) });
        if ((ber.meerwerkEigenBeheer || 0) > 0) posten.push({ label: 'Meerwerk – eigen beheer', waarde: formatBedrag(ber.meerwerkEigenBeheer || 0) });
        if ((ber.bouwrente || 0) > 0) posten.push({ label: 'Bouwrente', waarde: formatBedrag(ber.bouwrente || 0) });
      } else {
        if (ber.koopsomKavel > 0) posten.push({ label: 'Koopsom kavel', waarde: formatBedrag(ber.koopsomKavel) });
        if (ber.overdrachtsbelasting > 0) posten.push({ label: 'Overdrachtsbelasting', waarde: formatBedrag(ber.overdrachtsbelasting) });
        if ((ber.sloopOudeWoning || 0) > 0) posten.push({ label: 'Sloop oude woning', waarde: formatBedrag(ber.sloopOudeWoning || 0) });
        if (ber.bouwWoning > 0) posten.push({ label: 'Bouw woning', waarde: formatBedrag(ber.bouwWoning) });
        if (ber.meerwerk > 0) posten.push({ label: 'Meerwerk', waarde: formatBedrag(ber.meerwerk) });
      }

      // Consumptief
      if ((ber.consumptief || 0) > 0) posten.push({ label: 'Consumptief', waarde: formatBedrag(ber.consumptief || 0) });

      // Kosten
      const notariskosten = (ber.hypotheekakte || 0) + (ber.transportakte || 0);
      if (notariskosten > 0) posten.push({ label: 'Notariskosten', waarde: formatBedrag(notariskosten) });
      if (ber.adviesBemiddeling > 0) posten.push({ label: 'Advies & bemiddeling', waarde: formatBedrag(ber.adviesBemiddeling) });
      if (ber.taxatiekosten > 0) posten.push({ label: 'Taxatiekosten', waarde: formatBedrag(ber.taxatiekosten) });
      if (ber.bankgarantie > 0) posten.push({ label: 'Bankgarantie', waarde: formatBedrag(ber.bankgarantie) });
      if (ber.nhgToepassen && ber.nhgKosten > 0) posten.push({ label: 'NHG kosten', waarde: formatBedrag(ber.nhgKosten) });

      // Extra posten
      ber.extraPostenAankoop?.forEach(post => {
        if (post.value > 0) posten.push({ label: post.label, waarde: formatBedrag(post.value) });
      });
      ber.extraPostenKosten?.forEach(post => {
        if (post.value > 0) posten.push({ label: post.label, waarde: formatBedrag(post.value) });
      });

      // Eigen middelen
      const eigen_middelen: { label: string; waarde: string }[] = [];
      if (ber.overbrugging > 0) eigen_middelen.push({ label: 'Af: Overbrugging', waarde: formatBedrag(ber.overbrugging) });
      if (ber.overwaarde > 0) eigen_middelen.push({ label: 'Af: Overwaarde', waarde: formatBedrag(ber.overwaarde) });
      if (ber.eigenGeld !== 0) {
        const isNeg = ber.eigenGeld < 0;
        eigen_middelen.push({
          label: isNeg ? 'Bij: Eigen geld' : 'Af: Eigen geld',
          waarde: formatBedrag(Math.abs(ber.eigenGeld)),
        });
      }
      if (ber.schenkingLening > 0) eigen_middelen.push({ label: 'Af: Schenking/lening', waarde: formatBedrag(ber.schenkingLening) });
      ber.extraPostenEigenMiddelen?.forEach(post => {
        if (post.value > 0) eigen_middelen.push({ label: `Af: ${post.label}`, waarde: formatBedrag(post.value) });
      });

      // Bereken totalen (gebruik bestaande functies)
      // Import berekenTotaleInvestering, berekenEigenMiddelen, berekenBenodigdeHypotheek
      // from '@/utils/berekeningen'
      const { berekenTotaleInvestering, berekenEigenMiddelen, berekenBenodigdeHypotheek } = await import('@/utils/berekeningen');
      const totaal = berekenTotaleInvestering(ber);
      const hypotheek = berekenBenodigdeHypotheek(ber);

      result.push({
        naam: ber.naam,
        type_label: woningTypeLabel,
        posten,
        totaal: formatBedrag(totaal),
        eigen_middelen,
        hypotheek: formatBedrag(hypotheek),
      });
    }
  }

  // Wijziging-berekeningen
  if (wijzigingBerekeningen) {
    for (const ber of wijzigingBerekeningen) {
      const typeLabel = ber.aanpassingType === 'verhogen' ? 'Hypotheek verhogen'
        : ber.aanpassingType === 'oversluiten' ? 'Hypotheek oversluiten'
        : 'Partner uitkopen';

      const posten: { label: string; waarde: string }[] = [];
      if (ber.huidigeHypotheek > 0) posten.push({ label: 'Huidige hypotheek', waarde: formatBedrag(ber.huidigeHypotheek) });
      if ((ber.aanpassingType === 'verhogen' || ber.aanpassingType === 'oversluiten') && ber.verbouwing > 0) {
        posten.push({ label: 'Verbouwing', waarde: formatBedrag(ber.verbouwing) });
      }
      if (ber.aanpassingType === 'uitkopen' && ber.uitkoopPartner > 0) {
        posten.push({ label: 'Uitkoop partner', waarde: formatBedrag(ber.uitkoopPartner) });
      }
      if (ber.adviesBemiddeling > 0) posten.push({ label: 'Advies & bemiddeling', waarde: formatBedrag(ber.adviesBemiddeling) });
      if (ber.hypotheekakte > 0) posten.push({ label: 'Notariskosten', waarde: formatBedrag(ber.hypotheekakte) });
      if (ber.taxatiekosten > 0) posten.push({ label: 'Taxatiekosten', waarde: formatBedrag(ber.taxatiekosten) });
      if (ber.aanpassingType === 'oversluiten' && ber.boeterente > 0) {
        posten.push({ label: 'Boeterente', waarde: formatBedrag(ber.boeterente) });
      }
      if (ber.nhgToepassen && ber.nhgKosten > 0) posten.push({ label: 'NHG kosten', waarde: formatBedrag(ber.nhgKosten) });
      ber.extraPostenInvestering?.forEach(post => {
        if (post.value > 0) posten.push({ label: post.label, waarde: formatBedrag(post.value) });
      });
      ber.extraPostenKosten?.forEach(post => {
        if (post.value > 0) posten.push({ label: post.label, waarde: formatBedrag(post.value) });
      });

      // Totaal
      let totaal = ber.huidigeHypotheek + ber.adviesBemiddeling + ber.hypotheekakte + ber.taxatiekosten;
      if (ber.aanpassingType === 'verhogen' || ber.aanpassingType === 'oversluiten') totaal += ber.verbouwing;
      if (ber.aanpassingType === 'uitkopen') totaal += ber.uitkoopPartner;
      if (ber.aanpassingType === 'oversluiten') totaal += ber.boeterente;
      totaal += (ber.extraPostenInvestering || []).reduce((s, p) => s + p.value, 0);
      totaal += (ber.extraPostenKosten || []).reduce((s, p) => s + p.value, 0);
      if (ber.nhgToepassen) totaal += ber.nhgKosten;

      const eigenMiddelen = ber.eigenGeld + (ber.extraPostenEigenMiddelen || []).reduce((s, p) => s + p.value, 0);
      const hypotheek = totaal - eigenMiddelen;

      const eigen_middelen: { label: string; waarde: string }[] = [];
      if (ber.eigenGeld !== 0) {
        eigen_middelen.push({
          label: ber.eigenGeld < 0 ? 'Bij: Eigen geld' : 'Af: Eigen geld',
          waarde: formatBedrag(Math.abs(ber.eigenGeld)),
        });
      }
      ber.extraPostenEigenMiddelen?.forEach(post => {
        if (post.value > 0) eigen_middelen.push({ label: `Af: ${post.label}`, waarde: formatBedrag(post.value) });
      });

      result.push({
        naam: ber.naam,
        type_label: typeLabel,
        posten,
        totaal: formatBedrag(totaal),
        eigen_middelen,
        hypotheek: formatBedrag(hypotheek),
      });
    }
  }

  return result;
}

function buildMaandlastenData(
  scenarios: Scenario[],
  maandlastenResultaten: MaandlastenResultaat[],
  apiRenteaftrek?: Record<string, number>
) {
  const aflosvormNaam = (vorm: string): string => {
    switch (vorm) {
      case 'annuiteit': return 'Annuïtair';
      case 'lineair': return 'Lineair';
      case 'aflossingsvrij': return 'Aflossingsvrij';
      case 'spaarhypotheek': return '(Bank)spaar';
      default: return vorm;
    }
  };

  return scenarios.map((scenario, index) => {
    const resultaat = maandlastenResultaten[index];
    const externalRenteaftrek = apiRenteaftrek?.[scenario.id];

    const totaleInleg = scenario.leningDelen.reduce((sum, deel) => {
      return deel.aflossingsvorm === 'spaarhypotheek' ? sum + (deel.inleg || 0) : sum;
    }, 0);

    const effectiveRenteaftrek = externalRenteaftrek !== undefined ? externalRenteaftrek : resultaat.renteaftrek;
    const totaleBrutoMetInleg = resultaat.brutoBedrag + totaleInleg;
    const totaleNettoMetInleg = totaleBrutoMetInleg - effectiveRenteaftrek;
    const totaalLening = scenario.leningDelen.reduce((sum, deel) => sum + deel.bedrag + (deel.bedragBox3 || 0), 0);

    return {
      naam: scenario.naam,
      lening_delen: scenario.leningDelen.map((deel, i) => ({
        naam: deel.naam || `Leningdeel ${i + 1}`,
        aflosvorm: aflosvormNaam(deel.aflossingsvorm),
        looptijd: `${Math.round(deel.restantLooptijd / 12)} jaar`,
        rente: `${deel.rentepercentage.toFixed(2).replace('.', ',')}%`,
        rvp: `${Math.round(deel.rentevastePeriode / 12)} jaar`,
        bedrag: formatBedrag(deel.bedrag + (deel.bedragBox3 || 0)),
      })),
      totaal_lening: formatBedrag(totaalLening),
      rente: formatBedragDecimaal(resultaat.totaleRente),
      aflossing: formatBedragDecimaal(resultaat.totaleAflossing + totaleInleg),
      bruto: formatBedragDecimaal(totaleBrutoMetInleg),
      renteaftrek: formatBedragDecimaal(effectiveRenteaftrek),
      netto: formatBedragDecimaal(totaleNettoMetInleg),
    };
  });
}

export async function downloadSamenvattingPdf(
  invoer: AankoopInvoer,
  scenarios: Scenario[],
  maandlastenResultaten: MaandlastenResultaat[],
  natResultaten: (NatResultaat | null)[],
  apiRenteaftrek?: Record<string, number>,
  wijzigingBerekeningen?: WijzigingBerekening[],
) {
  const klantNaam = [
    invoer.klantGegevens.voornaamAanvrager,
    invoer.klantGegevens.achternaamAanvrager,
  ].filter(Boolean).join(' ');

  const payload = {
    klant_naam: klantNaam || '',
    datum: new Date().toLocaleDateString('nl-NL', { day: '2-digit', month: '2-digit', year: 'numeric' }),
    haalbaarheid: buildHaalbaarheidData(invoer, natResultaten),
    financiering: buildFinancieringData(invoer, wijzigingBerekeningen),
    maandlasten: buildMaandlastenData(scenarios, maandlastenResultaten, apiRenteaftrek),
  };

  const response = await fetch(`${API_BASE_URL}/samenvatting-pdf`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getApiHeaders(),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`PDF generatie mislukt: ${response.status}`);
  }

  // Download triggeren
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `samenvatting-hypotheek-${klantNaam.replace(/\s+/g, '-').toLowerCase() || 'berekening'}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

**Let op:** De `buildFinancieringData` functie gebruikt een dynamische `await import()`.
Verplaats de imports naar de top-level als Lovable dit niet ondersteunt:

```typescript
import { berekenTotaleInvestering, berekenEigenMiddelen, berekenBenodigdeHypotheek } from '@/utils/berekeningen';
```

En verwijder de `await import(...)` regel uit de functie.

---

## Stap 2: Download knop in SamenvattingStep

Pas `src/components/SamenvattingStep.tsx` aan:

**Bovenaan — import toevoegen:**
```typescript
import { Download, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { downloadSamenvattingPdf } from '@/utils/pdfDownload';
import { berekenMaandlasten } from '@/utils/berekeningen';
import { getFiscaleParameters } from '@/utils/fiscaleParameters';
import { useNatConfigContext } from '@/contexts/NatConfigContext';
```

**In de component, voeg state en handler toe:**
```typescript
const [isDownloading, setIsDownloading] = useState(false);
const { toast } = useToast();

const handleDownloadPdf = async () => {
  setIsDownloading(true);
  try {
    const maandlastenResultaten = scenarios.map(s => berekenMaandlasten(s, fiscaleParams));
    await downloadSamenvattingPdf(
      invoer,
      scenarios,
      maandlastenResultaten,
      natResultaten || [],
      apiRenteaftrek,
      wijzigingBerekeningen,
    );
    toast({ title: 'PDF gedownload', description: 'De samenvatting is als PDF opgeslagen.' });
  } catch (error) {
    console.error('PDF download error:', error);
    toast({
      title: 'PDF downloaden mislukt',
      description: 'Er is een fout opgetreden bij het genereren van de PDF. Probeer het opnieuw.',
      variant: 'destructive',
    });
  } finally {
    setIsDownloading(false);
  }
};
```

**In de JSX, voeg de knop toe boven de secties (na `<div className="space-y-6">`):**
```tsx
<div className="flex justify-end">
  <Button
    onClick={handleDownloadPdf}
    disabled={isDownloading}
    variant="outline"
    size="sm"
  >
    {isDownloading ? (
      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
    ) : (
      <Download className="h-4 w-4 mr-2" />
    )}
    {isDownloading ? 'PDF genereren...' : 'Download PDF'}
  </Button>
</div>
```

---

## Stap 3: CORS check

Het endpoint `/samenvatting-pdf` is een POST op de NAT API. CORS is al correct
geconfigureerd in `app.py` (allow_methods bevat POST, allow_origin_regex matcht
Lovable domeinen). Geen wijziging nodig.

---

## Samenvatting wijzigingen

| Bestand | Wijziging |
|---------|-----------|
| `src/utils/pdfDownload.ts` | **Nieuw** — PDF data builder + download functie |
| `src/components/SamenvattingStep.tsx` | Download knop + loading state + toast |

## Test

1. Ga naar Samenvatting stap na het invullen van een berekening
2. Klik "Download PDF"
3. Er verschijnt een loading spinner
4. De PDF wordt automatisch gedownload
5. Open de PDF en controleer dat alle 3 secties correct zijn
