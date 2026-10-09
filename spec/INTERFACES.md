# Wspólne interfejsy

> Wersja 0.2: obowiązują URI i REST /v2, command/query metadata oraz POA/CQRS/ES. Controller tworzy/weryfikuje plan i admission przed skutkiem; samo planowanie nie nadaje uprawnień. Cztery adaptery współdzielą read models.

## Przepływ wywołania

Transport uwierzytelnia klienta, mapuje żądanie do komendy, sprawdza JSON Schema i limity. Dispatcher wybiera dokładny URI z rejestru. Warstwa usług autoryzuje operację i zasoby, ustala spójność, wykonuje transakcję i mapuje wynik. Adapter serializuje jeden rezultat. Tenant i subject nie są edytowalnymi argumentami operacji.

W mutacjach idempotencyKey jest wymagany. `requestId` jest identyfikatorem korelacyjnym, nie kluczem idempotencji. Wynik ma `requestId` bieżącej próby i `replayed`; zapisany rezultat domenowy pozostaje ten sam. Reautoryzuj odtworzenie odpowiedzi, aby klucz nie omijał cofniętego dostępu.

## CLI / shell

Projektowany interfejs:

```bash
datactl operations list --json
datactl operations describe resource.read --json
datactl call resource.read --input @read.json --json
datactl call process.submit --input - --json < submit.json
datactl shell
```

`datactl shell` jest interaktywnym REPL operacji domenowych, nie powłoką systemu operacyjnego. CLI używa gateway i jego autoryzacji. Tokeny pobiera z credential store lub stdin/deskryptora; nie wymaga sekretów jako argumentów widocznych w liście procesów. stdout: jeden obiekt JSON na wywołanie, streaming jawnie JSONL; stderr: diagnostyka. Exit codes: 0 sukces/accepted, 2 walidacja, 3 auth, 4 not found, 5 konflikt, 6 tymczasowo niedostępne, 1 inne. `--wait` odpytuje status z limitem czasu; brak `--wait` nie zmienia statusu procesu na succeeded.

## REST

Wygenerowany OpenAPI 3.1 używa `POST /v2/operations/{operationName}` z konkretnymi ścieżkami na operację. Odczyty przez POST upraszczają zgodność z kontraktami i chronią parametry przed logami URL; nie są automatycznie cache'owane przez HTTP/CDN. Ciało to `{requestId, arguments, idempotencyKey?}`. Dla tego profilu klucz idempotencji w ciele jest kanoniczny; opcjonalny nagłówek musi być z nim identyczny.

200 oznacza ukończenie operacji synchronicznej, 202 przyjęcie `process.submit`; API zwraca processUrn do sprawdzania statusu. REST errors: 400 VALIDATION_ERROR/UNSUPPORTED_OPERATION; 401 UNAUTHENTICATED; 403 FORBIDDEN; 404 NOT_FOUND; 409 REVISION_CONFLICT/IDEMPOTENCY_CONFLICT; 429 LIMIT_EXCEEDED; 503 DEPENDENCY_UNAVAILABLE; 500 INTERNAL_ERROR/INTEGRITY_ERROR. Jednolita koperta `{requestId,error:{code,message,retryable}}`. Nie zwracaj szczegółów ACL cudzych zasobów; wdrożenie może mapować zabroniony odczyt na 404 konsekwentnie we wszystkich adapterach.

Jeśli żądanie nie ma poprawnego requestId lub nie zostało jeszcze zdekodowane, serwer nadaje nowy UUID do odpowiedzi błędu. Odrzuca duplikaty kluczy JSON i niepoprawne wartości liczbowe przed walidacją kontraktu. Reguły semantyczne, których JSON Schema nie wymusza, obejmują poprawne dekodowanie base64, rzeczywisty rozmiar bajtów, zakres PostgreSQL BIGINT i istnienie operacji w rejestrze jobów.

## GraphQL

`contracts/schema.graphql` ma typowane inputy/outputy i osobne Query/Mutation; nie wystawia arbitralnego `JSON` jako substytutu całej domeny. Scalar JSON występuje tylko w zmiennych parametrach zapytań i procesów, które przechodzą drugą walidację w rejestrze handlerów. Scalar `Revision` jest stringiem liczby dziesiętnej, `URN` przechodzi walidację UUID URN, `Base64` ma limit bajtów po dekodowaniu.

Każdy resolver wywołuje wspólny handler. Wiele mutacji w jednym dokumencie GraphQL NIE oznacza jednej transakcji DB. Błędy domenowe trafiają do `errors[].extensions` z code/requestId/retryable; HTTP 200 GraphQL nie musi oznaczać powodzenia operacji. Uwierzytelnianie transportu może zwracać 401/403. Limity: koszt zapytania, głębokość, liczba aliasów/mutacji, wielkość strony i wyników. DataLoader/batching ma zakres pojedynczego requestu i kontekstu uprawnień; nie współdziel go globalnie między tenantami.

## MCP

`contracts/mcp-tools.json` zawiera definicje tools z inputSchema/outputSchema i annotations. Nazwy są stabilne, np. `resource_read`, `resource_publish`, `process_submit`, `process_status`. Serwer może działać przez stdio lokalnie lub uwierzytelniony Streamable HTTP zdalnie; dobór transportu nie zmienia operacji.

Odpowiedzi sukcesu: `structuredContent` zgodne z outputSchema i krótka reprezentacja tekstowa JSON w content dla kompatybilności klientów. Duże wyniki: resource link/ref i osobny autoryzowany odczyt. Błędy wykonania: tool result `isError: true`, stabilny kod w treści; błędne wywołanie protokołu obsługuje SDK MCP. Adnotacja `readOnlyHint` ani `idempotentHint` nie nadaje uprawnień i nie jest dowodem bezpieczeństwa.

Serwer POWINIEN udostępniać `resources/read` dla autoryzowanych URN i katalog kontraktów z paginacją. Pełne listowanie prywatnych zasobów nie jest wymagane. MCP nie zastępuje pętli agentowej: runner LLM decyduje o kolejnych krokach, sprawdza wyniki i respektuje budżety. Domyślny profil protokołu w tym pakiecie jest przypięty do `2025-11-25` jako cel kompatybilności, nie deklaracja najnowszej dostępnej wersji. Negocjację nowszej wersji testuje runtime.

## Paginacja i zapytania

`dataset.query` przyjmuje queryId, schema-validated parameters, limit i opaque cursor. QueryId wskazuje istniejący handler/parametryzowany SQL z dozwolonymi projekcjami. Nie jest tekstem SQL. Cursor wiąże tenant, subject/authz scope, query digest, parametry, porządek i ostatni klucz, jest podpisany oraz wygasa. Porządek zawsze zawiera jednoznaczny tie-breaker. Dla spójnego eksportu materializuj snapshot jako zasób; nie utrzymuj transakcji przez wiele tur rozmowy LLM.
