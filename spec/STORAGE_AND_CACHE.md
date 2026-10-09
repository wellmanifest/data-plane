# PostgreSQL, Redis i przetwarzanie

> Wersja 0.2: obowiązkowe ES i profile SQLite/PostgreSQL określają STANDARD.md oraz POA_CQRS_ES.md. PostgreSQL jest źródłem prawdy tylko dla streamów, których jest authority. Bieżące tabele domenowe są projekcjami. Redis jest opcjonalny; profil LOW_RAM.md zastępuje wcześniejsze wartości startowe.

## PostgreSQL

Przykład SQL wspiera PostgreSQL 16+ i nie wymaga rozszerzeń. To minimalny rdzeń, który trzeba uzupełnić o model domeny, ACL i migracje. `resource_versions` przechowuje dokładne bajty małych zasobów; duże pliki przenieś do trwałego object store. `entity_heads` jest wskaźnikiem CAS. `process_runs` zapisuje stan procesu. `outbox_events` i `idempotency_records` zapewniają trwałość protokołów, a nie automatycznie poprawność zewnętrznych skutków.

Metadane często filtrowane trzymaj w typowanych kolumnach. JSONB indeksuj tylko pod konkretne operatory. Nie twórz GIN na każdym dokumencie. Indeksy B-tree uwzględniają tenant i kolejność filtrów/sortowania. Dla stanów aktywnych używaj indeksów częściowych. `EXPLAIN (ANALYZE, BUFFERS)` wykonuje zapytanie: mutacje analizuj na bezpiecznej kopii lub przez plan bez ANALYZE. Partycjonowanie wprowadzaj dla zmierzonej potrzeby retencji/skanu, nie na starcie.

Pieniądze/ścisłe wartości: NUMERIC o zadanej skali, nie float. Daty: TIMESTAMPTZ i UTC na interfejsach. BOOLEAN zamiast dowolnego 0/1. Ustal reguły collation i Unicode. Nie obiecuj identycznej semantyki SQLite NOCASE i PostgreSQL ILIKE. Indeksy unikalne sprawdzaj na rzeczywistych danych przed zaostrzeniem reguł.

Na transakcję: uwierzytelniony tenant, `set_config('app.tenant_id', tenant_uuid, true)`, statement_timeout/lock_timeout dobrane do klasy operacji, autoryzacja, SQL z parametrami, commit. `SET LOCAL` i transakcyjne advisory locks są właściwsze niż stan sesji przy PgBouncer transaction pooling. Prepared statements zależą od wersji PgBouncer, konfiguracji i sterownika; sprawdź obsługę protokołową, nie zakładaj że każda forma SQL PREPARE działa tak samo.

Budżet: suma wszystkich pul wszystkich procesów i replik + workery + maintenance < max_connections minus rezerwa. Licz procesy, nie tylko pody. PgBouncer zmniejsza liczbę backendów, ale nie usuwa przeciążenia SQL. Repliki read-only są opcjonalne; `strong`, odczyt po zapisie i kontrola cofniętego ACL idą na primary.

## Idempotencja i outbox

Mutacja wykonuje w jednej transakcji: rezerwację klucza idempotencji → kontrolę hashu → zmianę domeny → wpis outbox → zapis wyniku idempotencji. Unikalny klucz rozstrzyga równoległe próby. Przegrany czeka krótko lub dostaje retryable; nie wykonuje skutku ponownie. Rekord obejmuje tenant, subject, operation, key, argument hash i wynik. Rewizje/duże liczby serializuj jako stringi.

Outbox relay rezerwuje porcję `FOR UPDATE SKIP LOCKED`, nadaje owner/lease_until i zwiększa fencing token, zatwierdza krótką transakcję. Wysyła poza transakcją. ACK robi warunkowo dla owner + token; po wygaśnięciu lease inny worker może przejąć zadanie. Crash po wysłaniu przed ACK powoduje duplikat — odbiorca musi deduplikować eventId. `SKIP LOCKED` jest narzędziem kolejkowym, nie sposobem na spójne ogólne odczyty danych.

Procesy mają podobny claim/heartbeat/lease. Anulowanie jest żądaniem: `cancelRequested=true` nie dowodzi cofnięcia skutków. Worker potwierdza cancelled tylko, kiedy może to zrobić zgodnie z kontraktem. Terminalny succeeded ma utrwalone outputs i dowody weryfikacji. Retry efektów zewnętrznych wymaga ich idempotencji lub uzgodnienia; nie deklaruj exactly-once dla kliknięć GUI czy zewnętrznego HTTP.

## Redis: profil bazowy

Cache tylko niezmiennych treści zasobów. Schemat klucza:

`dp:v1:blob:<HMAC-SHA256(tenant || resourceUrn || contentHash || representationVersion)>`

Klucz HMAC pochodzi z konfiguracji runtime i nie trafia do modelu; serializacja elementów musi być jednoznaczna (np. canonical JSON). Nie umieszczaj sekretów, SQL ani promptów w kluczach. Ten sam klucz nie może reprezentować różnych projekcji lub redakcji. Domyślnie cache przechowuje pełne wewnętrzne bajty i wydaje je dopiero po aktualnej autoryzacji; redagowane reprezentacje wymagają dodatkowego policy/representation digest.

Algorytm odczytu:

1. Sprawdź ACL/tombstone w autorytatywnej warstwie i pobierz oczekiwaną referencję.
2. Sprawdź cache. Zweryfikuj hash/rozmiar; uszkodzoną wartość usuń i potraktuj jak miss.
3. Na miss użyj single-flight w procesie lub krótkiej blokady Redis wyłącznie do ograniczenia stampede. Timeout blokady nie zmienia poprawności.
4. Pobierz wersję z PostgreSQL, porównaj hash, zapisz w cache z TTL + jitter, oddaj wynik.
5. Cofnięcie uprawnień blokuje kolejne wydanie nawet gdy bajty pozostały w cache. Polityka usuwania może dodatkowo nakazać aktywne kasowanie bajtów.

Startowe wartości do pomiaru: cache timeout 30 ms w tej samej sieci, TTL treści 300 s ±20%, maxmemory ustalony względem limitu kontenera z zapasem, allkeys-lfu dla wyłącznie odtwarzalnego cache. To ustawienia próbne, nie uniwersalne SLA. AOF/RDB nie są wymagane dla takiego cache; uruchomienie Redis bez danych ma zachować poprawność. Port Redis i PostgreSQL nie są publiczne.

Ochrona awarii: limit równoległych fallbacków, ograniczenie kosztu zapytań, circuit breaker, load shedding z 503/retryable. Nie pozwól, aby utrata Redis otworzyła nieograniczoną liczbę połączeń do PostgreSQL. Monitoruj p95/p99, hit ratio, evictions, memory, DB pool wait i błędy integralności.

## Opcjonalny cache zmiennego stanu

Wyłączony w bazowym profilu. Sam `DELETE` po zapisie nie wystarcza: stary równoległy odczyt może ponownie wstawić poprzednią wartość. Sam outbox też daje okno niespójności przed dostarczeniem zdarzenia.

Rozszerzenie wymaga generacji scope i atomowego compare-and-set przy fill. Generacja musi zmieniać się przy invalidacji; po eviction nie może wracać do tej samej wartości (problem ABA). Nie można odtworzyć brakującej generacji przez nieaktualnego writera. Odbiorca invalidacji odrzuca starsze rewizje. TTL świeżości licz od chwili autorytatywnego odczytu, nie od opóźnionego zapisu do cache. Ogranicz czas snapshotu/SQL. Określ maksymalny wiek, dopuszczalny lag outbox i fallback po jego przekroczeniu. Odczyt `strong` nadal omija tę warstwę.

Nie cache'uj „brak dostępu”/„nie istnieje” globalnie. Cache list i wyników zapytań musi wiązać tenant, podmiot lub równoważny authz scope, wersję polityki, query/contract digest, parametry, projekcję i rewizję danych. Najpierw udowodnij brak przecieku między tenantami i brak odrodzenia starego stanu; dopiero potem zmierz zysk.

## Operacyjna trwałość

PostgreSQL: backup + archiwizacja WAL/PITR, szyfrowanie połączeń, secret manager, monitoring WAL, autovacuum, dead tuples i replication lag. Okresowo wykonuj pełny restore drill. RPO/RTO ustala właściciel systemu; posiadanie kopii bez próby odtworzenia nie dowodzi spełnienia celu. Audyt powinien zawierać actor, tenant, requestId, URI, hash argumentów, wynik i referencje, z redakcją danych wrażliwych. Retencja i purge dotyczą również backupów, logów i cache.
