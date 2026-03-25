"""
Calcasa Desktop Taxatie Client
===============================
Python client voor de Calcasa gRPC-Web API.
Gebruikt OAuth2 refresh_token voor authenticatie.
"""

import os
import json
import logging
import httpx
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

try:
    from Calcasa.protobuf_utils import (
        encode_field_string, encode_field_bytes, encode_field_varint,
        encode_field_double, encode_field_bool,
        decode_protobuf, grpc_web_encode, grpc_web_decode,
        pretty_print_protobuf, ProtoField, WIRE_LENGTH_DELIMITED,
    )
except ImportError:
    from protobuf_utils import (
        encode_field_string, encode_field_bytes, encode_field_varint,
        encode_field_double, encode_field_bool,
        decode_protobuf, grpc_web_encode, grpc_web_decode,
        pretty_print_protobuf, ProtoField, WIRE_LENGTH_DELIMITED,
    )

load_dotenv(Path(__file__).parent / ".env")

# ─── Calcasa Service Hosts ────────────────────────────────────
AUTH_HOST = "https://authentication.calcasa.nl"
ADRES_HOST = "https://adres.01.c.calcasa.nl"
VALUATION_HOST = "https://online-valuation.01.c.calcasa.nl"
BILLING_HOST = "https://billing.01.c.calcasa.nl"

# OAuth2
CLIENT_ID = "52e60157-29f3-5fc3-943f-10f081087a64"
TOKEN_URL = f"{AUTH_HOST}/oauth2/v2.0/token"

# Supabase (optioneel, voor token-persistentie)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


class CalcasaClient:
    """Client voor Calcasa Desktop Taxatie API (gRPC-Web).

    Token lifecycle:
    - Access token verloopt na ~1 uur
    - Refresh token is eenmalig: na gebruik krijg je een nieuwe
    - Bij elke refresh: nieuwe tokens opslaan in Supabase
    - _ensure_authenticated() wordt aangeroepen vóór elke API call
    """

    def __init__(self):
        # Probeer eerst Supabase, dan env var
        self.refresh_token = self._load_token_from_supabase() or os.getenv("CALCASA_REFRESH_TOKEN", "")
        self.access_token = os.getenv("CALCASA_BEARER_TOKEN", "")
        self._client = httpx.Client(timeout=30.0, follow_redirects=True)
        self._token_expires_at: float = 0  # Unix timestamp wanneer access token verloopt

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ─── Auth ─────────────────────────────────────────────────

    def _ensure_authenticated(self):
        """Zorg dat we een geldige access token hebben. Vernieuw als nodig."""
        import time
        if self.access_token and time.time() < self._token_expires_at - 60:
            return  # Token nog geldig (met 60s marge)
        logger.info("Access token verlopen of ontbreekt, vernieuwen...")
        self.refresh_access_token()

    def refresh_access_token(self) -> str:
        """Vernieuw access token via refresh_token, met Playwright fallback."""
        import time

        # Stap 1: Probeer huidige refresh token
        if self.refresh_token:
            try:
                result = self._refresh_via_token()
                self._token_expires_at = time.time() + 3500  # ~58 min
                return result
            except Exception as e:
                logger.warning("Refresh token mislukt (%s)", e)

        # Stap 2: Herlaad token uit Supabase (misschien is er een nieuwere)
        fresh_token = self._load_token_from_supabase()
        if fresh_token and fresh_token != self.refresh_token:
            self.refresh_token = fresh_token
            try:
                result = self._refresh_via_token()
                self._token_expires_at = time.time() + 3500
                return result
            except Exception as e:
                logger.warning("Supabase token ook mislukt (%s)", e)

        # Stap 3: Playwright fallback
        logger.info("Alle tokens mislukt, probeer Playwright login...")
        result = self._login_via_playwright()
        self._token_expires_at = time.time() + 3500
        return result

    def _refresh_via_token(self) -> str:
        """Vernieuw access token via refresh_token."""
        r = self._client.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "scope": "offline_access",
            "refresh_token": self.refresh_token,
            "client_id": CLIENT_ID,
        })
        r.raise_for_status()
        data = r.json()

        self.access_token = data["access_token"]
        new_refresh = data.get("refresh_token", "")
        if new_refresh:
            self.refresh_token = new_refresh
            self._save_new_refresh_token(new_refresh)

        return self.access_token

    def _login_via_playwright(self) -> str:
        """Login via headless browser (Playwright) en haal tokens op.
        Werkt zowel in sync als async (FastAPI) context."""
        username = os.getenv("CALCASA_USERNAME", "")
        password = os.getenv("CALCASA_PASSWORD", "")
        if not username or not password:
            raise ValueError(
                "Calcasa refresh token verlopen en geen CALCASA_USERNAME/"
                "CALCASA_PASSWORD beschikbaar voor automatische login."
            )

        logger.info("Playwright login gestart voor %s", username)

        # Detecteer of we in een async event loop zitten (FastAPI/uvicorn)
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            in_async = True
        except RuntimeError:
            in_async = False

        if in_async:
            # In async context: draai Playwright in een aparte thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._playwright_sync_login, username, password)
                tokens = future.result(timeout=60)
        else:
            tokens = self._playwright_sync_login(username, password)

        if not tokens or "access_token" not in tokens:
            raise RuntimeError("Playwright login gelukt maar geen tokens gevonden")

        self.access_token = tokens["access_token"]
        new_refresh = tokens.get("refresh_token", "")
        if new_refresh:
            self.refresh_token = new_refresh
            self._save_new_refresh_token(new_refresh)

        logger.info("Playwright login geslaagd, tokens vernieuwd")
        return self.access_token

    def _playwright_sync_login(self, username: str, password: str) -> dict:
        """Sync Playwright login (draait altijd in een eigen thread)."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError(
                "Playwright niet geïnstalleerd. Installeer met: "
                "pip install playwright && python -m playwright install chromium"
            )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # Stap 1: Ga naar Calcasa login pagina
            page.goto("https://app.desktoptaxatie.nl/", wait_until="networkidle")

            # Stap 2: Wacht op login formulier (Azure B2C redirect)
            page.wait_for_selector("input[name='E-mailadres'], input[name='logonIdentifier'], input[type='email']", timeout=15000)

            # Vul email in
            email_input = page.query_selector("input[name='E-mailadres'], input[name='logonIdentifier'], input[type='email']")
            email_input.fill(username)

            # Vul wachtwoord in
            password_input = page.query_selector("input[name='Wachtwoord'], input[name='password'], input[type='password']")
            password_input.fill(password)

            # Stap 3: Intercepteer de token response na login
            captured_tokens = {}

            def handle_response(response):
                if "oauth2" in response.url and "token" in response.url:
                    try:
                        data = response.json()
                        if "access_token" in data:
                            captured_tokens.update(data)
                    except Exception:
                        pass

            page.on("response", handle_response)

            # Klik login knop
            submit = page.query_selector("button[type='submit']")
            submit.click()

            # Wacht tot we op de app terechtkomen
            page.wait_for_url("**/overzicht**", timeout=30000, wait_until="domcontentloaded")

            # Geef de app even tijd om de token exchange te doen
            page.wait_for_timeout(3000)

            tokens = captured_tokens if captured_tokens.get("access_token") else None

            # Fallback: zoek tokens in localStorage/sessionStorage
            if not tokens:
                logger.info("Tokens niet via interceptie gevonden, zoek in storage...")
                tokens = page.evaluate("""() => {
                    for (const storage of [localStorage, sessionStorage]) {
                        for (let i = 0; i < storage.length; i++) {
                            const val = storage.getItem(storage.key(i));
                            try {
                                const obj = JSON.parse(val);
                                if (obj && obj.access_token && obj.refresh_token) return obj;
                            } catch {}
                        }
                    }
                    return null;
                }""")

            browser.close()

        return tokens

        self.access_token = tokens["access_token"]
        new_refresh = tokens.get("refresh_token", "")
        if new_refresh:
            self.refresh_token = new_refresh
            self._save_new_refresh_token(new_refresh)

        logger.info("Playwright login geslaagd, tokens vernieuwd")
        return self.access_token

    def _save_new_refresh_token(self, token: str):
        """Sla nieuw refresh token op in .env + Supabase."""
        # Lokaal: .env bestand
        env_path = Path(__file__).parent / ".env"
        try:
            if env_path.exists():
                content = env_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                new_lines = []
                found = False
                for line in lines:
                    if line.startswith("CALCASA_REFRESH_TOKEN="):
                        new_lines.append(f"CALCASA_REFRESH_TOKEN={token}")
                        found = True
                    else:
                        new_lines.append(line)
                if not found:
                    new_lines.append(f"CALCASA_REFRESH_TOKEN={token}")
                env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        except OSError:
            pass  # Read-only filesystem (Render)

        # Supabase: persistent over redeploys
        self._save_token_to_supabase(token)

    # ─── Supabase Token Persistentie ────────────────────────────

    @staticmethod
    def _supabase_headers() -> dict | None:
        """Supabase headers met service key. None als niet geconfigureerd."""
        if not SUPABASE_URL or not (SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY):
            return None
        key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
        return {
            "apikey": SUPABASE_ANON_KEY or key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    @staticmethod
    def _load_token_from_supabase() -> str:
        """Lees de laatst opgeslagen refresh token uit Supabase."""
        headers = CalcasaClient._supabase_headers()
        if not headers:
            return ""
        try:
            r = httpx.get(
                f"{SUPABASE_URL}/rest/v1/calcasa_tokens?select=refresh_token&limit=1",
                headers=headers,
                timeout=5.0,
            )
            if r.status_code == 200:
                rows = r.json()
                if rows and rows[0].get("refresh_token"):
                    token = rows[0]["refresh_token"]
                    if token != "placeholder":
                        logger.info("Calcasa refresh token geladen uit Supabase")
                        return token
        except Exception as e:
            logger.debug("Supabase token laden mislukt: %s", e)
        return ""

    @staticmethod
    def _save_token_to_supabase(token: str):
        """Sla refresh token op in Supabase.

        Strategie: DELETE alle rijen + INSERT nieuwe rij.
        Werkt ongeacht of id een int of uuid is.
        """
        headers = CalcasaClient._supabase_headers()
        if not headers:
            return
        try:
            # Stap 1: Verwijder bestaande rij(en)
            httpx.delete(
                f"{SUPABASE_URL}/rest/v1/calcasa_tokens?refresh_token=neq.IMPOSSIBLE_VALUE",
                headers=headers,
                timeout=5.0,
            )
            # Stap 2: Insert nieuwe rij
            r = httpx.post(
                f"{SUPABASE_URL}/rest/v1/calcasa_tokens",
                headers=headers,
                json={"refresh_token": token},
                timeout=5.0,
            )
            if r.status_code in (200, 201):
                logger.info("Calcasa refresh token opgeslagen in Supabase")
            else:
                logger.warning("Supabase token opslaan: %s %s", r.status_code, r.text[:200])
        except Exception as e:
            logger.debug("Supabase token opslaan mislukt: %s", e)

    def _grpc_headers(self) -> dict:
        """Standaard headers voor gRPC-Web calls."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/grpc-web-text",
            "Accept": "application/grpc-web-text",
            "X-Grpc-Web": "1",
            "X-User-Agent": "grpc-web-javascript/0.1",
        }

    def _grpc_call(self, host: str, service: str, method: str,
                   protobuf_bytes: bytes) -> bytes:
        """Voer een gRPC-Web call uit en return response protobuf bytes.

        Automatische re-auth bij 401 of bij gRPC UNAUTHENTICATED status.
        """
        self._ensure_authenticated()

        url = f"{host}/{service}/{method}"
        body = grpc_web_encode(protobuf_bytes)

        r = self._client.post(url, content=body, headers=self._grpc_headers())

        # Check voor auth-fouten (HTTP 401 of gRPC status 16 = UNAUTHENTICATED)
        needs_reauth = (
            r.status_code == 401
            or r.headers.get("grpc-status") == "16"
            or (r.status_code == 200 and not r.text and r.headers.get("grpc-status", "0") != "0")
        )

        if needs_reauth:
            logger.info("gRPC auth fout, hernieuw token en retry...")
            self._token_expires_at = 0  # Forceer re-auth
            self._ensure_authenticated()
            r = self._client.post(url, content=body, headers=self._grpc_headers())

        r.raise_for_status()
        return grpc_web_decode(r.text)

    # ─── GetBanks ─────────────────────────────────────────────

    def get_banks(self) -> list[dict]:
        """Haal alle beschikbare geldverstrekkers op."""
        response = self._grpc_call(
            AUTH_HOST,
            "calcasa.protocols.authentication.AuthenticationService",
            "GetBanks",
            b"",  # leeg request
        )
        return self._parse_banks(response)

    def _parse_banks(self, data: bytes) -> list[dict]:
        """Parse GetBanks response naar lijst van banken."""
        banks = []
        fields = decode_protobuf(data)
        for field in fields:
            if field.field_number == 1 and isinstance(field.value, bytes):
                bank = self._parse_bank(field.value)
                if bank:
                    banks.append(bank)
        return banks

    def _parse_bank(self, data: bytes) -> dict | None:
        """Parse een enkel bank-record."""
        fields = decode_protobuf(data)
        bank = {}
        for f in fields:
            if f.field_number == 1:
                bank["uuid"] = f.as_string()
            elif f.field_number == 2:
                bank["name"] = f.as_string()
            elif f.field_number == 3:
                bank["description"] = f.as_string()
            elif f.field_number == 4:
                bank["slug"] = f.as_string()
        return bank if "slug" in bank else None

    # ─── AdressenInPostcode ───────────────────────────────────

    def zoek_adressen(self, postcode: str) -> list[dict]:
        """Zoek alle adressen op een postcode."""
        request = encode_field_string(2, postcode.upper().replace(" ", ""))
        response = self._grpc_call(
            ADRES_HOST,
            "calcasa.protocols.adres.AdresLookupService",
            "AdressenInPostcode",
            request,
        )
        return self._parse_adressen(response)

    def _parse_adressen(self, data: bytes) -> list[dict]:
        """Parse AdressenInPostcode response.
        Structuur: herhaalde field 2 met geneste adres-records.
        """
        adressen = []
        fields = decode_protobuf(data)
        for field in fields:
            if field.field_number == 2 and isinstance(field.value, bytes):
                adres = self._parse_adres(field.value)
                if adres:
                    adressen.append(adres)
        return adressen

    def _parse_adres(self, data: bytes) -> dict | None:
        """Parse een enkel adres-record.
        Structuur: field 1 = ID (varint), field 2 = genest adres-object.
        Genest: field 1 = plaats, field 2 = postcode, field 3 = straat,
                field 4 = huisnummer (varint), field 5 = toevoeging (string).
        """
        fields = decode_protobuf(data)
        adres = {}
        for f in fields:
            if f.field_number == 1 and isinstance(f.value, int):
                adres["id"] = f.value
            elif f.field_number == 2 and isinstance(f.value, bytes):
                # Genest adres-object
                sub = decode_protobuf(f.value)
                for sf in sub:
                    if sf.field_number == 1:
                        adres["plaats"] = sf.as_string()
                    elif sf.field_number == 2:
                        adres["postcode"] = sf.as_string()
                    elif sf.field_number == 3:
                        adres["straat"] = sf.as_string()
                    elif sf.field_number == 4:
                        adres["huisnummer"] = sf.value if isinstance(sf.value, int) else sf.as_string()
                    elif sf.field_number == 5:
                        adres["toevoeging"] = sf.as_string()
        return adres if "huisnummer" in adres else None

    # ─── GetFormulierInstellingen ─────────────────────────────

    def get_formulier_instellingen(self, bank_slug: str) -> bytes:
        """Haal formulier-instellingen op voor een bank. Geeft raw bytes."""
        # Field 1 = bank slug, Field 2 = configuratie (vast)
        request = (
            encode_field_string(1, bank_slug)
            + encode_field_bytes(2, bytes([0x0C, 0x03, 0x06, 0x08, 0x0A, 0x12]))
        )
        return self._grpc_call(
            VALUATION_HOST,
            "calcasa.protocols.online_valuation.OnlineValuationService",
            "GetFormulierInstellingen",
            request,
        )

    # ─── GetControleVragen (wizard) ───────────────────────────

    def check_taxatie_mogelijk(
        self,
        bank_slug: str,
        adres_id: int,
        hypotheekbedrag: float,
        geschatte_waarde: float,
        bestaande_bouw: bool = True,
        eigen_bewoning: bool = True,
    ) -> dict:
        """
        Doorloop de GetControleVragen wizard om te checken of
        een desktoptaxatie mogelijk is.

        Returns:
            {
                "mogelijk": True/False,
                "blokkering": None of str (reden waarom niet mogelijk),
                "stappen": int (aantal wizard-stappen doorlopen),
            }
        """
        # Formulier instellingen bytes (vast, uit HAR)
        formulier_settings = bytes([0x0C, 0x03, 0x06, 0x08, 0x0A, 0x12])

        # Stap 1: Eerste call — geen antwoorden, krijg eerste vraag
        # Structuur: field 1 = bank, field 2 = {field 3 = adres_id, field 4 = formulier, field 5 = {field 1 = 5}}
        inner = (
            encode_field_varint(3, adres_id)
            + encode_field_bytes(4, formulier_settings)
            + encode_field_bytes(5, encode_field_varint(1, 5))
        )
        request = (
            encode_field_string(1, bank_slug)
            + encode_field_bytes(2, inner)
        )

        antwoorden = []  # list of raw answer bytes
        stap = 0

        for _ in range(10):  # max 10 stappen (safety)
            stap += 1
            response = self._grpc_call(
                VALUATION_HOST,
                "calcasa.protocols.online_valuation.OnlineValuationService",
                "GetControleVragen",
                request,
            )

            # Parse response
            fields = decode_protobuf(response)
            vragen = []       # parsed vraag dicts
            raw_vragen = []   # raw bytes per vraag
            status = None

            for f in fields:
                if f.field_number == 1 and isinstance(f.value, bytes):
                    vraag = self._parse_controle_vraag(f.value)
                    if vraag:
                        vragen.append(vraag)
                        raw_vragen.append(f.value)
                elif f.field_number == 2:
                    status = f.value  # 3 = formulier compleet

            # Check of wizard klaar is
            if status == 3 or not vragen:
                return {
                    "mogelijk": True,
                    "blokkering": None,
                    "stappen": stap,
                }

            # Beantwoord vragen
            for vraag, raw_bytes in zip(vragen, raw_vragen):
                antwoord = self._beantwoord_vraag(
                    vraag, raw_bytes,
                    hypotheekbedrag, geschatte_waarde,
                    bestaande_bouw, eigen_bewoning
                )
                if antwoord is None:
                    return {
                        "mogelijk": False,
                        "blokkering": vraag.get("blokkering", "Onbekende blokkering"),
                        "stappen": stap,
                    }
                antwoorden.append(antwoord)

            # Bouw nieuwe request met alle antwoorden
            request = self._build_controle_vragen_request(
                bank_slug, adres_id, antwoorden, formulier_settings
            )

        return {
            "mogelijk": False,
            "blokkering": "Te veel wizard-stappen (max 10)",
            "stappen": stap,
        }

    def _parse_controle_vraag(self, data: bytes) -> dict | None:
        """Parse een controle-vraag uit de response."""
        fields = decode_protobuf(data)
        vraag = {}
        for f in fields:
            if f.field_number == 1 and isinstance(f.value, int):
                vraag["type"] = f.value  # 3=bedrag, 4=keuze
            elif f.field_number == 2:
                vraag["id"] = f.as_string()
            elif f.field_number == 3:
                vraag["label"] = f.as_string()
            elif f.field_number == 7 and isinstance(f.value, bytes):
                # Validatieregel met blokkeermelding
                sub = decode_protobuf(f.value)
                for sf in sub:
                    if sf.field_number == 6:
                        # Blokkeermelding tekst (field 6, niet field 5)
                        vraag["blokkering"] = sf.as_string()
                    elif sf.field_number == 5 and isinstance(sf.value, bytes):
                        # Soms zit blokkeermelding in field 5 als string
                        vraag.setdefault("blokkering", sf.as_string())
                    elif sf.field_number == 1 and isinstance(sf.value, bytes):
                        # Min/max range
                        range_fields = decode_protobuf(sf.value)
                        for rf in range_fields:
                            if rf.field_number == 1 and isinstance(rf.value, float):
                                vraag["min"] = rf.value
                            elif rf.field_number == 2 and isinstance(rf.value, float):
                                vraag["max"] = rf.value
            elif f.field_number == 8 and isinstance(f.value, bytes):
                # Keuze-opties
                sub = decode_protobuf(f.value)
                opties = []
                for sf in sub:
                    if isinstance(sf.value, bytes):
                        optie_fields = decode_protobuf(sf.value)
                        optie = {}
                        for of_ in optie_fields:
                            if of_.field_number == 1:
                                optie["value"] = of_.as_string()
                            elif of_.field_number == 2:
                                optie["label"] = of_.as_string()
                        if optie:
                            opties.append(optie)
                if opties:
                    vraag["opties"] = opties
            elif f.field_number == 9 and isinstance(f.value, bytes):
                # Geselecteerd antwoord (bij herhaalde calls)
                vraag["huidig_antwoord"] = f.value

        return vraag if "id" in vraag else None

    def _beantwoord_vraag(self, vraag: dict, raw_vraag_bytes: bytes,
                          hypotheekbedrag: float, geschatte_waarde: float,
                          bestaande_bouw: bool, eigen_bewoning: bool) -> bytes | None:
        """Genereer het antwoord-protobuf voor een vraag.
        Echoot de originele vraag-bytes terug met field 9 als antwoord.
        None = geblokkeerd.
        """
        vraag_id = vraag.get("id", "")

        if vraag_id == "hypotheekbedrag":
            min_val = vraag.get("min", 25000)
            max_val = vraag.get("max", 1500000)
            if hypotheekbedrag < min_val or hypotheekbedrag > max_val:
                vraag["blokkering"] = vraag.get(
                    "blokkering",
                    f"Hypotheekbedrag moet tussen {min_val:,.0f} en {max_val:,.0f} liggen"
                )
                return None
            return self._inject_answer(raw_vraag_bytes, encode_field_double(2, hypotheekbedrag))

        elif vraag_id == "klantwaarde":
            min_val = vraag.get("min", 25000)
            max_val = vraag.get("max", 2000000)
            if geschatte_waarde < min_val or geschatte_waarde > max_val:
                vraag["blokkering"] = vraag.get(
                    "blokkering",
                    f"Woningwaarde moet tussen {min_val:,.0f} en {max_val:,.0f} liggen"
                )
                return None
            return self._inject_answer(raw_vraag_bytes, encode_field_double(2, geschatte_waarde))

        elif vraag_id == "bestaande_bouw":
            if not bestaande_bouw:
                vraag["blokkering"] = "Modelmatige waardebepaling is niet mogelijk voor nieuwbouw"
                return None
            # field 4 varint = 1 (keuze-index voor "Bestaande bouw")
            return self._inject_answer(raw_vraag_bytes, b"\x20\x01")

        elif vraag_id == "eigen_bewoning":
            if not eigen_bewoning:
                vraag["blokkering"] = "Desktop Taxatie alleen mogelijk voor eigen bewoning"
                return None
            # field 4 varint = 1 (keuze-index voor "Ja")
            return self._inject_answer(raw_vraag_bytes, b"\x20\x01")

        else:
            # Onbekende vraag — skip
            return None

    def _inject_answer(self, raw_vraag_bytes: bytes, answer_value: bytes) -> bytes:
        """Neem de originele vraag-bytes, strip onnodige velden, voeg field 9 toe.
        De portal echoot fields 1,2,3,7 terug en voegt field 9 toe als antwoord.
        """
        fields = decode_protobuf(raw_vraag_bytes)
        result = b""
        for f in fields:
            # Behoud field 1 (type), 2 (id), 3 (label), 7 (validatie)
            # Skip field 5, 8 (opties), 10, en andere metadata
            if f.field_number in (1, 2, 3, 7):
                if f.wire_type == WIRE_LENGTH_DELIMITED:
                    result += encode_field_bytes(f.field_number, f.value)
                else:
                    result += encode_field_varint(f.field_number, f.value)

        # Voeg antwoord toe als field 9
        result += encode_field_bytes(9, answer_value)
        return result

    def _build_controle_vragen_request(
        self, bank_slug: str, adres_id: int,
        antwoorden: list[bytes], formulier_settings: bytes
    ) -> bytes:
        """Bouw GetControleVragen request met alle beantwoorde vragen.
        Elk antwoord wordt dubbel genest: field 1(field 1(antwoord_bytes)).
        Na alle antwoorden: field 1(field 2: true) als bevestiging.
        """
        count = len(antwoorden)
        antwoorden_msg = b""
        for antwoord in antwoorden:
            # Dubbel genest: field 1 → field 1 → antwoord data
            antwoorden_msg += encode_field_bytes(1, encode_field_bytes(1, antwoord))
        # Teller: field 1 → {field 2: count}
        antwoorden_msg += encode_field_bytes(1, encode_field_varint(2, count))

        # Inner message: antwoorden + field 2: count + adres_id + formulier + type
        inner = (
            antwoorden_msg
            + encode_field_varint(2, count)
            + encode_field_varint(3, adres_id)
            + encode_field_bytes(4, formulier_settings)
            + encode_field_bytes(5, encode_field_varint(1, 5))
        )

        request = (
            encode_field_string(1, bank_slug)
            + encode_field_bytes(2, inner)
        )
        return request

    # ─── InitialiseerWaarderingVanFormulier ─────────────────

    def _doorloop_wizard(
        self, bank_slug: str, adres_id: int,
        hypotheekbedrag: float, geschatte_waarde: float,
    ) -> tuple[list[bytes], bytes | None] | None:
        """Doorloop de GetControleVragen wizard.
        Returns (antwoorden_full, last_request_inner) of None bij blokkering.
        - antwoorden_full: raw vraag-bytes + field 9 per vraag
        - last_request_inner: de inner bytes van het laatste GetControleVragen request
        """
        formulier_settings = bytes([0x0C, 0x03, 0x06, 0x08, 0x0A, 0x12])
        inner = (
            encode_field_varint(3, adres_id)
            + encode_field_bytes(4, formulier_settings)
            + encode_field_bytes(5, encode_field_varint(1, 5))
        )
        request = encode_field_string(1, bank_slug) + encode_field_bytes(2, inner)

        antwoorden = []       # stripped, voor GetControleVragen
        antwoorden_full = []  # full raw + field 9, voor InitialiseerWaardering
        last_inner = None     # inner bytes van laatste request

        for _ in range(10):
            response = self._grpc_call(
                VALUATION_HOST,
                "calcasa.protocols.online_valuation.OnlineValuationService",
                "GetControleVragen",
                request,
            )
            fields = decode_protobuf(response)
            vragen = []
            raw_vragen = []
            status = None
            for f in fields:
                if f.field_number == 1 and isinstance(f.value, bytes):
                    vraag = self._parse_controle_vraag(f.value)
                    if vraag:
                        vragen.append(vraag)
                        raw_vragen.append(f.value)
                elif f.field_number == 2:
                    status = f.value

            if status == 3 or not vragen:
                return (antwoorden_full, last_inner)

            for vraag, raw_bytes in zip(vragen, raw_vragen):
                antwoord = self._beantwoord_vraag(
                    vraag, raw_bytes,
                    hypotheekbedrag, geschatte_waarde, True, True
                )
                if antwoord is None:
                    return None
                antwoorden.append(antwoord)

                # Full: raw bytes + field 9
                answer_value = self._get_answer_value(vraag, hypotheekbedrag, geschatte_waarde)
                if answer_value is not None:
                    antwoorden_full.append(raw_bytes + encode_field_bytes(9, answer_value))
                else:
                    antwoorden_full.append(raw_bytes)

            request = self._build_controle_vragen_request(
                bank_slug, adres_id, antwoorden, formulier_settings
            )
            # Bewaar de inner bytes voor InitialiseerWaardering
            req_fields = decode_protobuf(request)
            for rf in req_fields:
                if rf.field_number == 2 and isinstance(rf.value, bytes):
                    last_inner = rf.value
                    break

        return None

    def _get_answer_value(self, vraag: dict, hypotheekbedrag: float,
                          geschatte_waarde: float) -> bytes | None:
        """Return de field 9 value bytes voor een vraag."""
        vraag_id = vraag.get("id", "")
        if vraag_id == "hypotheekbedrag":
            return encode_field_double(2, hypotheekbedrag)
        elif vraag_id == "klantwaarde":
            return encode_field_double(2, geschatte_waarde)
        elif vraag_id == "bestaande_bouw":
            return b"\x20\x01"  # field 4 varint = 1
        elif vraag_id == "eigen_bewoning":
            return b"\x20\x01"
        return None

    def initialiseer_waardering(
        self, bank_slug: str, adres_id: int,
        hypotheekbedrag: float, geschatte_waarde: float,
    ) -> dict:
        """
        Roep InitialiseerWaarderingVanFormulier aan.
        Checkt of hypotheekbedrag <= 90% modelwaarde.

        Returns: {
            "success": True/False,
            "blokkering": None of str,
            "waardering_id": str of None,
            "kosten": int of None (centen),
        }
        """
        # Eerst wizard doorlopen om antwoorden op te bouwen
        wizard_result = self._doorloop_wizard(
            bank_slug, adres_id, hypotheekbedrag, geschatte_waarde
        )
        if wizard_result is None:
            return {
                "success": False,
                "blokkering": "Wizard geblokkeerd (bereik of type)",
                "waardering_id": None,
                "kosten": None,
            }

        antwoorden_full, last_inner = wizard_result

        # Extract single-nested antwoorden uit de laatste wizard request
        # (double-nested → single-nested voor InitialiseerWaardering)
        extracted = []
        if last_inner:
            for f in decode_protobuf(last_inner):
                if f.field_number == 1 and isinstance(f.value, bytes):
                    sub = decode_protobuf(f.value)
                    if sub and sub[0].field_number == 1 and isinstance(sub[0].value, bytes):
                        extracted.append(sub[0].value)

        if not extracted:
            return {
                "success": False,
                "blokkering": "Geen antwoorden geextraheerd",
                "waardering_id": None,
                "kosten": None,
            }

        # Bouw InitialiseerWaarderingVanFormulier request
        formulier_settings = bytes([0x0C, 0x03, 0x06, 0x08, 0x0A, 0x12])

        # field 1: waardering config
        config_inner = (
            encode_field_varint(2, 5)  # type = desktop
            + encode_field_varint(6, adres_id)
            + encode_field_string(7, bank_slug)
            + encode_field_string(11, "")  # kenmerk
            + encode_field_string(14, "")  # leeg
        )
        config = (
            encode_field_bytes(2, config_inner)
            + encode_field_bytes(10, formulier_settings)
        )

        # field 2: controle-antwoorden (enkel genest) + count=3
        antwoorden_msg = b""
        for antwoord in extracted:
            antwoorden_msg += encode_field_bytes(1, antwoord)
        antwoorden_msg += encode_field_varint(2, 3)

        request = (
            encode_field_bytes(1, config)
            + encode_field_bytes(2, antwoorden_msg)
        )

        response = self._grpc_call(
            VALUATION_HOST,
            "calcasa.protocols.online_valuation.OnlineValuationService",
            "InitialiseerWaarderingVanFormulier",
            request,
        )

        return self._parse_initialiseer_response(response, hypotheekbedrag)

    def _parse_initialiseer_response(self, data: bytes, hypotheekbedrag: float) -> dict:
        """Parse InitialiseerWaarderingVanFormulier response.

        Response structuur:
        - field 1: UUID (string)
        - field 2: adres info
        - field 3: waardering config (bevat hypotheekbedrag)
        - field 4: 1 = success (betaalscherm)
        - field 9: validatie info
          - field 9.1 = 1: success
          - field 9.1 = 6: LTV-blokkering
          - field 9.2: {field 1: "max_ltv", field 2: 0.90}
          - field 9.3: {field 4: "Ltv 153.06 %  is boven 90.00 %"}
        - field 10: kosten info
        """
        if not data:
            return {"success": False, "blokkering": "Lege response"}

        fields = decode_protobuf(data)
        result = {
            "success": False,
            "blokkering": None,
            "waardering_id": None,
            "kosten": None,
            "ltv_percentage": None,
            "max_ltv": None,
            "hypotheekbedrag_test": hypotheekbedrag,
        }

        for f in fields:
            if f.field_number == 1 and isinstance(f.value, bytes):
                try:
                    text = f.value.decode("utf-8")
                    if "-" in text and len(text) == 36:
                        result["waardering_id"] = text
                except UnicodeDecodeError:
                    pass

            elif f.field_number == 4 and isinstance(f.value, int):
                if f.value == 1:
                    result["success"] = True

            elif f.field_number == 9 and isinstance(f.value, bytes):
                # Validatie info
                sub = decode_protobuf(f.value)
                for sf in sub:
                    if sf.field_number == 1 and isinstance(sf.value, int):
                        if sf.value == 1:
                            result["success"] = True
                        elif sf.value == 6:
                            result["success"] = False
                    elif sf.field_number == 2 and isinstance(sf.value, bytes):
                        # max_ltv info
                        ltv_fields = decode_protobuf(sf.value)
                        for lf in ltv_fields:
                            if lf.field_number == 2 and isinstance(lf.value, float):
                                result["max_ltv"] = lf.value
                    elif sf.field_number == 3 and isinstance(sf.value, bytes):
                        # LTV foutmelding met percentage
                        detail_fields = decode_protobuf(sf.value)
                        for df in detail_fields:
                            if df.field_number == 4 and isinstance(df.value, bytes):
                                msg = df.as_string()
                                result["blokkering"] = msg
                                # Parse LTV percentage uit "Ltv 153.06 %  is boven 90.00 %"
                                import re
                                match = re.search(r"Ltv\s+([\d.]+)\s*%", msg)
                                if match:
                                    result["ltv_percentage"] = float(match.group(1))

            elif f.field_number == 10 and isinstance(f.value, bytes):
                sub = decode_protobuf(f.value)
                for sf in sub:
                    if sf.field_number == 3 and isinstance(sf.value, int):
                        result["kosten"] = sf.value  # in centen

        return result

    # ─── Modelwaarde Bepalen ─────────────────────────────────

    def bepaal_modelwaarde(
        self, bank_slug: str, adres_id: int,
    ) -> dict:
        """
        Bepaal de Calcasa modelwaarde voor een adres.
        Gebruikt een hoog hypotheekbedrag om de LTV-foutmelding te triggeren.
        Uit het LTV-percentage wordt de modelwaarde berekend.

        Kosten: GRATIS (geen taxatie wordt uitgevoerd).

        Returns: {
            "modelwaarde": 588000,
            "ltv_percentage": 153.06,
            "hypotheekbedrag_test": 900000,
            "max_ltv": 0.90,
        }
        """
        # Gebruik een hoog bedrag om altijd de LTV-fout te triggeren
        result = self.initialiseer_waardering(
            bank_slug=bank_slug,
            adres_id=adres_id,
            hypotheekbedrag=1500000,  # maximaal
            geschatte_waarde=25000,   # minimaal
        )

        if not result.get("ltv_percentage"):
            # Geen LTV info — probeer met lager bedrag
            result = self.initialiseer_waardering(
                bank_slug=bank_slug,
                adres_id=adres_id,
                hypotheekbedrag=900000,
                geschatte_waarde=25000,
            )

        ltv = result.get("ltv_percentage")
        hypotheek = result.get("hypotheekbedrag_test", 1500000)

        if ltv and ltv > 0:
            modelwaarde = round(hypotheek / (ltv / 100))
            # Rond af op duizendtallen
            modelwaarde = round(modelwaarde / 1000) * 1000
            return {
                "modelwaarde": modelwaarde,
                "ltv_percentage": ltv,
                "hypotheekbedrag_test": hypotheek,
                "max_ltv": result.get("max_ltv", 0.90),
            }

        return {
            "modelwaarde": None,
            "error": result.get("blokkering", "Kon modelwaarde niet bepalen"),
        }

    # ─── Wallet Info ──────────────────────────────────────────

    def get_wallet_info(self) -> dict:
        """Haal wallet/saldo info op."""
        # Wallet ID is gebaseerd op organisatie-slug
        request = encode_field_string(1, "hondsrug_finance_b_v_.hondsrug_finance")
        response = self._grpc_call(
            BILLING_HOST,
            "calcasa.protocols.wallet.WalletService",
            "GetInfo",
            request,
        )
        fields = decode_protobuf(response)
        info = {}
        for f in fields:
            if f.field_number == 1:
                info["wallet_id"] = f.as_string()
            elif f.field_number == 5:
                info["saldo"] = f.value  # in centen?
            elif f.field_number == 6:
                info["limiet"] = f.value
        return info

    # ─── Debug helpers ────────────────────────────────────────

    def debug_response(self, data: bytes) -> str:
        """Pretty-print een protobuf response voor debugging."""
        return pretty_print_protobuf(data)
