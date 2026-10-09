# Status implementacji 0.2.0

## Dostarczone

- Repozytorium standardu z normami, manifestem, profilami i lockiem upstream.
- Jedenaście kontraktów operacji i generator OpenAPI/GraphQL/MCP.
- Działający audytor SQLite oraz model ES: append, CAS, deduplikacja, immutable history, outbox, replay i relay dwóch SQLite.
- Executable GraphQL fixture łączący dwa źródła SQLite; batch lookup, tenant filtering i jawny partial result.
- Schematy SQL PostgreSQL dla ES/audytu/projekcji i przykłady low-RAM.
- Typowany Protobuf domenowego przykładu; checker zgodności audytu i katalogu błędów ze wskazanym logs.
- Makefile, Docker/Compose, GitHub Actions, RAM probe i syntetyczny benchmark.

## Granice

Modele conformance są bibliotekami testowymi, nie serwerem produkcyjnym. Nie mają OAuth, zewnętrznego kontrolera admission, TLS, kompletnych handlerów katalogu, zdalnego relay PG, egzekwowanego fencing między hostami ani uniwersalnego migratora SQLite. Biblioteka GraphQL fixture nie implementuje pełnego query complexity limiter/HTTP server; pokazuje zachowanie ograniczonego zarejestrowanego query. Chronienie dowolnych dokumentów GraphQL pozostaje wymaganiem runtime.

SQL jest wzorcem schema i transakcji. Samo stworzenie tabel nie zapewnia poprawnego append, hashowania, autoryzacji lub atomowych efektów domeny. Snapshoty, authority transfer, cold archive i upstream continuity są określone normatywnie; pełny runtime musi dostarczyć ich implementacje i testy.

CI i Docker są przygotowane do uruchomienia w repo adoptera. Raport qa/REPORT.md jest autorytatywny w sprawie tego, które kontrole wykonano w tej sesji. Nie wykonano publikacji GitHub ani migracji jakiejkolwiek bazy użytkownika.
