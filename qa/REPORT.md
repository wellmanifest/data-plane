# Raport weryfikacji Data Plane 0.2.0

Data: 2026-10-09. Python 3.12.14, SQLite 3.53.1. Zakres: repo standardu i modele conformance; brak produkcyjnego deployu.

## Wykonane

- **30/30 testów**: kontrakty, audytor SQLite, atomic rollback, idempotencja i konflikt payloadu, dwóch równoległych writerów, crash po target commit przed source ACK, gap/tamper, replay, restart, authority mismatch, historia immutable, ograniczenie batch i izolacja tenantów.
- GraphQL fixture: dwa rzeczywiste pliki SQLite, jeden batched query na źródło, tenant filtering, limit kluczy oraz unavailable odróżnione od pustego wyniku.
- Dziesięć grup kontroli statycznych: 11 kontraktów operacji, JSON Schema, profile POA/CQRS/ES, wygenerowane OpenAPI/MCP, GraphQL SDL, przykłady i parser SQL/PLpgSQL.
- Protobuf `proto/domain_event.proto` skompilowany przez grpcio-tools 1.84.0.
- Przypięty upstream logs: validation przeszła dla jego 2 streamów/18 eventów; nasz audit fixture jest poprawny; 4 runbooki DP przeszły error-adoption.
- Demo: 3 eventy, source i replica zgodnie value=6, replay bez ponowienia skutków.

Pełny output: checks-output.txt i upstream-check.json. Poprzedni wynik statyczny w static-checks.json dotyczy tego samego zestawu reguł; końcowe pełne wykonanie jest zapisane w checks-output.txt.

## Pomiar pamięci modelu

Syntetyczny proces Python + dwa pliki SQLite, **10,000 eventów** typu counter.changed. Append, relay małymi batchami i replay zakończone, wartości źródła i projekcji zgodne.

- Peak RSS procesu według Linux getrusage: **16.62 MiB**.
- Pliki źródła i celu, łącznie z WAL przed zamknięciem: **41.54 MiB**.
- Czas append: 3.88 s; relay: 5.25 s; replay: 1.61 s.
- /proc smaps_rollup nie było dostępne; PSS i próbki bieżącego RSS pozostają niezmierzone. Nie zastąpiono ich wymyślonymi wartościami.

To wynik konkretnego małego modelu, nie benchmark PostgreSQL/Redis/gateway ani dowód stałego zużycia RAM dla dowolnej domeny. Nie obejmuje LLM, noVNC, dużych payloadów lub wielu niezależnych procesów. Plik sqlite-memory.json zachowuje pełne dane i ograniczenia pomiaru. Budżety LOW_RAM.md pozostają kandydatami do weryfikacji na rzeczywistym runtime.

## Nie wykonano

- Live PostgreSQL/Redis, sprawdzenia RLS na serwerze, zdalnego relay SQLite→PostgreSQL i PostgreSQL FDW.
- Docker/Compose ani GitHub Actions: konfiguracje są dołączone; Docker nie jest dostępny w tej sesji.
- Produkcyjnego gateway HTTP/MCP/auth, authority transfer odłączonego writera, snapshot/cold archive runtime ani migracji bazy użytkownika.
- Publikacji GitHub lub wdrożenia.

Model SQLite nie jest substytutem testów PostgreSQL. Dowody conformance nie tworzą uprawnień. Wszystkie przyszłe deklaracje wdrożenia wymagają testów docelowego runtime.
