# Lovable Prompt — Stap 7: Rollen-systeem (RBAC)

> Kopieer deze prompt in Lovable om role-based access control toe te voegen.

---

## Wat moet er gebeuren?

De app heeft nu drie gebruikersrollen in de Supabase `profiles` tabel: `admin`, `adviseur`, en `viewer`. De database-kant (RLS policies) is al ingesteld. We moeten nu de **frontend** aanpassen zodat de UI zich aanpast aan de rol van de ingelogde gebruiker.

**Rollenmatrix:**

| Actie | Admin | Adviseur | Viewer |
|-------|-------|----------|--------|
| Dossiers bekijken | Alle | Alle | Alle |
| Dossiers aanmaken | Ja | Ja | Nee |
| Eigen dossiers bewerken | Ja | Ja | Nee |
| Andermans dossiers bewerken | Ja | Nee | Nee |
| Dossiers verwijderen | Alle | Eigen | Nee |
| Berekeningen uitvoeren (Aankoop/Aanpassen) | Ja | Ja | Nee |
| PDF downloaden | Ja | Ja | Ja |
| Gebruikers/rollen beheren | Ja | Nee | Nee |

---

## Stap 1: Maak `src/hooks/useUserRole.ts`

Deze hook haalt de rol op uit de `profiles` tabel in Supabase.

```typescript
import { useState, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';

export type UserRole = 'admin' | 'adviseur' | 'viewer';

interface UseUserRoleReturn {
  role: UserRole;
  isAdmin: boolean;
  isAdviseur: boolean;
  isViewer: boolean;
  isLoading: boolean;
}

export function useUserRole(): UseUserRoleReturn {
  const [role, setRole] = useState<UserRole>('adviseur');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchRole() {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        setIsLoading(false);
        return;
      }

      const { data: profile } = await supabase
        .from('profiles')
        .select('role')
        .eq('user_id', user.id)
        .single();

      if (profile?.role) {
        setRole(profile.role as UserRole);
      }
      setIsLoading(false);
    }

    fetchRole();

    // Herlaad rol bij auth-wijzigingen
    const { data: { subscription } } = supabase.auth.onAuthStateChange(() => {
      fetchRole();
    });

    return () => subscription.unsubscribe();
  }, []);

  return {
    role,
    isAdmin: role === 'admin',
    isAdviseur: role === 'adviseur',
    isViewer: role === 'viewer',
    isLoading,
  };
}
```

---

## Stap 2: Maak `src/contexts/RoleContext.tsx`

React context zodat elk component bij de rol kan.

```typescript
import { createContext, useContext } from 'react';
import { useUserRole, type UserRole } from '@/hooks/useUserRole';

interface RoleContextType {
  role: UserRole;
  isAdmin: boolean;
  isAdviseur: boolean;
  isViewer: boolean;
  isLoading: boolean;
}

const RoleContext = createContext<RoleContextType>({
  role: 'adviseur',
  isAdmin: false,
  isAdviseur: true,
  isViewer: false,
  isLoading: true,
});

export function RoleProvider({ children }: { children: React.ReactNode }) {
  const roleData = useUserRole();
  return (
    <RoleContext.Provider value={roleData}>
      {children}
    </RoleContext.Provider>
  );
}

export function useRoleContext() {
  return useContext(RoleContext);
}
```

---

## Stap 3: Wrap de app met `RoleProvider`

In `App.tsx`, voeg de `RoleProvider` toe **binnen** de bestaande providers (na `NatConfigProvider`, binnen de `QueryClientProvider`):

```typescript
import { RoleProvider } from '@/contexts/RoleContext';

// In de return, binnen ProtectedRoute:
<RoleProvider>
  {/* bestaande routes */}
</RoleProvider>
```

**Let op:** De `RoleProvider` moet BINNEN `ProtectedRoute` staan (want het heeft een ingelogde user nodig), maar BUITEN de individuele pagina-routes.

---

## Stap 4: Navigatie aanpassen

Pas de navigatie-component aan (waarschijnlijk een header of navbar).

### Voor admin:
Voeg een "Beheer" link toe in de navigatie, naast "Start" en "Dossiers":

```tsx
const { isAdmin } = useRoleContext();

// In de navigatie-links:
{isAdmin && (
  <Link to="/admin">Beheer</Link>
)}
```

Gebruik hetzelfde styling-patroon als de bestaande "Start" en "Dossiers" links.

### Voor viewer:
Geen wijziging in de navigatie — viewer ziet dezelfde links maar bepaalde knoppen op pagina's worden verborgen.

---

## Stap 5: Home-pagina aanpassen (Index)

Op de home-pagina staan drie kaarten: "Nieuw dossier", "Aankoop woning", "Aanpassen hypotheek".

### Voor viewer:
Verberg de knoppen "Dossier aanmaken" en "Start berekening" op de kaarten. Toon in plaats daarvan een grijze tekst "Alleen-lezen toegang".

```tsx
const { isViewer } = useRoleContext();

// Bij elke actie-knop op de kaarten:
{!isViewer ? (
  <Button onClick={...}>Dossier aanmaken</Button>
) : (
  <p className="text-sm text-muted-foreground">Alleen-lezen toegang</p>
)}
```

---

## Stap 6: Dossiers-pagina aanpassen

Op de dossiers-lijst pagina:

### Voor viewer:
- Verberg de "Nieuw dossier" knop (als die er staat)
- Dossiers zijn nog steeds klikbaar en te bekijken

### Voor admin:
- Geen wijziging (kan alles al)

---

## Stap 7: Dossier detail-pagina aanpassen

Op de dossier detail-pagina (`/dossier/:id`):

### Voor viewer:
- Verberg "Bewerken", "Verwijderen", en "Nieuwe aanvraag" knoppen
- Dossier-data en PDF-download blijven beschikbaar

### Voor adviseur:
- Toon "Bewerken" en "Verwijderen" ALLEEN als het dossier van de ingelogde gebruiker is
- Vergelijk `dossier.owner_id` met de huidige `user.id`

### Voor admin:
- Toon "Bewerken" en "Verwijderen" altijd (ook bij andermans dossiers)

```tsx
const { isAdmin, isViewer } = useRoleContext();
const [currentUserId, setCurrentUserId] = useState<string | null>(null);

useEffect(() => {
  supabase.auth.getUser().then(({ data: { user } }) => {
    setCurrentUserId(user?.id ?? null);
  });
}, []);

const isOwner = dossier.owner_id === currentUserId;
const canEdit = isAdmin || (isOwner && !isViewer);
const canDelete = isAdmin || (isOwner && !isViewer);

// In de UI:
{canEdit && <Button>Bewerken</Button>}
{canDelete && <Button variant="destructive">Verwijderen</Button>}
```

---

## Stap 8: Berekening-pagina's beschermen

De pagina's `/aankoop` en `/aanpassen` zijn berekening-wizards. Viewers mogen deze niet gebruiken.

Voeg bovenaan beide componenten toe:

```tsx
const { isViewer } = useRoleContext();
const navigate = useNavigate();

useEffect(() => {
  if (isViewer) {
    toast({
      title: "Geen toegang",
      description: "Je hebt geen rechten om berekeningen uit te voeren.",
      variant: "destructive",
    });
    navigate('/');
  }
}, [isViewer, navigate]);
```

---

## Stap 9: Instellingen-pagina — Rolbadge

Op de Instellingen/Profiel-pagina, toon de huidige rol als badge bovenaan de pagina.

```tsx
const { role } = useRoleContext();

// Boven de bestaande secties, onder de paginatitel:
const roleBadgeColor = {
  admin: 'bg-green-100 text-green-800 border-green-200',
  adviseur: 'bg-blue-100 text-blue-800 border-blue-200',
  viewer: 'bg-gray-100 text-gray-800 border-gray-200',
};

const roleLabel = {
  admin: 'Administrator',
  adviseur: 'Adviseur',
  viewer: 'Alleen lezen',
};

<div className="flex items-center gap-2 mb-4">
  <span className={`px-3 py-1 rounded-full text-sm font-medium border ${roleBadgeColor[role]}`}>
    {roleLabel[role]}
  </span>
</div>
```

De badge is read-only — gebruikers kunnen hun eigen rol niet wijzigen.

---

## Stap 10: Admin-pagina (`/admin`)

Maak een nieuwe pagina `src/pages/Admin.tsx` die alleen toegankelijk is voor admins.

### Route toevoegen in App.tsx:

```tsx
import Admin from '@/pages/Admin';

// Bij de routes, binnen ProtectedRoute:
<Route path="/admin" element={<Admin />} />
```

### Pagina-inhoud:

**Titel:** "Gebruikersbeheer"

**Bescherming:** Bovenaan het component:

```tsx
const { isAdmin, isLoading } = useRoleContext();
const navigate = useNavigate();

useEffect(() => {
  if (!isLoading && !isAdmin) {
    navigate('/');
  }
}, [isAdmin, isLoading, navigate]);

if (isLoading || !isAdmin) return null;
```

**Gebruikerstabel:**

Haal alle profielen op (admin heeft RLS-toegang tot alle profielen):

```tsx
const [users, setUsers] = useState<any[]>([]);

useEffect(() => {
  async function fetchUsers() {
    const { data } = await supabase
      .from('profiles')
      .select('*')
      .order('naam');
    setUsers(data ?? []);
  }
  fetchUsers();
}, []);
```

**Tabel layout:**

| Naam | Bedrijf | Rol | Acties |
|------|---------|-----|--------|

- **Naam**: uit `profiles.naam`
- **Bedrijf**: uit `profiles.bedrijfsnaam`
- **Rol**: Dropdown (Select) met opties: Admin, Adviseur, Alleen lezen
  - De huidige gebruiker (admin zelf) kan zijn eigen rol NIET wijzigen (voorkomt lock-out)
  - Disable de dropdown voor de eigen rij
- **Acties**: geen extra acties voorlopig

**Rolwijziging handler:**

```tsx
async function handleRoleChange(userId: string, newRole: string) {
  // Bevestigingsdialoog
  const confirmed = window.confirm(
    `Weet je zeker dat je de rol wilt wijzigen naar "${newRole}"?`
  );
  if (!confirmed) return;

  const { error } = await supabase
    .from('profiles')
    .update({ role: newRole })
    .eq('user_id', userId);

  if (error) {
    toast({
      title: "Fout bij wijzigen rol",
      description: error.message,
      variant: "destructive",
    });
  } else {
    toast({
      title: "Rol gewijzigd",
      description: `Rol is bijgewerkt naar ${newRole}.`,
    });
    // Herlaad de lijst
    fetchUsers();
  }
}
```

**Styling:** Gebruik bestaande UI-componenten (Card, Table, Select, Button). Zelfde stijl als de rest van de app.

---

## Stap 11: Aanvraag-wizard beschermen

Op de aanvraag-pagina (`/aanvraag/:dossierId`): zelfde bescherming als de berekening-pagina's.

```tsx
const { isViewer } = useRoleContext();

useEffect(() => {
  if (isViewer) {
    toast({
      title: "Geen toegang",
      description: "Je hebt geen rechten om aanvragen te bewerken.",
      variant: "destructive",
    });
    navigate('/');
  }
}, [isViewer]);
```

---

## Verificatie

1. **Admin (Alex)**: ziet "Beheer" in navigatie, kan alle dossiers bewerken/verwijderen, kan rollen toewijzen op /admin
2. **Adviseur**: ziet geen "Beheer", kan eigen dossiers bewerken, kan andermans dossiers alleen lezen
3. **Viewer**: ziet geen aanmaak-knoppen, kan dossiers en PDFs alleen bekijken, kan niet navigeren naar /aankoop of /aanpassen
4. **Rolbadge**: Instellingen-pagina toont juiste rol in kleur
5. **Admin-pagina**: tabel met alle gebruikers, rol-dropdown werkt

---

## Samenvatting

| Bestand | Wijziging |
|---------|-----------|
| `src/hooks/useUserRole.ts` | **Nieuw** — haalt rol op uit profiles |
| `src/contexts/RoleContext.tsx` | **Nieuw** — React context voor rol |
| `App.tsx` | RoleProvider wrappen + /admin route |
| Navigatie/header | "Beheer" link voor admin |
| Index (home) | Verberg aanmaak-knoppen voor viewer |
| Dossiers-lijst | Verberg "Nieuw dossier" voor viewer |
| Dossier detail | Toon/verberg bewerken/verwijderen op basis van rol + ownership |
| `src/pages/Aankoop.tsx` | Redirect viewer naar / |
| `src/pages/Aanpassen.tsx` | Redirect viewer naar / |
| Aanvraag-wizard | Redirect viewer naar / |
| `src/pages/Instellingen.tsx` | Rolbadge tonen |
| `src/pages/Admin.tsx` | **Nieuw** — Gebruikersbeheer (admin-only) |
