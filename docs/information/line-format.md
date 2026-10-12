---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "line-format",
  "kind": "information",
  "version": 2,
  "title": "Jednoliniowy format żądań, wyników i logów data-plane.line/v1",
  "status": "proposed",
  "owner": "wellmanifest/data-plane",
  "created": "2026-10-12",
  "updated": "2026-10-12",
  "review_after": "2026-10-26",
  "source_revision": "4c7a67e977b8b13cf152564794b88a827926f087",
  "affected_repositories": [
    "wellmanifest/data-plane"
  ],
  "evidence": [
    "https://github.com/wellmanifest/nl-uri-dsl-llm/blob/2de9cab701466f4928f93e20269057aed7d6a237/README.md",
    "https://github.com/wellmanifest/logs/blob/cd9d9558e09b9135ef92712096eb951fd524aa75/docs/ARCHITECTURE.md",
    "https://www.rfc-editor.org/rfc/rfc3986",
    "https://www.rfc-editor.org/rfc/rfc8141"
  ]
}
---

# Jednoliniowy format żądań, wyników i logów data-plane.line/v1

<!-- docs:section purpose -->
## Purpose

Jeden zapis w jednej linii służy do wywołania operacji i do jej zalogowania,
niezależnie od transportu (shell CLI, REST, gRPC, MCP, strumień logów):

```text
<typ>: <obiekt URI/URN/URL> {<zmienne JSON>}
resource.read: urn:uuid:11111111-1111-4111-8111-111111111111 {"consistency":"strong","requestId":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}
```

Ta sama linia jest wejściem, podstawą `inputHash` i czytelnym rekordem w logu.

<!-- docs:section scope -->
## Scope

Kontrakt `data-plane.line/v1`: gramatyka, postać kanoniczna, klasyfikacja,
powiązanie z katalogiem operacji `/v2` i bezstratne projekcje zdarzeń. Nie zmienia
`contracts/operations.json`, kształtu wejść/wyjść `/v2`, kontraktu
`wellmanifest.logs/event/v1` ani `STANDARD.md`. Linia jest danymi: jej parsowanie
nie nadaje uprawnień; wykonanie przechodzi przez ten sam kernel, autoryzację i
idempotencję co pozostałe transporty (API-030). GraphQL nie jest transportem
linii — pozostaje językiem zapytań nad tym samym katalogiem.

<!-- docs:section evidence -->
## Evidence

Format uogólnia linię hybrydową `uri: scheme://domain/action {...}` z
`wellmanifest/nl-uri-dsl-llm` 1.3.1 (`2de9cab`, pin z `manifest.json`): ta linia jest poprawną linią `v1` typu `uri`.
Implementacja referencyjna: `conformance/line.py`, adapter shell `tools/dp_line.py`,
powiązania `contracts/line-bindings.json`, schemat `schemas/line.schema.json`,
gRPC `proto/line.proto`, przykłady `examples/lines/examples.line`, testy
`tests/test_line.py`.

<!-- docs:section content -->
## Content

**LINE-001 — Gramatyka.** Jedna linia UTF-8 bez BOM, zakończona LF (CRLF tolerowane
przy odczycie), najwyżej 65536 bajtów:

```text
line   = type ": " target [ " " vars ]
type   = segment *( "." segment )        ; segment = [a-z] *[a-z0-9_-], ≤128 znaków
target = absolutny URI RFC 3986 lub URN RFC 8141, ASCII, bez spacji, ≤2048 znaków
vars   = jeden obiekt JSON w jednej linii, głębokość ≤32
```

Dokładnie jedna spacja po dwukropku i przed `{`. Znaki spoza ASCII w obiekcie
kodujemy procentowo. JSON odrzuca duplikaty kluczy, liczby zmiennoprzecinkowe,
NaN i liczby całkowite poza ±(2^53−1); większe wartości to stringi dziesiętne.

**LINE-002 — Postać kanoniczna i hash.** Klucze posortowane, JSON bez zbędnych
białych znaków (`wellmanifest-canonical-json-v1`), pusty `{}` pominięty.
`inputHash` = SHA-256 bajtów kanonicznej linii bez LF. Zapis do logu i podpis
używają postaci kanonicznej; tryb `strict` odrzuca inne bajty.

**LINE-003 — Klasyfikacja.** W tej kolejności: `vars.schema` zadeklarowany w
`events` → projekcja zdarzenia; `uri` → linia nl-uri; `result`/`error` → odpowiedź;
nazwa operacji z katalogu → żądanie; w innym przypadku linia jest odrzucana.

**LINE-004 — Żądanie.** `typ` = nazwa operacji (`resource.read`), `obiekt` = argument
wskazany w `contracts/line-bindings.json` (opcjonalnie w formie `urn:uuid:`) albo URI
operacji, gdy nie ma podmiotu (`resource.publish`, `dataset.query`). `vars` = pola
sterujące (`requestId`, `idempotencyKey`) i pozostałe argumenty na jednym poziomie.
Konwersja jest bezstratna i daje dokładnie wejście `/v2`, walidowane jego
`inputSchema`. Argument nie może zasłaniać pola sterującego.

**LINE-005 — Odpowiedź.** `result: urn:uuid:<requestId> {"replayed":…,"result":…}`.
Błąd: `error: urn:uuid:<requestId> {"code":"DP-…","message":"…","retryable":…}`.
Pola są zamknięte: `code` z katalogu `logs-error-catalog.v1.json` (z runbookiem
`errors/{CODE}.md`), opcjonalnie `retryable` (bool) i `message` (≤512 znaków).
Odpowiedź nie powtarza zmiennych żądania; inne pola są odrzucane.

**LINE-006 — Logi.** Zdarzenie domenowe (`data-plane.domain-event/v1`) i audyt
(`wellmanifest.logs/event/v1`) mają bezstratną projekcję
`<eventType>: <streamUrn|subjectRef> {reszta pól}`; `vars.schema` zachowuje
tożsamość schematu, a `eventHash` się nie zmienia. Projekcja nie zastępuje
kanonicznego JSONL logs ani nie jest wejściem jego checkera. Audyt operacji zapisuje
`inputHash` linii i `subjectRef` = obiekt, nie samą linię: zmienne mogą zawierać
dane prywatne. Zdarzenie bez adresowalnego obiektu nie ma projekcji.

**LINE-007 — Transporty.**

| Transport | Postać |
| --- | --- |
| Shell CLI | argument lub kolejne linie stdin; wynik na stdout; kod 0 sukces, 2 naruszenie kontraktu |
| REST | `POST /v2/line`, `Content-Type: text/plain; charset=utf-8; profile="data-plane.line/v1"`, ciało i odpowiedź po jednej linii |
| gRPC | `LineGateway.Execute(Line)` i strumień `Stream`, `Line.text` bez LF |
| MCP | narzędzie `line.execute` z wejściem `{"line": "…"}` |
| Strumień/plik | jedna linia na rekord, `.line`, LF |

Każdy transport mapuje linię na ten sam handler i zwraca tę samą odpowiedź co
dotychczasowy endpoint JSON. Błąd parsera nie powtarza odrzuconej treści.

<!-- docs:section limitations -->
## Limitations

Repo standardu zawiera parser, konwersje i kontrakt gRPC, nie gateway: REST
`/v2/line`, `LineGateway` i narzędzie MCP nie są uruchomione ani przetestowane na
żywym serwerze.
Profil nie jest przyjęty przez `nl-uri-dsl-llm` ani logs; zgodność dotyczy tylko
kierunku nl-uri → v1. Typ medium REST jest profilem `text/plain`, nie
zarejestrowanym typem IANA.

<!-- docs:section next_actions -->
## Next actions

Adopter gatewaya implementuje `/v2/line`, `LineGateway` i `line.execute` nad
istniejącym kernelem z testem równoważności z endpointami JSON. Ewentualne przeniesienie gramatyki do `wellmanifest/jsonl`
lub `nl-uri-dsl-llm` wymaga osobnej decyzji właścicieli i nowego pinu.
