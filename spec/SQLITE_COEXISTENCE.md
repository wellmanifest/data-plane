# SQLite i PostgreSQL równolegle

Tak: można przyjąć POA/CQRS/ES i nowe interfejsy bez natychmiastowego przeniesienia wszystkich danych z SQLite. Najpierw ustal właściciela każdego rodzaju danych/streamu. „Równolegle” oznacza podział odpowiedzialności lub replikę/projekcję, nie dwa niezależne mastery.

## Trzy warianty

| Wariant | Writer | Druga baza | Złożoność |
|---|---|---|---|
| Embedded | Istniejąca aplikacja przez adapter SQLite ES | Brak PostgreSQL lub centralny odbiorca później | Najniższy RAM |
| SQLite → PostgreSQL | SQLite command transaction + ES/outbox | Centralna kopia eventów/projekcje dla GraphQL/MCP | Stopniowa migracja |
| PostgreSQL → SQLite | PostgreSQL command handler | Lokalny read model/archiwum/offline read | Prostszy wspólny write authority |

Można też mieć osobne strumienie należące do różnych baz. Federowane query podaje freshness osobno dla każdego źródła. Wysyłanie lokalnych poleceń offline do centralnego writera jest kolejką komend z możliwością konfliktu; nie oznacza zatwierdzenia domeny przed akceptacją.

## Minimalna refaktoryzacja legacy

1. Wprowadź Repository/UnitOfWork i rozdziel command/query bez zmiany silnika.
2. Zidentyfikuj wszystkie writery: kod aplikacji, crony, CLI, wtyczki i bezpośredni SQL.
3. W tej samej SQLite transakcji zapisuj zdarzenie i aktualizację wymaganej projekcji legacy. ES+outbox umieść w tym samym pliku, aby rollback obejmował całość.
4. Utwórz spójny baseline snapshot i jawny `legacy.snapshot_imported`. Nie fabrykuj historycznych faktów biznesowych. Komendy po baseline muszą emitować kompletne zdarzenia.
5. Dołącz dispatcher interfejsów. Dotychczasowy UI może nadal czytać swoją tabelę-projekcję.
6. Uruchom relay małymi porcjami. W PostgreSQL insert/inbox/projection/checkpoint są jedną transakcją. ACK źródła dopiero po trwałym commicie celu.
7. Porównuj projekcje i spójność; przełączaj odczyty. Authority zapisu przenoś dopiero jako osobny krok.

Jeśli nie można od razu zmienić writerów, triggery mogą transakcyjnie zbierać row changes. Jest to etap CDC/compatibility, a nie pełna semantyka command/domain event. Oznacz go `transitional`; dokumentuj, które zmiany, DDL, deletes i typy obsługuje. Zewnętrzne kopiowanie pliku nie jest poprawnym capture aktywnego SQLite WAL.

## Relay bez rozproszonej transakcji

At-least-once: odczytaj porcję pending → waliduj event → commit na celu → ACK na źródle. Crash przed commit celu: nic nie dostarczono. Crash po commit celu przed ACK: następuje duplikat, który cel rozpoznaje po eventUrn i hashu. Ten sam ID z inną treścią: quarantine/konflikt, nigdy overwrite. Gap w streamie blokuje checkpoint tego streamu; napraw brak albo odtwórz od zaufanego snapshotu.

Nie ma atomowej transakcji między lokalnym SQLite i zdalnym PG. Poprawność daje outbox+inbox+idempotencja i jawna eventual consistency. Buforowanie transportu może być na dysku. Backpressure ma ograniczać RAM, a rosnący backlog musi być widoczny i podlegać limitowi wolnego dysku. Nie usuwaj niepotwierdzonych eventów.

SQLite: foreign_keys=ON, WAL dla lokalnego współdzielenia odczyt/zapis, synchronous=FULL dla wymaganej trwałości, małe cache_size i busy timeout. WAL jest przeznaczony dla procesów na tym samym hoście; nie traktuj pliku na zwykłym filesystemie sieciowym jak wielohostowej bazy. Atomowość ATTACH zależy od konfiguracji; profil bazowy celowo nie opiera capture na transakcji wielu plików w WAL.

## Zmiana authority

Freeze/drain wszystkich writerów streamu → ostatni head H → pełna dostawa do celu i porównanie H → przeniesienie aktywnych kluczy idempotencji/receipts → trwałe odgrodzenie starego writera → authorityEpoch+1 → uruchomienie nowego. Nowe eventy kontynuują wersje i chain, zachowując nowe authority/epoch jako metadane. Tożsamość streamu i eventów pozostaje stała.

Nie da się bezpiecznie przejąć streamu, jeśli jego odłączony writer nadal może lokalnie przyjmować commity. Sam nowy epoch w PG tego nie blokuje. Poczekaj na fence/wygaśnięcie wymuszalnej dzierżawy albo użyj osobnych streamów i jawnej polityki konfliktów. Nie obiecuj uniwersalnego offline multi-master.

Po nowych zapisach w PG powrót wymaga zsynchronizowania SQLite do nowego head i ponownej procedury authority transfer. Cofnięcie DSN gubi dane. Repo zawiera testowy relay SQLite→SQLite ilustrujący protokół; adapter PostgreSQL i rzeczywista aplikacja wymagają własnych testów integracyjnych.
