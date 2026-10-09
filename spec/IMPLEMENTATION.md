# Wdrożenie i kryteria odbioru

> Wersja 0.2: obowiązuje kolejność adopcji ES, współistnienie SQLite oraz domyślny low-ram z Redis wyłączonym. Wcześniejszą tabelę runtime uzupełniają POA_CQRS_ES.md, SQLITE_COEXISTENCE.md i LOW_RAM.md.

## Kolejność dostarczenia

| Iteracja | Zakres | Gotowe, gdy |
|---|---|---|
| A | Audyt SQLite, ADR, kontrakty, model tożsamości | Są dowody i decyzje transformacji |
| B | PostgreSQL, repozytoria, role/RLS, backup | Regresja i restore drill przechodzą |
| C | Handlery resource/entity/process, idempotencja/outbox | Równoległe retry nie powiela skutków DB |
| D | REST + CLI, następnie MCP i GraphQL | Ten sam test domenowy przechodzi przez cztery adaptery |
| E | Redis immutable cache, metryki, limity | Awaria Redis degraduje wydajność, zachowuje poprawność |
| F | Próba migracji, benchmark, cutover | Wszystkie bramki migracji spełnione |

Rozdziel repo standardu i runtime; przykładowa implementacja może mieć `domain/`, `application/`, `adapters/{cli,rest,graphql,mcp}`, `storage/{postgres,redis}`, `workers/`, `migrations/`, `tests/`. Użyj jednego stosu językowego zgodnego z istniejącą aplikacją. Python jest praktycznym wyborem, jeśli kod już korzysta z sqlite3/Python; nie ma powodu przepisywać sprawnej aplikacji na inny język tylko dla MCP.

Sam PostgREST, silnik GraphQL lub generyczny PostgreSQL MCP nie zapewnia pełnego kontraktu procesów, URI/URN, idempotencji i wspólnego audytu. Można ich używać jako adapterów po sprawdzeniu, że nie omijają tych reguł. Do LLM udostępnij ograniczony katalog zadań, nie bezpośrednią rolę administratora PostgreSQL.

## Profil eksploatacyjny

Początkowo jedna baza PostgreSQL, jeden Redis cache, gateway i worker. Kontenery lub VM są wymienne, jeśli zachowasz trwałe wolumeny, networking i secrets. NoVNC pozostaje podglądem osobnego środowiska wykonawczego; proces w tym standardzie może trwale opisywać zadanie agenta sterującego desktopem, ale baza nie zastępuje sterownika GUI.

Dla wielu aplikacji/datasetów rozpocznij od wspólnego klastra i jawnych granic domen/tenantów. Oddzielna baza na aplikację ułatwia odrębne migracje i lifecycle, ale zwiększa liczbę pul, backupów i zadań administracyjnych. Wspólne tabele z tenant_id wymagają testów RLS i indeksów tenant-aware. Oddzielna baza nie izoluje CPU/IO wspólnego klastra; silna izolacja obciążenia może wymagać osobnego klastra. Wybór zapisuje ADR. Provisioning fizycznych baz, ról i limitów jest osobnym control plane; zwykły agent danych nie tworzy arbitralnie baz przez SQL. Jeżeli ma robić to autonomicznie, dodaj wąską operację administracyjną z rejestrem dozwolonych parametrów i limitami zasobów.

Przypnij dokładne wersje obrazów/dependencies i sprawdź licencje w implementacji. Przykład SQL targetuje PostgreSQL 16+, nie twierdzi, że 16 jest najnowszą wersją. Plik Redis jest jedynie fragmentem profilu cache, nie kompletnym serwerem z auth/TLS. Nie publikuj portów 5432/6379 do Internetu. Zdalny gateway uwierzytelnia użytkowników/usługi; transport MCP nie jest sam w sobie modelem tożsamości.

## Plan testów runtime

| Scenariusz | Oczekiwany rezultat |
|---|---|
| Podmiot A odczytuje URN tenantu B, także z cache | Brak danych i brak ujawnienia istnienia według przyjętej polityki |
| Cofnięcie ACL po nagrzaniu cache | Kolejny autoryzowany odczyt respektuje cofnięcie |
| 20 równoległych mutacji z tym samym idempotencyKey | Jedna mutacja DB, identyczny rezultat domenowy |
| Ten sam klucz, inne argumenty | Jawny konflikt |
| 20 aktualizacji tego samego expectedRevision | Jedna wygrywa; pozostałe conflict |
| Crash worker po send przed ACK | Duplikat zdarzenia nie powiela skutku u idempotentnego odbiorcy |
| Wygaśnięcie lease i późny ACK starego workera | Odrzucenie starego fencing tokenu |
| Redis timeout/flush/eviction | Poprawne dane; bounded fallback i brak lawiny połączeń |
| GraphQL wiele aliasów / MCP nadmierny limit | Walidacja/limit przed kosztownym zapytaniem |
| Cursor innego tenantu, query lub parametrów | Odrzucenie |
| Restart wszystkich usług | Procesy, outbox, idempotencja i dane zachowane w PostgreSQL |
| Przejście przez wszystkie adaptery | Ta sama autoryzacja, rezultat, konflikt i semantyka błędów |

## Benchmark bez wymyślonych wyników

Wypełnij `examples/benchmark-plan.json` rzeczywistymi wartościami. Wartości docelowe ustala się przed testem względem potrzeb aplikacji. Mierz: throughput, p50/p95/p99, błędy, pool wait, CPU/RAM/IO, WAL, outbox lag, cache hit/evictions, rozmiar odpowiedzi, liczbę wywołań i tokenów LLM na zakończone zadanie. Opóźnienie modelu raportuj oddzielnie od gateway/SQL.

Workload obejmuje hot keys i równomierny rozkład, krótkie i długie procesy, listy z filtrem, paginację, mutacje, burst i sustained load. Ustal seed, rozmiar datasetu, współbieżność, fazę warm-up i czas pomiaru. Używaj danych syntetycznych odpowiadających rozkładowi produkcji. Porównuj: SQLite baseline, PostgreSQL bez cache, Redis cold/warm, Redis down. Nie uznawaj poprawy pojedynczego SELECT za poprawę całego procesu LLM.

## Czego pakiet nie wdraża

Brak działającego gateway, resolvera ACL, OAuth, drivera KVM, workerów domenowych, reverse replication i produkcyjnego migratora. Wymaga to kodu docelowej aplikacji i dostępu do środowiska. Dołączone testy sprawdzają kontrakty, audytor i spójność przykładów; nie zastępują testów opisanych powyżej.
