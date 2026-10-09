# Memory-first: profil low-ram-v1

Cel: ograniczyć stały koszt infrastruktury i szczyt RAM pojedynczego zadania. Throughput może być niższy. Podane parametry to punkt startu testów; nie są wynikiem benchmarku ani gwarancją, że aplikacja zmieści się w określonej pamięci.

## Kolejność oszczędzania

1. Zostaw SQLite dla małych lokalnych domen, jeśli centralny write store nie jest potrzebny. Wspólny protokół POA/CQRS/ES działa z oboma silnikami.
2. Nie uruchamiaj Redis domyślnie. SQLite/PG i cache stron OS już używają RAM; dodatkowy cache może duplikować te same dane.
3. Jeden proces gateway obsługuje REST, GraphQL i MCP HTTP oraz wewnętrzny dispatcher. CLI jest cienkim klientem; nie uruchamia nowego backendu DB na każde polecenie. Projector może być jednym zadaniem w tym samym procesie, jeśli izolacja nie wymaga osobnego workera.
4. Ogranicz aktywne zapytania i pule. Wiele procesów aplikacji mnoży pule, cache schematów i DataLoadery.
5. Małe strony i porcje ograniczaj zarówno liczbą rekordów, jak bajtami. Jeden wielki rekord może przekroczyć budżet nawet przy limit=1.
6. Przenieś filtry, agregacje i ciężkie joins do indeksowanej projekcji SQL. Nie buduj wielkich list/hash-map w resolverze.

## Profil próbny PostgreSQL

| Parametr | Wartość startowa | Znaczenie |
|---|---:|---|
| shared_buffers | 128 MiB | Wspólny cache; nie mnożyć przez backendy |
| wal_buffers | 8 MiB | Bufor WAL |
| work_mem | 2 MiB | Na operację sort/hash, nie na cały request |
| hash_mem_multiplier | 1.0 | Ograniczenie mnożnika dla hash operations |
| maintenance_work_mem | 32 MiB | Maintenance; w razie potrzeby zwiększ tylko dla kontrolowanej operacji |
| autovacuum_work_mem | 16 MiB | Na worker; nie wyłączaj autovacuum |
| autovacuum_max_workers | 1 | Początek testów dla małego workloadu; obserwuj bloat/lag |
| max_connections | 20 | Cały serwer; aplikacja używa dużo mniej |
| max_parallel_workers_per_gather | 0 | Brak mnożenia pamięci query przez parallel workers |
| jit | off | Mniejszy koszt krótkich zapytań |
| effective_cache_size | 512 MiB | Wskazówka planera, nie alokacja RAM |

Pula gateway: max 4; projector: max 1 (lub współdzielona pula z wydzielonym limitem); admin/backup mają rezerwę. Przy wielu tenantach/bazach limit musi być globalny, a nie 4 na każdą z setek baz. PgBouncer jest opcją, gdy połączeń jest faktycznie dużo; sam jest kolejnym procesem.

Przybliżenie kosztu sort/hash: aktywne zapytania × jednoczesne memory nodes planu × work_mem × odpowiedni hash multiplier × wykonujące procesy. Nie jest to ścisła górna granica całego query: są też executor, wyniki, driver, ORM i inne struktury. Mierz plany reprezentatywnych zapytań. Więcej spill do dysku jest akceptowalnym kompromisem, jeśli czas zadania nadal spełnia wymagania.

## SQLite i Redis

SQLite: początkowo 1–2 otwarte połączenia na proces, `cache_size=-2048` (około 2 MiB sugerowanego page cache na bazę), `mmap_size=0`, `temp_store=FILE`, streaming cursor zamiast fetchall. LRU otwartych plików: maksymalnie 2 aktywne źródła w profilu demo. W praktyce cache_size nie jest twardym limitem całego SQLite/process. Setki podłączonych plików × osobne cache sumują się. Nie używaj temp_store=MEMORY dla dużych joins/importów.

Redis opcjonalnie `maxmemory 32mb`, `allkeys-lfu`, bez trwałości dla wyłącznie odtwarzalnego cache. Cały proces zużyje więcej przez allocator, połączenia i bufory; maxmemory nie jest limitem RSS. Początkowy limit kontenera 128 MiB wymaga testu pod rzeczywistym workloadem. Nie twórz drugiej kolejki trwałych zadań w Redis. Wyłączenie Redis zachowuje poprawność.

## Limity runtime i ES

Startowe limity: strona 25 (max 100 w low-ram), odpowiedź 32 KiB, batch replay/relay 64 eventy i 256 KiB, 2 jednoczesne źródła GraphQL, 1 projector. Envelope pojedynczego eventu do 16 KiB; większa treść jako immutable resource. Deduplikacja/inbox i registry mają storage na dysku, nie nieskończony set w pamięci. Cache kontraktów ograniczony LRU. Rozszerzenie profilu wymaga nowego budżetu, a nie cichego ignorowania limitu.

Replay czyta porcję, redukuje jeden/bounded zbiór agregatów, zatwierdza checkpoint i oddaje pamięć. Nie odtwarzaj wszystkich agregatów do RAM na startup. Duże projekcje przechowuj w indeksowanych tabelach. Snapshot skraca odczyt historii; kompresja sealed segments ogranicza dysk/IO, ale jej bufor i dekompresja też wymagają limitu.

## Jak mierzyć

Użyj `tools/memory_probe.py --pid PID --cgroup /sys/fs/cgroup/...` przed obciążeniem i w jego trakcie. Narzędzie odczytuje Linux smaps_rollup (RSS/PSS) oraz cgroup v2 memory.current/peak/stat; nie uruchamia testu i nie mierzy automatycznie całego drzewa procesów. Cgroup musi obejmować dokładnie badany zakres. Nie sumuj RSS postgres backendów bez uwzględnienia wspólnych stron. PSS jest proporcjonalne, a memory.current uwzględnia także pamięć przypisaną cgroup, np. cache plików.

Scenariusze: idle po startup, cold/warm query, łączenie źródeł, replay 1M małych eventów porcjami, reconnect/awaria źródła, slow client, Redis off/on. Raportuj peak, ustabilizowany idle, cgroup OOM/events i rozmiar zbioru; nie tylko Python tracemalloc, który nie obejmuje całego native/DB memory.

Na hoście 8 GB z Ollama/noVNC budżet modeli i pulpitów rezerwuje się osobno. Nie zakładaj, że całe 8 GB należy do bazy. Kandydat do rozpoczęcia testów to osobny budżet usług danych rzędu 0,75–1 GiB bez modelu i pulpitu, ale rzeczywisty limit ustala pomiar. Duży lokalny model może wymagać pozostania przy profilu SQLite lub wyniesienia PostgreSQL na inny host.
