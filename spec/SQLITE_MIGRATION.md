# Migracja SQLite → PostgreSQL + Redis

> Wersja 0.2: dokument opisuje finalny cutover. Przed nim można wdrażać stopniowe współistnienie według SQLITE_COEXISTENCE.md. Każdy docelowy profil wymaga POA/CQRS/ES, a importowany legacy state ma jawny baseline.

Profil domyślny: kontrolowane okno bez zapisów. Celem jest zachowanie zachowania aplikacji i danych, a następnie optymalizacja. Samo zastąpienie DSN nie jest migracją.

## Etapy i wymagane dowody

| Etap | Praca | Warunek przejścia |
|---|---|---|
| 0. Inwentaryzacja | Znajdź wszystkie pliki SQLite, writery, surowy SQL, ORM, crony, FTS, funkcje SQLite | Mapa konsumentów i właściciel cutover |
| 1. Audyt | Spójny backup, integrity_check, foreign_key_check, rzeczywiste typy, liczności i ograniczenia | Raport anomalii oraz decyzja dla każdej transformacji |
| 2. Abstrakcja | Interfejs repozytoriów i unit of work; backend SQLite zachowuje obecne zachowanie | Istniejące testy nadal przechodzą |
| 3. PostgreSQL | Jawne migracje schema, constraints, indeksy, role/RLS, SQL parametryzowany | Regresja i testy izolacji na rzeczywistym PostgreSQL |
| 4. Próba danych | Import snapshotu przez staging/COPY, walidacja, normalizacja i porównanie | Brak niewyjaśnionych różnic; znany czas importu |
| 5. Cache i interfejsy | Wspólne usługi, adaptery; Redis dopiero po poprawności | Zgodność czterech transportów; poprawny tryb bez Redis |
| 6. Cutover | Zatrzymaj wszystkie writery, finalny snapshot, import, walidacja, przełącz | Trwały checkpoint i uzgodniona decyzja go/no-go |
| 7. Stabilizacja | Monitoruj, zachowaj rollback assets, zdejmuj kompatybilność stopniowo | Retencja i podpisany raport migracji |

## Audytor w pakiecie

```bash
python3 tools/sqlite_audit.py ./app.sqlite --output audit.json
```

Źródło jest otwierane `mode=ro`; Backup API tworzy prywatny tymczasowy snapshot uwzględniający WAL. Nie kopiuj samego pliku `.sqlite` aktywnej bazy w trybie WAL. Audytor raportuje DDL, table_xinfo, indeksy, FK, liczności i histogram `typeof()` każdej kolumny. Dane wierszy nie trafiają do raportu, ale DDL/nazwy i domyślne wartości mogą być poufne — traktuj raport jak metadane projektu.

Operacje pełnego liczenia/typowania i integrity_check mogą być kosztowne. Wymagane jest wolne miejsce na snapshot; narzędzie ma timeout i czyści snapshot po zakończeniu. Jest narzędziem audytu, nie pełnym skanerem semantyki: nie wykrywa wszystkich dat, kolizji collation ani intencji aplikacji. Wirtualne tabele wymagające niedostępnego rozszerzenia są jawnie raportowane jako nieprzebadane i blokują uznanie audytu za kompletny. `--timeout` nie jest twardym OS kill; po jego przekroczeniu przerywane są kolejne operacje SQLite/backup callbacks.

## Mapa typów i semantyki

| SQLite / wzorzec | PostgreSQL / wymagane sprawdzenie |
|---|---|
| INTEGER / rowid / AUTOINCREMENT | BIGINT / identity; zachowaj ID i ustaw sekwencję po imporcie |
| Mieszane typy w jednej kolumnie | Jawna konwersja i tabela odrzuceń; nigdy ciche obcięcie |
| INTEGER 0/1 | BOOLEAN po sprawdzeniu innych wartości i NULL |
| TEXT datetime | TIMESTAMPTZ po ustaleniu strefy i niepoprawnych dat |
| REAL dla kwot | NUMERIC ze skalą; uzgodnij zaokrąglenia i historyczne błędy |
| BLOB | BYTEA lub object store z hashem |
| JSON zapisany jako TEXT | JSONB tylko gdy semantyka dokumentu wystarcza; zachowaj bajty osobno dla podpisów/hash |
| NOCASE / LIKE | Jawne zasady collation/case-folding i test unikalności |
| FTS5 | Osobny projekt wyszukiwania; TSVECTOR nie jest mechanicznym zamiennikiem |
| INSERT OR REPLACE | Ustal semantykę delete+insert; nie zamieniaj ślepo na UPSERT |
| last_insert_rowid(), PRAGMA, datetime() | RETURNING, migracje/configuration i funkcje PostgreSQL |
| FK niewymuszane historycznie | Wykryj sieroty; popraw przed walidacją constraints |

Puste stringi i NULL nie są zamienne. Testuj kolumny PK dopuszczające historycznie NULL, duplikaty, generated columns, triggery, attach databases, FTS oraz limit zmiennych zapytania. SQLite serializuje zapisy inaczej; PostgreSQL ujawnia race conditions maskowane pojedynczym writerem. Testuj lost update, deadlock retry i atomic increment.

## Import i porównanie

1. Przygotuj niezmienny snapshot i jego SHA-256, wersję aplikacji, migracji i raport audytu. Finalny snapshot wykonaj po zatrzymaniu **wszystkich** zapisów, również background workers.
2. Utwórz nowe schema i staging w PostgreSQL. Importuj dane strumieniowo przez driver COPY, w kolejności zależności, z jawnym mapowaniem typów. Nie składaj SQL z wartości wejściowych. Nie przenoś limitów pamięci na LLM.
3. Obsłuż odrzucenia jawnie. Wartości źródłowe, przyczyna i decyzja są kontrolowanym artefaktem migracji. Nie loguj masowo sekretów.
4. Ustaw sekwencje względem największego zachowanego ID; obsłuż pustą tabelę. Przy identity ALWAYS użyj właściwej ścieżki importu/OVERRIDING SYSTEM VALUE. Zweryfikuj następny INSERT po imporcie.
5. Zweryfikuj FK/UNIQUE/CHECK, liczności, zakresy, NULL, sumy kontrolne domeny i reprezentatywne zapytania. Uruchom ANALYZE po masowym imporcie.
6. Dla każdej tabeli ustal jawny porządek klucza i kanoniczną normalizację komórek: NULL marker, typ, UTF-8, daty UTC, dokładne decimal, BLOB jako hash. Haszuj uporządkowane porcje. Surowe JSON dumps lub same COUNT(*) nie dowodzą równoważności. Zapisz mapę świadomych różnic transformacji.
7. Jeśli tabela nie ma stabilnego klucza, zaprojektuj deterministyczny sposób porównania multizbiorów z licznością duplikatów. Nie używaj XOR hashy, które mogą gubić parzyste duplikaty.

ID zachowaj, jeśli to możliwe. Publiczne URN można dodać przez tabelę aliasów `(sourceSystem, table, legacyId) → urn`, z trwałą unikalnością. UUIDv5 wymaga przypiętej przestrzeni nazw i jednoznacznej serializacji kluczy złożonych. Nie zmieniaj niejawnie FK i linków zapisanych w dokumentach.

## Cutover i rollback

Przed przełączeniem wykonaj próbę na kopii, zmierz czas i przyjmij limit. Zatrzymaj przyjmowanie mutacji, opróżnij/utrwal kolejki, zatrzymaj writery SQLite, zrób finalny snapshot, import i porównanie. Przełącz konfigurację wszystkich konsumentów, uruchom smoke tests odczytu i kontrolowanej mutacji, dopiero potem otwórz ruch.

**Granica rollback:** przed pierwszym nowym zapisem w PostgreSQL można wrócić do niezmienionego SQLite. Po pierwszym nowym zapisie cofnięcie DSN grozi utratą danych. Wtedy zatrzymaj zapisy i odtwórz/uzgodnij zmiany odwrotnie według przygotowanej procedury lub napraw PostgreSQL do przodu. Nie ma „automatycznego bezstratnego rollback” bez trwałego dziennika i odwracalnych transformacji.

Nie usuwać starej bazy i backupów w tym samym wdrożeniu. Nie usuwać kolumn kompatybilności przed zakończeniem okna wycofania. Zero downtime wymaga odrębnej analizy CDC/change log; bazowy standard nie deklaruje gotowego uniwersalnego CDC dla SQLite.
