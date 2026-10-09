# Adopcja wellmanifest/logs

Źródło: `upstream.lock.json`, logs 0.5.0. Jego README jest starsze od kontraktów; `docs/ARCHITECTURE.md`, `docs/information/hourly-diagnostic-storage.md`, kontrakt v0.5 i checker definiują faktyczny analizowany zakres.

## Podział danych

`data-plane.domain-event/v1` przechowuje typowany fakt pozwalający odtworzyć domenę. `wellmanifest.logs/event/v1` zapisuje ograniczony audyt: identyfikatory, statusy, hashe, evidence i wybrane diagnostic/continuity. Hash wejścia bez jego znaczenia lub dostępnego zasobu nie odtworzy salda, dokumentu lub zadania. Surowe logi aplikacji, obserwacje diagnostyczne i recovery transcripts mają osobne prywatne kontrakty.

Wspólny PostgreSQL może przechowywać te klasy w osobnych schematach/tabelach i rolach. Nie trzeba osobnego procesu DB per klasę. SQLite może lokalnie przechowywać te same kontrakty. Canonical bytes są przechowywane obok małych indeksowanych kolumn; JSONB jest opcjonalną pochodną do query, nie źródłem oryginalnego hashu.

## Mapowanie domena → audyt

| Pole logs | Źródło i reguła |
|---|---|
| eventId | Osobna stabilna tożsamość audit event, np. event:data-…; nie zmieniaj przy retry |
| stream / sequence / previousHash | Osobny chain audit streamu; nie kopiuj seq domenowego streamu |
| correlationId / causationId | Zachowaj rzeczywiste powiązanie; causation wskazuje poprzedni audit event, gdy wymaga tego continuity |
| producer / source | Kto działał oraz jaki subsystem wyemitował; odrębne pola |
| mode / outcome / subjectState | PLAN lub APPLY, wynik operacji oraz stan obiektu; nie utożsamiaj |
| subjectRef | Dopuszczalny URN obiektu/zdarzenia; sam nie nadaje dostępu |
| inputHash | Hash rzeczywistego kanonicznego wejścia komendy; nie hash zredagowanej parafrazy |
| evidence | Istniejące pliki względem korzenia publikacji z dokładnymi hashami; nie wstawiaj URN w pole path |
| receiptRef | Rzeczywisty receipt:// albo null; nie wymyślaj potwierdzenia |
| diagnostic / continuity | Wyłącznie warianty dopuszczone przypiętym kontraktem |

Canonical audit exporter używa dokładnego algorytmu upstream: wyklucza eventHash podczas liczenia SHA-256, odrzuca float i zapisuje canonical JSONL z pojedynczym LF. Referencyjny checker waliduje też causation i powiązania między continuity events; samo JSON Schema tego nie zastępuje.

Transactional outbox zapisuje zamiar audytu razem ze zdarzeniem domenowym. Exporter nadaje uporządkowanie w swoim audit streamie i deduplikuje po tożsamości zamiaru. Crash po zapisie do bazy audytu przed ACK nie tworzy nowego audit event. JSONL powstaje z zatwierdzonych bajtów; marker eksportu/checkpoint jest trwały. Przy awarii pozostaje jawny lag, nie fałszywe potwierdzenie publikacji.

## JSONL, rotacja i prywatność

Nie publikuj całego prywatnego event store w Git. Publikuj zatwierdzone, ograniczone audit streams i odpowiednie evidence. Sekwencja kanonicznego streamu nie resetuje się co godzinę. Godzinne pliki diagnostyczne są inną reprezentacją. Jeśli eksport ma być tylko wycinkiem, dołącz kontrakt segmentu i zaufany predecessor/manifest; nie podawaj go pełnemu checkerowi jako stream zaczynający się od 1. Usunięcie pola/wiersza zmienia treść i hash — wymaga osobnej deklarowanej projekcji.

## Conformance i zależność

Repo nie redystrybuuje kodu/proto upstream. `make upstream-check` pobiera przypięty commit do ignorowanego build/upstream albo używa WELLLOGS_ROOT. Sprawdza dokładne hashe plików, uruchamia upstream validation i waliduje nasze audit fixtures jego funkcją validate_event. Przykład audit w tym repo ma schema logs bez dodatkowych pól. Udane testy próbki nie oznaczają, że każdy runtime wdrożył capture, authority i publikację.

Przy pełnym runtime dodaj własny namespace, np. DP, oraz adopter-error-catalog z contractSha256 i runbookami sprawdzanymi przez upstream error-adoption. Nie rezerwuj namespace LOGS dla błędów produktu. Katalog DP w tym repo jest dodatkowo sprawdzany przez upstream error-adoption; wynik dotyczy dokumentów i kontraktu, nie uprawnień do wykonania remediacji.
