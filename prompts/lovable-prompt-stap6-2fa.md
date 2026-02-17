# Lovable Prompt — Stap 6: 2FA met Microsoft Authenticator (TOTP)

> Kopieer deze prompt in Lovable om tweestapsverificatie toe te voegen via Supabase Auth MFA.

---

## Wat moet er gebeuren?

De app heeft nu simpele email/password login. We voegen **optionele 2FA** toe via TOTP (Time-based One-Time Password), compatible met Microsoft Authenticator, Google Authenticator, etc.

Supabase ondersteunt MFA out-of-the-box. Geen Supabase dashboard-configuratie nodig.

**Resultaat:**
- Gebruikers kunnen 2FA inschakelen via Instellingen
- Bij login met 2FA: na wachtwoord → 6-cijferige code invoeren
- Zonder 2FA: login werkt zoals voorheen

---

## Supabase MFA API referentie

Alle methoden zijn beschikbaar op de bestaande `supabase` client:

```typescript
// Factor aanmaken (enrollment)
const { data, error } = await supabase.auth.mfa.enroll({
  factorType: 'totp',
  friendlyName: 'Microsoft Authenticator'
});
// data = { id: 'factor-uuid', totp: { qr_code: 'data:image/svg+xml;...', secret: 'BASE32...' } }

// Challenge aanmaken (voor verificatie)
const { data: challenge, error } = await supabase.auth.mfa.challenge({
  factorId: 'factor-uuid'
});
// challenge = { id: 'challenge-uuid' }

// Code verifiëren
const { data: session, error } = await supabase.auth.mfa.verify({
  factorId: 'factor-uuid',
  challengeId: 'challenge-uuid',
  code: '123456'  // 6-cijferige code uit authenticator-app
});
// Bij succes: sessie gepromoveerd naar AAL2

// MFA-status checken
const { data, error } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
// data = { currentLevel: 'aal1' | 'aal2', nextLevel: 'aal1' | 'aal2' | null }
// currentLevel < nextLevel → gebruiker moet nog MFA verifiëren

// Ingeschreven factoren opvragen
const { data, error } = await supabase.auth.mfa.listFactors();
// data = { totp: [{ id, friendly_name, factor_type, status }], phone: [] }
// status = 'verified' betekent actief

// Factor verwijderen (uitschakelen)
const { data, error } = await supabase.auth.mfa.unenroll({
  factorId: 'factor-uuid'
});
```

---

## Stap 1: Maak `src/components/MfaEnroll.tsx`

Dit component toont het enrollment-proces: QR-code + verificatie.

```typescript
interface MfaEnrollProps {
  onSuccess: () => void;
  onCancel: () => void;
}
```

**Wat het moet doen:**

1. Bij mount: `supabase.auth.mfa.enroll({ factorType: 'totp', friendlyName: 'Microsoft Authenticator' })` aanroepen
2. QR-code tonen uit `data.totp.qr_code` (dit is een SVG data-URI, direct bruikbaar als `<img src={...} />`)
3. Onder de QR-code: de geheime sleutel tonen (`data.totp.secret`) met een "Kopieer" knop, als fallback voor handmatige invoer
4. Instructietekst: "Scan de QR-code met Microsoft Authenticator of voer de code handmatig in"
5. Invoerveld voor 6-cijferige verificatiecode (grote cijfers, auto-focus)
6. "Verifiëren" knop die:
   a. `supabase.auth.mfa.challenge({ factorId: data.id })` aanroept
   b. `supabase.auth.mfa.verify({ factorId, challengeId, code })` aanroept
   c. Bij succes: `onSuccess()` callback
   d. Bij fout: foutmelding tonen ("Ongeldige code. Probeer het opnieuw.")
7. "Annuleren" knop die `onCancel()` aanroept

**Styling:** Gebruik bestaande UI-componenten (Card, Button, Input, Label). Centreer de content. QR-code max 200x200px.

---

## Stap 2: Maak `src/components/MfaVerify.tsx`

Dit component toont het verificatie-scherm bij login.

```typescript
interface MfaVerifyProps {
  factorId: string;
  onSuccess: () => void;
  onError?: (error: string) => void;
}
```

**Wat het moet doen:**

1. Toon een Card met titel "Tweestapsverificatie"
2. Instructietekst: "Voer de 6-cijferige code in uit je authenticator-app"
3. Invoerveld voor 6-cijferige code:
   - `maxLength={6}`, `pattern="[0-9]*"`, `inputMode="numeric"`
   - Auto-focus bij mount
   - Grote, gecentreerde cijfers (text-2xl, text-center, tracking-widest)
4. "Verifiëren" knop die:
   a. `supabase.auth.mfa.challenge({ factorId })` aanroept
   b. `supabase.auth.mfa.verify({ factorId, challengeId, code })` aanroept
   c. Bij succes: `onSuccess()` callback
   d. Bij fout: foutmelding tonen + invoerveld leegmaken
5. Auto-submit wanneer 6 cijfers zijn ingevoerd (optioneel, maar prettig)
6. Loading state op de knop tijdens verificatie

**Styling:** Dezelfde stijl als de login-Card in `Auth.tsx`. Compact, centered.

---

## Stap 3: Wijzig `src/pages/Auth.tsx` — MFA bij login

### Wat er nu staat:

Na `signInWithPassword()` wordt de gebruiker direct doorgestuurd naar `/`.

### Wat het moet worden:

Na succesvolle `signInWithPassword()`:

1. Roep `supabase.auth.mfa.getAuthenticatorAssuranceLevel()` aan
2. **Als `data.nextLevel === 'aal2'` en `data.currentLevel === 'aal1'`:**
   - De gebruiker heeft 2FA ingeschakeld maar moet nog verifiëren
   - Haal de factorId op: `supabase.auth.mfa.listFactors()` → `data.totp[0].id`
   - Toon het `<MfaVerify />` component in plaats van het login-formulier
   - Bij succesvolle verificatie: `navigate('/')`
3. **Anders:** navigeer direct naar `/` (normaal gedrag)

### Nieuwe state variabelen:

```typescript
const [mfaRequired, setMfaRequired] = useState(false);
const [mfaFactorId, setMfaFactorId] = useState<string | null>(null);
```

### Aangepaste login handler:

```typescript
const handleLogin = async (e: React.FormEvent) => {
  e.preventDefault();
  setError('');
  setLoading(true);

  const { error: signInError } = await supabase.auth.signInWithPassword({
    email,
    password,
  });

  if (signInError) {
    // ... bestaande error handling ...
    setLoading(false);
    return;
  }

  // Check MFA status
  const { data: aalData } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();

  if (aalData?.nextLevel === 'aal2' && aalData?.currentLevel === 'aal1') {
    // Gebruiker heeft 2FA → toon verificatiescherm
    const { data: factors } = await supabase.auth.mfa.listFactors();
    const totpFactor = factors?.totp?.find(f => f.status === 'verified');
    if (totpFactor) {
      setMfaFactorId(totpFactor.id);
      setMfaRequired(true);
      setLoading(false);
      return;
    }
  }

  // Geen MFA → normaal doorsturen
  navigate('/');
};
```

### Render logica:

```tsx
// In de return:
{mfaRequired && mfaFactorId ? (
  <MfaVerify
    factorId={mfaFactorId}
    onSuccess={() => navigate('/')}
  />
) : mode === 'login' ? (
  // ... bestaand login-formulier ...
) : (
  // ... bestaand wachtwoord-reset formulier ...
)}
```

---

## Stap 4: Wijzig `src/pages/Instellingen.tsx` — 2FA beheer

Voeg een nieuwe sectie toe aan de Instellingen-pagina voor 2FA-beheer.

### Nieuwe state:

```typescript
const [mfaEnabled, setMfaEnabled] = useState(false);
const [mfaFactorId, setMfaFactorId] = useState<string | null>(null);
const [showMfaEnroll, setShowMfaEnroll] = useState(false);
const [mfaLoading, setMfaLoading] = useState(true);
```

### Bij mount — MFA status laden:

```typescript
useEffect(() => {
  async function checkMfaStatus() {
    const { data } = await supabase.auth.mfa.listFactors();
    const verifiedFactor = data?.totp?.find(f => f.status === 'verified');
    if (verifiedFactor) {
      setMfaEnabled(true);
      setMfaFactorId(verifiedFactor.id);
    }
    setMfaLoading(false);
  }
  checkMfaStatus();
}, []);
```

### 2FA sectie in de UI:

Voeg toe als een nieuwe Card/sectie, onder de bestaande secties:

**Titel:** "Tweestapsverificatie (2FA)"

**Als 2FA inactief:**
- Tekst: "Beveilig je account extra met een authenticator-app zoals Microsoft Authenticator."
- Knop: "2FA inschakelen" → `setShowMfaEnroll(true)`

**Als enrollment getoond wordt (`showMfaEnroll`):**
- Toon `<MfaEnroll onSuccess={handleEnrollSuccess} onCancel={() => setShowMfaEnroll(false)} />`
- `handleEnrollSuccess`: update state (mfaEnabled=true), toon toast "2FA is ingeschakeld"

**Als 2FA actief:**
- Badge/tekst: "✓ 2FA is actief" (groene badge)
- Knop: "2FA uitschakelen" → bevestigingsdialoog
- Bij bevestiging: `supabase.auth.mfa.unenroll({ factorId: mfaFactorId })` → update state, toast "2FA is uitgeschakeld"

---

## Stap 5: Wijzig `src/components/ProtectedRoute.tsx` — AAL check

### Wat er nu staat:

Checkt alleen of er een sessie is. Zo niet → redirect naar `/auth`.

### Wat erbij moet:

Na de sessie-check, ook de AAL-level controleren:

```typescript
// Na succesvolle sessie-check:
const { data: aalData } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();

if (aalData?.nextLevel === 'aal2' && aalData?.currentLevel === 'aal1') {
  // Gebruiker heeft 2FA maar zit nog op AAL1 → moet verifiëren
  navigate('/auth');
  return;
}
```

Dit voorkomt dat een gebruiker met 2FA de app kan gebruiken zonder de tweede factor te verifiëren (bijv. door direct een URL te bezoeken).

---

## Stap 6: Opruimen

1. **Imports toevoegen** in alle gewijzigde bestanden (MfaEnroll, MfaVerify, supabase client)
2. **Bestaande `onAuthStateChange` listeners** in Auth.tsx: zorg dat de MFA-state reset wordt bij sign-out
3. **Console.log verwijderen** — geen debug-logging in productie

---

## Verificatie

1. **Zonder 2FA:** Login werkt precies zoals voorheen (geen extra stap)
2. **2FA inschakelen:** Instellingen → "2FA inschakelen" → QR-code verschijnt → scan met MS Authenticator → voer code in → "2FA is actief"
3. **Login met 2FA:** Uitloggen → email + wachtwoord invoeren → 6-cijferig code-scherm verschijnt → code invoeren → redirect naar dashboard
4. **Verkeerde code:** Foutmelding "Ongeldige code", invoerveld leeg, opnieuw proberen
5. **ProtectedRoute:** Open een directe URL (bijv. `/dossiers`) zonder MFA-verificatie → redirect naar `/auth` voor verificatie
6. **2FA uitschakelen:** Instellingen → "2FA uitschakelen" → bevestigen → status "inactief" → login werkt weer zonder code
7. **Geheime sleutel kopiëren:** Bij enrollment, "Kopieer" knop werkt voor handmatige invoer in authenticator-app

## Samenvatting

| Bestand | Wijziging |
|---------|-----------|
| `src/components/MfaEnroll.tsx` | **Nieuw** — QR-code enrollment flow |
| `src/components/MfaVerify.tsx` | **Nieuw** — 6-cijferig TOTP verificatie |
| `src/pages/Auth.tsx` | MFA-check na login, toon MfaVerify indien nodig |
| `src/pages/Instellingen.tsx` | 2FA sectie: status, inschakelen, uitschakelen |
| `src/components/ProtectedRoute.tsx` | AAL-level check, redirect bij onvolledige MFA |
