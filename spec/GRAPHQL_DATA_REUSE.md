# Jedno query GraphQL, różne bazy i konteksty

Tak: resolver GraphQL może połączyć dane z PostgreSQL, SQLite i innych źródeł. GraphQL opisuje API, nie wykonuje automatycznie federowanego SQL ani rozproszonej transakcji. Warstwa danych musi zdefiniować relacje, routing, uprawnienia, świeżość i limity.

## Wybór strategii

| Układ | Rekomendowana ścieżka | Koszt i ograniczenie |
|---|---|---|
| Dane w kilku schematach jednej bazy PG | SQL JOIN/view pod jednym resolverem | Najmniej orkiestracji i jeden snapshot transakcji |
| Kilka baz PostgreSQL, sporadyczny bounded join | Batch resolvers lub kontrolowane postgres_fdw | FDW nie gwarantuje pushdown między różnymi serwerami ani globalnej atomowości |
| PostgreSQL + SQLite | Adaptery source registry, batched key lookup | Jawne freshness i częściowe błędy; brak jednego globalnego snapshotu |
| Powtarzalny ciężki join wielu źródeł | Projekcja integracyjna z ES w jednym PG | Więcej dysku i lag projekcji, mniej RAM gateway i sieci |
| Wiele niezależnych zespołów/API | Federation lub schema stitching | Dodatkowe procesy i planowanie; niekoniecznie potrzebne przy priorytecie RAM |

Pojęcie schema PG i database PG jest istotne: zwykły SQL nie łączy lokalnych tabel z osobnych database przez trzyczęściową nazwę. Można połączyć schematy w jednej bazie, użyć FDW lub aplikacyjnych adapterów. Dla najniższego RAM zacznij od jednego gateway i wspólnych projekcji, nie od osobnego GraphQL subgraph server dla każdej małej bazy.

## Przykład relacji

```graphql
query CustomerOverview($id: ID!) {
  customerOverview(id: $id) {
    id
    displayName
    tickets { id title status }
    sources { sourceId status observedAt version }
    partial
  }
}
```

Customer pochodzi np. z PostgreSQL CRM, a tickets z lokalnego SQLite. Registry mapuje `(tenantId, sourceId, localId)` na wspólny entityId/URN. Sam `id=42` nie jest globalnym kluczem. Resolver pobiera customer i ograniczony zestaw ticketów po indeksowanym customer_id. Przy liście klientów najpierw zbiera najwyżej N kluczy, potem jedno batch query do ticketów; nie wykonuje zapytania na każdy rekord.

Przykładowy executable GraphQL fixture w `conformance/federation.py` używa dwóch rzeczywistych plików SQLite jako dwóch źródeł. Weryfikuje batching, izolację i częściowy błąd. Wymiana jednego adaptera na PG wymaga osobnej integracji; test SQLite nie dowodzi zachowania postgres_fdw lub drivera PostgreSQL.

## Freshness, błędy, kontekst

Źródła zwracają sourceId, observedAt, status i wersję/checkpoint. `partial=true` oznacza, że część źródeł nie odpowiedziała. Pole tickets=null przy awarii nie oznacza tickets=[] („klient nie ma ticketów”). Dla odpowiedzi wymagającej pełnej spójności awaria oznacza błąd całego query. Tryb consistency jest częścią kontraktu.

Autoryzacja jest wykonywana dla każdego źródła i rekordu. Ten sam subjectId może mapować się inaczej w różnych systemach. Registry przechowuje odwołania do secrets, nie hasła w schemacie GraphQL. Klient/LLM wybiera dozwolone sourceId; nie przesyła dowolnego DSN ani ścieżki pliku. Federation nie może omijać RLS przez uprzywilejowane wspólne konto.

Reuse danych zapewniają: wspólne immutable resource URN, katalog encji/aliasów, wersjonowane widoki domenowe i typowane kontrakty. Ten sam read model może obsługiwać UI, CLI, REST, GraphQL i MCP bez pięciu kopii danych. Kontekst LLM jest ograniczoną projekcją z referencjami, freshness i truncation, nie eksportem całej bazy. Cache auth-sensitive projections wiąże tenant, policy revision i parametry.

## Memory-safe execution

Push down filtry i projekcję kolumn do źródła. Limituj źródła jednocześnie, klucze per batch, fan-out i wynik w bajtach. DataLoader cache jest per request, nigdy globalny dla wszystkich tenantów. Dla głębokich relacji użyj jawnej paginacji i kosztu query. Lista ma limit także wtedy, gdy klient nie poda argumentu.

Nie buduj ogromnego hash join w Pythonie. Jeśli bounded lookup nie wystarcza, zarejestruj osobny query handler nad projekcją integracyjną. Duże eksporty wykonuj strumieniowo do zasobu. Złożone dashboardy mogą używać gotowych query IDs; unifikacja interfejsu nie oznacza udostępnienia dowolnego zapytania do wszystkich baz.
