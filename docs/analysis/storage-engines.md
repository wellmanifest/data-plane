---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "storage-engines",
  "kind": "analysis",
  "version": 1,
  "title": "SQLite, grupowe zatwierdzanie, PostgreSQL i PGlite dla wzorca data-plane",
  "status": "proposed",
  "owner": "wellmanifest/data-plane",
  "scope": "repository",
  "created": "2026-10-13",
  "updated": "2026-10-13",
  "review_after": "2026-10-27",
  "source_revision": "ba461cb6d49610a69c416f4ed8f818a866ff0f8a",
  "affected_repositories": [
    "wellmanifest/data-plane"
  ],
  "evidence": [
    "repo://wellmanifest/data-plane/benchmarks/engines.py",
    "repo://wellmanifest/data-plane/tests/test_postgres_live.py",
    "repo://wellmanifest/data-plane/examples/postgres/es-schema.sql",
    "https://pglite.dev/docs/pglite-socket"
  ]
}
---

# SQLite, grupowe zatwierdzanie, PostgreSQL i PGlite dla wzorca data-plane

<!-- docs:section question -->
## Question

Który silnik powinien przechowywać autorytatywny log zdarzeń i audyt w
profilach data-plane? Rozważane opcje:

- SQLite;
- SQLite z grupowym zatwierdzaniem (group commit);
- natywny PostgreSQL;
- PGlite, czyli PostgreSQL w WASM udostępniany przez `pglite-server`.

Drugie pytanie: czy referencyjny schemat ES dla PostgreSQL działa na żywej bazie.

<!-- docs:section scope -->
## Scope

- **Obciążenie:** ta sama praca transakcyjna co w kernelu data-gateway.
  - Polecenie: receipt, głowa strumienia, zdarzenie (ok. 1 KB), blob 512 B,
    zasób, receipt i rekord audytu z łańcuchem hashy.
  - Zapytanie: zasób z blobem i rekord audytu.
- **Wersje:** PostgreSQL 16 (`postgres:16-alpine`, domyślne `fsync` i
  `synchronous_commit`), PGlite 0.5.9 z `pglite-socket` 0.2.12 (wewnętrznie
  PostgreSQL 18.6), SQLite z `synchronous=FULL`.
- **Poza zakresem:**
  - DuckDB (osobna propozycja: analityka tylko do odczytu na pliku SQLite);
  - replikacja;
  - wielu hostów.

<!-- docs:section method -->
## Method

`benchmarks/engines.py` uruchamia każdą konfigurację (silnik × 1 lub 8
klientów, 200 poleceń i 200 zapytań) w osobnym procesie, w 3 przeplatanych
rundach. Raport podaje mediany. Mierzone są:

- przepustowość;
- p50;
- CPU klienta;
- RSS procesu klienta i szczytowy RSS drzewa procesów serwera (próbkowanie co
  50 ms);
- logiczny rozmiar tabel, przez `dbstat` albo `pg_total_relation_size`.

Synchronizację z dyskiem sprawdzono przez
`strace -f -e trace=fsync,fdatasync,sync_file_range,msync,sync,syncfs`.
Dysk hosta był bardzo obciążony (fsync rzędu 10–20 ms), więc rozstrzygają
proporcje, nie wartości bezwzględne.

Test `tests/test_postgres_live.py` (`make pg-live`) tworzy własną bazę i rolę
aplikacji, stosuje `examples/postgres/es-schema.sql` i sprawdza zachowanie
schematu na PostgreSQL 16.

<!-- docs:section evidence -->
## Evidence

| Silnik | op/s, 1 klient | op/s, 8 klientów | p50 zapisu, 8 klientów | RSS serwera | Bajty/zapis |
|---|---|---|---|---|---|
| SQLite | 8 | 8 | 27,8 ms | 0 (w procesie, łącznie 22–23 MB) | 4731 |
| SQLite, odczyty `NORMAL` | 11 | 42 | 11,9 ms | 0 (22–23 MB) | 4731 |
| SQLite + grupowe zatwierdzanie (okno 2 ms) | 42 | 187 | 26,7 ms | 0 (22–24 MB) | 4731 |
| PostgreSQL 16 | 15 | 15 | 127,6 ms | 134–364 MB | 6185–7004 |
| PGlite 0.5.9 | 111 | 77 (1 z 3 rund całkowicie nieudana) | 96,0 ms | 385–430 MB | 6185–6413 |

Średnia grupa przy 8 klientach wynosiła 7,1 polecenia na COMMIT.

Synchronizacja z dyskiem:

| Przebieg | Wywołania sync |
|---|---|
| SQLite `FULL`, 20 poleceń i 20 zapytań | 59 × `fsync` |
| PGlite przez `pglite-server`, 100 poleceń i 100 zapytań | 0 |

PostgreSQL 16, `make pg-live`, wynik 3/3 OK:

- schemat się stosuje;
- RLS z `FORCE` izoluje tenantów dla roli aplikacji; zapis cudzego wiersza
  kończy się `InsufficientPrivilege`, a bez `app.tenant_id` rola nie widzi
  żadnych wierszy;
- `UPDATE` i `DELETE` historii kończą się `23000`;
- zduplikowana wersja strumienia kończy się `UniqueViolation`;
- strzeżony CAS głowy ze starą wersją zmienia 0 wierszy.

<!-- docs:section facts -->
## Facts

- **PGlite nie synchronizuje zatwierdzeń z dyskiem.** W tej konfiguracji nie
  wykonał żadnego wywołania `fsync` ani `fdatasync`. Jego przewaga przy jednym
  kliencie wynika z braku trwałości, której wymaga profil SQLite data-plane
  (`synchronous=FULL`). Nie spełnia więc wymagań autorytatywnego logu.
- **PGlite multipleksuje klientów na jedną sesję silnika.**
  - Przygotowane zapytania psycopg kolidowały między połączeniami
    (`DuplicatePreparedStatement`), dopóki nie wyłączono `prepare_threshold`.
  - Przy 8 klientach połączenia kończyły się błędami protokołu albo
    „server closed the connection”.
  - `CREATE ROLE` przechodzi, ale `SET ROLE` na nową rolę zwraca błąd, więc RLS
    nie da się w nim sprawdzić rolą bez uprawnień superusera.
  - Zużywa najwięcej pamięci: 385–430 MB.
- **PostgreSQL 16** daje rzeczywistą współbieżność, ale w tym obciążeniu wszyscy
  piszą do jednego łańcucha audytu (`FOR UPDATE` na głowie), więc 8 klientów nie
  zwiększa przepustowości. Kosztuje 134–364 MB RSS i ok. 30–48% więcej miejsca
  niż SQLite.
- **Grupowe zatwierdzanie** to najsilniejsza dźwignia przy wielu klientach:
  23 razy więcej operacji niż SQLite bez grupowania, bez zmiany trwałości
  potwierdzonego polecenia.
- **Wcześniejsza luka zamknięta:** referencyjny schemat ES był dotąd sprawdzany
  tylko statycznie (pglast). Teraz zachowuje się zgodnie z normą na żywym
  PostgreSQL 16.

<!-- docs:section hypotheses -->
## Hypotheses

- Przepustowość PostgreSQL wzrosłaby przy wielu niezależnych łańcuchach audytu,
  np. per tenant albo per strumień. To zmienia semantykę audytu i wymaga
  osobnej decyzji.
- `commit_delay` i `commit_siblings` w PostgreSQL działają podobnie do
  grupowego zatwierdzania, ale nie były tu strojone.
- Wywołanie sync w PGlite mogłoby się pojawić przy innym backendzie systemu
  plików albo innej wersji. Nie sprawdzano tego.

<!-- docs:section limitations -->
## Limitations

- Jeden host z mocno obciążonym dyskiem i CPU; wartości bezwzględne nie
  przenoszą się na inne maszyny.
- PostgreSQL działał w kontenerze z wolumenem Dockera na tym samym dysku.
- Test na żywej bazie dotyczy tylko schematu, bez pełnego runtime'u append,
  outbox ani relay.
- RSS SQLite to cały proces klienta w Pythonie, a RSS serwerów to tylko serwer,
  bez klienta.

<!-- docs:section recommendations -->
## Recommendations

1. **SQLite z grupowym zatwierdzaniem** jako domyślny profil autorytatywny dla
   jednego węzła. Najmniej pamięci i miejsca, a przy współbieżności najwyższa
   przepustowość w tym pomiarze.
2. **PostgreSQL** jako profil współdzielony, gdy wiele usług lub hostów pisze do
   jednej bazy. Testy `make pg-live` uruchamiać na jednorazowym serwerze w CI
   lub w OneDev.
3. **PGlite nie jako magazyn autorytatywny.** Ewentualnie tylko do testów
   składni i dialektu, ze świadomością braku fsync, ról i stabilnej
   współbieżności.
4. Redis i DuckDB dopiero po pomiarze konkretnego modelu odczytu, tym samym
   skryptem.
