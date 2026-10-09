# POA, CQRS i Event Sourcing

## Warstwa sterowania

POA oznacza tu Process-Oriented Architecture, zgodnie z logs. Proces ma dokładny URI, opis celu, schemat argumentów/wyniku i efekty. Query `command.plan` tworzy propozycję i planHash. Controller sprawdza uprawnienia, bieżącą wersję streamu, cel i budżet. Command wykonuje przyjęty plan. Agent może robić te kroki autonomicznie w przyznanej polityce; grant nie pochodzi z tekstu LLM.

Plan obejmuje target/stream, operation URI+contract digest, hash argumentów, expectedVersion, authorityEpoch i effects. Command musi sprawdzić zgodność tych pól z planem. Idempotencja jest związana z tenantem, podmiotem, operacją i kluczem; inputHash obejmuje argumenty wraz z preconditions. Ponowne użycie klucza z innym wejściem to konflikt. Nowy plan po konflikcie stanu jest nową intencją/komendą, nie cichą modyfikacją starego retry.

## Magazyny

| Dane | Tabela/rola | Odtwarzalne? |
|---|---|---|
| Fakty domenowe | `domain_events` | Źródło prawdy; historia musi przetrwać |
| Wersja i authority | `stream_heads` | Head można zweryfikować historią; authority jest kontrolą zapisu |
| Kanoniczny audyt logs | `audit_events` | Osobna historia i chain, związana z domeną przez hashe/ID |
| Publikacja do projectorów | `event_outbox` | Stan dostarczania; deduplikacja po eventUrn |
| Bieżący stan domeny | Read models, np. `entity_heads` | Tak, przez replay |
| Postęp projektora | `projection_checkpoints` | Atomowy z read model; wersjonowany |
| Snapshot agregatu | `aggregate_snapshots` | Tak; hash i source head są wymagane |
| Wyniki ponowień komend | `command_receipts` | Trwały zakres idempotencji; nie zastępuje go Redis |

Przykładowe SQL 0.1 resource/entity/process pozostają pokazem struktur zasobów/projekcji. W 0.2 ich bezpośrednie mutowanie przez API jest zabronione: aktualizacja musi wynikać z command/event i odpowiedniego projektora. `examples/postgres/es-schema.sql` dodaje właściwy event store. Referencyjny model Python demonstruje jedną typowaną domenę counter.changed; nie deklaruje implementacji wszystkich handlerów katalogu.

## Atomic append i kolejność

Dla jednego streamu: BEGIN → lock head → porównanie authority+epoch i expectedVersion → reautoryzacja/idempotencja → walidacja schematu/invariants → wygenerowanie zdarzeń z kolejnymi wersjami i chain → zapis → synchroniczna projekcja, jeśli potrzebna → outbox i receipt → COMMIT.

Blokada działa per stream; kilka streamów w jednej transakcji wymaga stałego porządku blokowania. Konflikty biznesowe nie są ślepym retry z nową expectedVersion. Nie trzymać transakcji podczas generacji LLM, sieci ani KVM. Zewnętrzny skutek zaczyna się po durable command acceptance; jego wykonanie i wynik są kolejnymi faktami. Nie ma ogólnej gwarancji exactly-once dla zewnętrznego efektu.

PostgreSQL sequence przydziela numery przed COMMIT. Transakcja A z ID 10 może zakończyć się po B z ID 11. Konsument ustawiający globalny cursor na 11 straci A. Wersja bazowa używa per-stream wersji i outbox z ACK; nie używa BIGSERIAL jako bezpiecznej globalnej pozycji commitów. Globalny porządek wymaga osobnego jawnego mechanizmu i ma koszt synchronizacji.

## Replay, checkpointy i snapshoty

Projector otrzymuje bounded porcję, weryfikuje chain, schemat i ciągłość. Read model plus checkpoint/inbox zatwierdza w jednej transakcji. Crash przed commit nic nie zmienia; crash po commit przed ACK powoduje duplikat, który jest rozpoznany. Sam zapis checkpointu przed read model jest niedozwolony.

Nie istnieje jedna liczba freshness dla niezależnych baz. Odpowiedź podaje wersje per source/stream lub jawnie nazwany spójny snapshot. Write receipt zawiera barierę stream/version/hash. Query czeka do deadline na projekcję co najmniej tej wersji albo jawnie informuje o braku świeżości.

Rebuild uruchom do nowej wersji read model, z osobnym checkpointem. Porównaj wyniki, osiągnij barierę i przełącz alias. Nie kasuj aktywnej projekcji przed weryfikacją. Snapshot co N eventów lub po progu kosztu replay jest ustawieniem do pomiaru, nie obowiązkiem wykonywania co event. Snapshot w pamięci obejmuje najwyżej jeden/bounded zestaw agregatów; reszta pozostaje na dysku.

## Kanoniczne bajty

Profil domenowy `data-plane-canonical-json-v1`: UTF-8, bez BOM/newline wewnątrz rekordu, JSON bez whitespace, klucze sortowane po Unicode code points, wartości Unicode bez normalizacji, brak float, brak duplicate keys, liczby całkowite tylko w bezpiecznym zakresie JSON; długie liczby jako strings. To jawny profil aplikacyjny, nie deklaracja RFC 8785. eventHash = SHA256 kanonicznego obiektu bez pola eventHash. Genesis previousHash to 64 zera. Redis/jsonb/Protobuf nie mogą zmienić bajtów historycznego rekordu.

Protobuf jest typowanym kontraktem transportowym przykładu. `deterministic serialization` Protobuf nie jest tu algorytmem hash-chain. Przenoszony canonical_json ma pozostać identyczny, a odbiorca porównuje reprezentacje przed akceptacją. Nie dodawaj google.protobuf.Struct jako obejścia zamkniętych event payloadów.

## Wzrost danych

ES rośnie przede wszystkim na dysku, nie musi rosnąć w RAM. Minimalny indeks: tenant+stream+version oraz unique event ID; indeksy JSONB/GIN dodawaj pod konkretne zapytania, zwykle na projekcjach. Payloady duże i powtarzalne przenieś do immutable resources. Kompresuj sealed cold segments, zachowaj manifest hashów i zakresów wersji. Snapshot przyspiesza replay, ale sam nie daje prawa do usunięcia całej wcześniejszej historii. Retencję, RPO/RTO i ewentualne usuwanie danych osobowych zaprojektuj przed publikacją niezmiennych payloadów.
