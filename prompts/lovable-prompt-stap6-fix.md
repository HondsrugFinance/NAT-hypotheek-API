# Lovable Fix — 2FA Auth Bug (data verdwijnt na login)

> Kopieer deze prompt in Lovable om de auth-bug te fixen die ervoor zorgt dat data kort verschijnt na login en dan weer verdwijnt.

---

## Het probleem

Na de 2FA-implementatie verdwijnen dossiers en profieldata een paar seconden na het inloggen. De oorzaak is een race condition tussen `onAuthStateChange`, de MFA AAL-check in `ProtectedRoute`, en React state updates.

**Symptomen:**
- Login werkt (email + wachtwoord)
- Data laadt kort correct na login
- Na 2-5 seconden: profiel toont "Laden...", dossiers tonen "Nog geen dossiers"
- Geen MFA-prompt verschijnt (ook niet verwacht, want nog geen 2FA ingeschakeld)

---

## Fix 1: `src/components/ProtectedRoute.tsx` — Verwijder de async AAL-check

De AAL-check in ProtectedRoute is de hoofdoorzaak. Het probleem: de check is asynchroon en veroorzaakt een state-update die de children unmount en opnieuw mount, waardoor alle child-state (dossiers, profiel) verloren gaat.

### Huidige code (kapot):

De ProtectedRoute doet nu waarschijnlijk iets als:

```typescript
// VERWIJDER DIT PATROON:
useEffect(() => {
  async function checkAuth() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { navigate('/auth'); return; }

    // DIT IS HET PROBLEEM — deze async check veroorzaakt een extra re-render
    const { data: aalData } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
    if (aalData?.nextLevel === 'aal2' && aalData?.currentLevel === 'aal1') {
      navigate('/auth');
      return;
    }

    setIsAuthenticated(true); // of setLoading(false)
  }
  checkAuth();
}, []);
```

Of er zit een timeout/fallback in, of de AAL-check faalt en reset de auth state.

### Nieuwe code (werkend):

Vervang de HELE `ProtectedRoute.tsx` door deze versie:

```typescript
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    // Initiële sessie-check
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        navigate("/auth");
      } else {
        setIsAuthenticated(true);
      }
      setIsLoading(false);
    });

    // Luister naar auth-wijzigingen
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        if (event === "SIGNED_OUT" || !session) {
          setIsAuthenticated(false);
          navigate("/auth");
        } else if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED") {
          setIsAuthenticated(true);
        }
      }
    );

    return () => subscription.unsubscribe();
  }, [navigate]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-lg">Laden...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
```

**Belangrijk:**
- GEEN `getAuthenticatorAssuranceLevel()` aanroep in ProtectedRoute
- GEEN timeout of fallback
- GEEN extra async checks na de sessie-check
- De AAL-check doen we ALLEEN in Auth.tsx bij de login-handler (dat is voldoende)

---

## Fix 2: `src/pages/Auth.tsx` — Fix de onAuthStateChange listener

Het tweede probleem: de `onAuthStateChange` listener in Auth.tsx reageert op events (zoals TOKEN_REFRESHED) en navigeert ongewenst naar `/`, wat kan conflicteren met andere componenten.

### Wat er fout gaat:

```typescript
// DIT PATROON IS KAPOT:
useEffect(() => {
  const { data: { subscription } } = supabase.auth.onAuthStateChange(
    async (event, session) => {
      if (session) {
        // PROBLEEM: dit vuurt ook bij TOKEN_REFRESHED
        // en kan de MFA-state resetten
        const { data: aalData } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
        if (aalData?.nextLevel === 'aal2' && aalData?.currentLevel === 'aal1') {
          // MFA nodig...
        } else {
          navigate('/'); // DIT VEROORZAAKT ONGEWENSTE REDIRECTS
        }
      }
    }
  );
  return () => subscription.unsubscribe();
}, []);
```

### Nieuwe code:

De `onAuthStateChange` listener in Auth.tsx moet ALLEEN reageren op uitloggen. De login-flow wordt VOLLEDIG afgehandeld door de `handleLogin` functie.

Zoek de `onAuthStateChange` in Auth.tsx en vervang deze door:

```typescript
useEffect(() => {
  // Check of gebruiker al ingelogd is bij mount
  supabase.auth.getSession().then(({ data: { session } }) => {
    if (session) {
      // Al ingelogd — check of MFA nodig is
      supabase.auth.mfa.getAuthenticatorAssuranceLevel().then(({ data: aalData }) => {
        if (aalData?.nextLevel === 'aal2' && aalData?.currentLevel === 'aal1') {
          // MFA nodig maar niet voltooid — blijf op auth pagina
          supabase.auth.mfa.listFactors().then(({ data: factors }) => {
            const totpFactor = factors?.totp?.find(f => f.status === 'verified');
            if (totpFactor) {
              setMfaFactorId(totpFactor.id);
              setMfaRequired(true);
            }
          });
        } else {
          // Volledig geauthenticeerd — redirect naar home
          navigate('/');
        }
      });
    }
  });

  // Luister ALLEEN naar sign-out events
  const { data: { subscription } } = supabase.auth.onAuthStateChange(
    (event, _session) => {
      if (event === 'SIGNED_OUT') {
        // Reset MFA state bij uitloggen
        setMfaRequired(false);
        setMfaFactorId(null);
      }
      // BELANGRIJK: GEEN navigate('/') hier bij SIGNED_IN of TOKEN_REFRESHED
      // De login-flow wordt afgehandeld door handleLogin()
    }
  );

  return () => subscription.unsubscribe();
}, [navigate]);
```

### De handleLogin functie moet ONVERANDERD blijven:

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
    // bestaande error handling
    setLoading(false);
    return;
  }

  // Check MFA status
  const { data: aalData } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();

  if (aalData?.nextLevel === 'aal2' && aalData?.currentLevel === 'aal1') {
    const { data: factors } = await supabase.auth.mfa.listFactors();
    const totpFactor = factors?.totp?.find(f => f.status === 'verified');
    if (totpFactor) {
      setMfaFactorId(totpFactor.id);
      setMfaRequired(true);
      setLoading(false);
      return;
    }
  }

  // Geen MFA nodig → redirect
  navigate('/');
};
```

---

## Fix 3: Controleer dat er GEEN andere plekken zijn die auth-state beïnvloeden

Zoek in de hele codebase naar:
1. `onAuthStateChange` — mag ALLEEN voorkomen in `ProtectedRoute.tsx` en `Auth.tsx`
2. `getAuthenticatorAssuranceLevel` — mag ALLEEN voorkomen in `Auth.tsx` (login handler + mount check) en `Instellingen.tsx` (status weergave)
3. `navigate('/auth')` in componenten buiten `ProtectedRoute.tsx` — mag niet voorkomen
4. `setTimeout` of `setInterval` in auth-gerelateerde code — mag niet voorkomen
5. Elke `navigate('/')` in `onAuthStateChange` callbacks — VERWIJDER deze

Als je ergens een van bovenstaande vindt buiten de genoemde bestanden, verwijder het.

---

## Fix 4: Verwijder debug console.log statements

Verwijder alle `console.log` en `console.warn` statements die te maken hebben met auth, MFA, of sessie-checks. Deze zijn niet meer nodig en vervuilen de console.

---

## Verificatie

Test in een incognito-venster:

1. **Ga naar de app** → moet redirect naar `/auth` (login scherm)
2. **Log in met email + wachtwoord** → moet redirect naar `/` (dashboard)
3. **Dossiers pagina** → dossiers moeten verschijnen EN BLIJVEN STAAN (niet verdwijnen na een paar seconden)
4. **Profiel/Instellingen** → profieldata moet verschijnen EN BLIJVEN STAAN
5. **Wacht 30 seconden** → data moet nog steeds zichtbaar zijn
6. **Ververs de pagina (F5)** → moet ingelogd blijven, data moet laden
7. **Log uit** → moet terug naar `/auth`

## Samenvatting

| Bestand | Wijziging |
|---------|-----------|
| `src/components/ProtectedRoute.tsx` | Volledig vervangen: alleen sessie-check, GEEN AAL-check, GEEN timeout |
| `src/pages/Auth.tsx` | onAuthStateChange: ALLEEN reageren op SIGNED_OUT, niet op SIGNED_IN/TOKEN_REFRESHED. MFA-check alleen in handleLogin en bij mount. |
| Overige bestanden | Verwijder ongewenste onAuthStateChange listeners, setTimeout in auth code, en debug logging |
