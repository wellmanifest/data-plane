# Data Plane 0.2.0 — POA/CQRS/ES

Status: proposal. Docelowe HOME: `wellmanifest/data-plane`. MUSI i NIE WOLNO oznaczają wymagania; POWINIEN — zalecenie z jawnym odstępstwem. Reguły 0.2 zastępują 0.1 w nowo przyjmowanych wdrożeniach.

## Obowiązkowy model

**DP-001 — POA.** Każde wdrożenie MUSI mieć dokładne URI procesów, typowane wejścia/wyjścia, efekty i granice uprawnień. LLM proponuje plan. Zaufany controller wiąże plan z podmiotem, celem, wersją stanu i polityką. Autonomia korzysta z wcześniej przyznanego zakresu; nie wymaga ręcznej obsługi każdego kroku. Plan, digest i URN nie są grantem.

**DP-002 — CQRS.** Operacje są jawnie command lub query. Queries nie zmieniają domeny. Commands sprawdzają invariants i expectedVersion, następnie emitują zdarzenia. CLI, REST, GraphQL i MCP nie duplikują logiki domenowej.

**DP-003 — ES.** Trwałe przejścia stanu zarządzanej domeny MUSZĄ wynikać ze zdarzeń. Projekcje są odtwarzalne. Deduplikacja, leases i cursory są mutowalnymi metadanymi protokołu, nie drugim źródłem prawdy domeny. Snapshot jest pochodną historii albo jawnym baseline importu legacy z niedostępną wcześniejszą historią.

**DP-004 — Authority per stream.** Każdy stream ma jednego writera, authorityId i authorityEpoch. Profil wskazuje PostgreSQL albo SQLite jako jego autorytatywny magazyn. Redis nie jest źródłem prawdy. Dwie bazy mogą współistnieć, lecz niezależny zapis tego samego streamu do obu jest zabroniony. Nieobjęci capture writery oznaczają status transitional, nie conformant.

## Event store

**ES-010 — Envelope.** Event zawiera eventUrn, tenantId, streamUrn, streamVersion, eventType, schemaVersion, processUri, commandId, correlationId, causationUrn, occurredAt, authorityId/epoch, inputHash, previousHash, eventHash i typowane data. Rewizje są decimal-string na publicznym interfejsie. URI operacji, URN wykonania i URN wersji danych mają różne role.

**ES-011 — Typowanie i zasoby.** Każdy eventType ma zamknięty wersjonowany schema payloadu. Duże treści są zasobami URN + sha256 + mediaType + byteLength. Prywatny payload wymaga ACL i retencji. Prompt, token i raw output nie trafiają do publicznego audytu.

**ES-012 — Atomic append.** Jedna transakcja obejmuje CAS/blokadę head, kontrolę authorityEpoch/expectedVersion, idempotencję, append batchu, wymagane synchroniczne projekcje, trwałe zadanie dalszej projekcji i wynik komendy. Historii nie wolno edytować; korekta jest nowym eventem. Retry po utracie odpowiedzi używa tego samego klucza.

**ES-013 — Kolejność.** StreamVersion rośnie ciągle od 1; chain nie resetuje się przy rotacji/migracji. Timestamp i BIGSERIAL nie dowodzą kolejności commitów. Checkpoint MAX(id) może pominąć później zatwierdzony niższy ID. Użyj checkpointów per stream, delivery/claim albo jawnie uporządkowanego logu transportu.

**ES-014 — Projector.** Zmiana read model i inbox/checkpoint są atomowe w bazie projekcji. Duplikat nie powiela zmiany. Ten sam eventUrn z innymi bajtami jest błędem. Gap lub inny previousHash zatrzymuje stream. Checkpoint wiąże tenant, stream, source authority, seq/hash i wersję projektora.

**ES-015 — Replay.** Replay jest porcjowany i nie wykonuje skutków zewnętrznych: nie klika GUI ani nie wysyła ponownie wiadomości. Upcaster jest czysty i wersjonowany. Snapshot zawiera source head, wersję projektora i hash; zły snapshot wymaga odtworzenia od wcześniejszego poprawnego punktu.

**ES-016 — Integralność i retencja.** Hash-chain wykrywa zmianę względem zaufanego checkpointu, ale sam nie uwierzytelnia autora ani całego logu. Retencja zachowuje zakotwiczone manifesty segmentów i restore. Hot history można archiwizować po weryfikacji kompletnego cold archive; wymaganych faktów nie usuwa TTL cache.

## Wellmanifest logs

**LOG-020 — Oddzielne kontrakty.** `wellmanifest.logs/event/v1` to audyt. Domenowe ES używa `data-plane.domain-event/v1`. Nie wolno dopisać payload do logs pod starą nazwą schematu. Hash wejścia nie wystarcza do odtworzenia stanu aplikacji.

**LOG-021 — Pin i canonicalization.** Adopcja wskazuje commit i SHA kontraktu/proto/checkera logs 0.5.0. Logs używa `wellmanifest-canonical-json-v1` bez float, nie RFC 8785. Nowa serializacja nie może zmieniać historycznych hashy.

**LOG-022 — Baza i JSONL.** Canonical audit bytes oraz indeksowane metadane mogą być w PostgreSQL/SQLite. Repo JSONL to kontrolowany eksport zachowujący chain. JSONB nie służy do odtwarzania oryginalnych bajtów. Redakcja lub selekcja części eventów wymaga jawnej projekcji/nowego streamu; nie udaje pełnej historii.

**LOG-023 — Klasy danych.** Audyt, diagnostic observations, raw logs, recovery sessions i domain ES pozostają oddzielne. Zachowaj PLAN/APPLY, producer/source, subjectState/outcome, inputHash i causation/continuity. Błędy i runbooki mają namespace adoptera. Braki pokrycia źródeł, freshness i truncation są jawne.

## Interfejsy i dane

**API-030 — Jeden kernel.** Adaptery współdzielą kontrakty, autoryzację i idempotencję. 202/submit oznacza przyjęcie, nie ukończenie. GraphQL Mutation nie zapewnia transakcji całego dokumentu ani kilku baz. MCP annotations nie nadają uprawnień.

**API-031 — Spójność.** Wynik wskazuje źródła i wersje projekcji. Read-your-writes wymaga bariery streamUrn/version/eventHash albo synchronicznej projekcji. Niespełniona bariera do deadline oznacza stale/unavailable. Niezależne bazy nie tworzą automatycznie globalnego snapshotu.

**API-032 — Federacja.** Każde źródło ma sourceId, adapter, tenant/authz mapping, capabilities i freshness. GraphQL łączy wyniki przez jawne klucze/URN i bounded batch joins. Ciężkie powtarzalne joins przenosi się do projekcji integracyjnej. Nie pobieraj całych tabel do gateway.

**API-033 — Bounded queries.** Obowiązują limity wierszy, bajtów, fan-out, deadline i projekcja pól. Cursor wiąże źródła, filtry, tenant/authz scope i pozycję. DataLoader działa per request i ma limit kluczy. Duży wynik jest strumieniem lub zasobem URN.

## RAM i izolacja

**MEM-040 — Memory first.** Low-ram jest profilem domyślnym, Redis opcjonalny i początkowo wyłączony. Jeden gateway może obsłużyć wszystkie adaptery. Minimalne pule, bounded queues i jeden projector mają pierwszeństwo przed wzrostem równoległości.

**MEM-041 — Limity.** Ogranicz procesy, aktywne zapytania, połączenia, handles SQLite, batch rows/bytes, wyniki, cache i payloady. work_mem jest budżetem operacji planu, mnożonym przez współbieżność/operatorów/workerów, nie limitem całego PG. Redis maxmemory nie ogranicza całego RSS. Konfiguracja nie zastępuje pomiarów.

**MEM-042 — Pomiar.** Raport obejmuje idle, cold start, replay, query wieloźródłowe, Redis on/off i błąd źródła. Mierz PSS lub cgroup memory.current/memory.peak; nie sumuj wprost RSS backendów PostgreSQL ze wspólną pamięcią. Budżet RAM nie jest wynikiem benchmarku.

**SEC-050 — Auth.** Sprawdzaj uprawnienia przed cache/event/projection read. PG runtime: non-owner, non-superuser, NOBYPASSRLS; tenant wynika z uwierzytelnienia. Zwykły MCP nie wystawia arbitralnego SQL lub shell. Model conformance nie jest granicą auth produkcji.

**SEC-051 — Cache.** Tylko odtwarzalne treści/wersjonowane projekcje. Aktualny ACL nie jest zastępowany nieograniczenie starym cache. Redis down wymaga bounded fallback; authoritative ES nie może zniknąć przez eviction.

## Migracja i adopcja

**MIG-060 — SQLite równolegle.** Adaptery repozytoriów + transactional capture/ES + relay pozwalają na stopniową migrację. Zapis aplikacji i capture są atomowe w tym samym pliku SQLite. Niepełne objęcie writerów nie jest pełnym ES. Row-change triggery nie odtwarzają intencji domenowej.

**MIG-061 — Transfer authority.** Przełączenie wymaga freeze/drain starego writera, sprawdzenia head/barrier, przeniesienia idempotencji, nowego authorityEpoch i fencing starego writera. Sam rekord PG nie blokuje odłączonego SQLite. Bez potwierdzonego zatrzymania nie wolno przejąć streamu. Offline multi-writer wymaga osobnego kontraktu scalania.

**MIG-062 — Uczciwa historia.** Legacy baseline opisuje stan, nie wymyśla dawnych zdarzeń. Import wymaga snapshotu, mapy typów/ID, checksum i restore. Po nowych zapisach rollback wymaga uzgodnienia/reverse replication, nie samej zmiany DSN.

**GOV-070 — Dowody.** Oddziel wyniki statyczne, conformance, upstream, live PG/Redis, pomiar RAM i deployment. Nie deklaruj oficjalnej adopcji lub wdrożenia na podstawie posiadania manifestu. Wersja 0.2 używa nowych URI `/v2`; stare kontrakty i eventy są niezmienne.
