# Źródła i pochodzenie

## Rozszerzenie 0.2: POA/CQRS/ES, SQLite i RAM

- [wellmanifest/logs, przypięty commit](https://github.com/wellmanifest/logs/tree/cd9d9558e09b9135ef92712096eb951fd524aa75): odczyt przez Git, kontrakt 0.5.0, Protobuf v0.5, checker, architektura i hourly-diagnostic-storage. Weryfikacja naszych przykładów oraz katalogu błędów wykonana tym checkerem. Stare README nie określa aktualnego zakresu implementacji.
- [PostgreSQL Resource Consumption](https://www.postgresql.org/docs/current/runtime-config-resource.html): shared_buffers, mnożenie work_mem, hash_mem_multiplier i pamięć maintenance. Konkretne wartości low-ram są naszą propozycją do pomiaru.
- [PostgreSQL postgres_fdw](https://www.postgresql.org/docs/current/postgres-fdw.html): odczyt z odrębnych baz, opcje pushdown i zarządzanie zdalnymi transakcjami.
- [SQLite PRAGMA](https://www.sqlite.org/pragma.html): cache_size, mmap_size, temp_store oraz parametry połączeń. Ich ustawienie nie jest limitem całego procesu.
- [SQLite WAL](https://www.sqlite.org/wal.html): współdzielenie na jednym hoście i granice wieloplikowych transakcji.
- [GraphQL Federation](https://graphql.org/learn/federation/): kompozycja API; wybór jednej warstwy resolverów zamiast osobnych subgraph servers w low-RAM jest decyzją projektową tego standardu.

Pomiary w qa/sqlite-memory.json dotyczą wyłącznie syntetycznego modelu Python/SQLite. Nie pochodzą z dokumentacji producentów ani z działającego stosu PostgreSQL/Redis/LLM.

Weryfikacja: 9 października 2026. Poniższe dokumenty są podstawą wybranych faktów technicznych. Architektura Data Plane, reguły DP, kontrakty i wartości startowe limitów są propozycją tego pakietu, nie rekomendacją wydawców źródeł.

| Źródło pierwotne | Zastosowanie |
|---|---|
| [wellmanifest/nl-uri-dsl-llm — przypięty commit](https://github.com/wellmanifest/nl-uri-dsl-llm/tree/2de9cab701466f4928f93e20269057aed7d6a237) | Odczyt przez Git: README, VERSION, spec/SEMANTIC_NL_PLAN.md, profiles/semantic-v1.json, schematy i konwencje standardu |
| [RFC 8141: URN](https://www.rfc-editor.org/info/rfc8141/) | Rozdzielenie nazwy zasobu i lokalizacji |
| [RFC 9562: UUID](https://www.rfc-editor.org/info/rfc9562/) | Standardowa przestrzeń nazw urn:uuid |
| [RFC 8785: JCS](https://www.rfc-editor.org/info/rfc8785/) | Kanoniczna reprezentacja JSON do hashy kontraktów; samo sort_keys nie gwarantuje zgodności |
| [PostgreSQL: Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) | RLS, FORCE RLS, wyjątki dla superuser/BYPASSRLS i właściciela |
| [PostgreSQL: COPY](https://www.postgresql.org/docs/current/sql-copy.html) | Import/eksport danych; wymaga jawnego mapowania i uprawnień |
| [PostgreSQL: Populating a Database](https://www.postgresql.org/docs/current/populate.html) | Import masowy i aktualizacja statystyk |
| [PostgreSQL: SELECT](https://www.postgresql.org/docs/current/sql-select.html) | Blokady wierszy i SKIP LOCKED |
| [PostgreSQL: LIMIT/OFFSET](https://www.postgresql.org/docs/current/queries-limit.html) | Wymóg przewidywalnego porządku i koszt pomijania rekordów |
| [PgBouncer: Features](https://www.pgbouncer.org/features.html) i [FAQ](https://www.pgbouncer.org/faq.html) | Ograniczenia transaction pooling i zależna od konfiguracji obsługa prepared statements |
| [Redis: Cache-aside](https://redis.io/docs/latest/develop/use-cases/cache-aside/) | Model cache z odczytem źródła przy miss i ograniczoną świeżością |
| [Redis: Key eviction](https://redis.io/docs/latest/develop/reference/eviction/) | maxmemory i polityki usuwania kluczy |
| [SQLite: Online Backup API](https://www.sqlite.org/backup.html) | Spójne kopiowanie aktywnej bazy |
| [Python sqlite3](https://docs.python.org/3/library/sqlite3.html) | Connection.backup, połączenie URI read-only i progress handler |
| [SQLite: Quirks](https://www.sqlite.org/quirks.html) i [STRICT tables](https://www.sqlite.org/stricttables.html) | Rzeczywiste typy i wymuszanie ograniczeń podczas migracji |
| [MCP tools, wersja 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) | inputSchema, outputSchema, structuredContent i błędy narzędzi; przypięty cel kompatybilności |
| [GraphQL: Security](https://graphql.org/learn/security/) i [Pagination](https://graphql.org/learn/pagination/) | Kontrola kosztu, limity i paginacja |

Dokumenty oznaczone `current`/`latest` mogą się zmieniać. Repozytorium runtime powinno zapisać dokładne wersje komponentów i wyniki testów kompatybilności. Ten pakiet nie stwierdza, że przypięty target MCP lub minimalna wersja PostgreSQL jest najnowsza.

Schemat w `reference/process-exchange.schema.json` wyodrębniono ze wskazanego commita bez zmian semantycznych; formatowanie pliku jest lokalne. Licencja upstream jest dołączona. Nie skopiowano runtime ani nie przyjęto uprawnień lub statusu governance upstream.
