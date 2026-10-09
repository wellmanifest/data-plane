# Zadania adopcji 0.2 dla agenta LLM

Cel nadrzędny: POA/CQRS/ES w każdym wdrożeniu, mały RAM i wspólne dane. Używaj istniejącej autoryzacji i instrukcji repozytorium; standard sam nie nadaje uprawnień do produkcji.

| Zadanie | Konkretna praca | Dowód ukończenia |
|---|---|---|
| DP-01 Inventory | Zidentyfikuj bazy, tabele, writery, czytniki, ścieżki CLI/API, cache i istniejące eventy | Mapa ownership oraz audit SQLite |
| DP-02 ADR | Wybierz profile storage/low-ram, granice streamów i source registry | Jednoznaczny writer per stream, lista nieobjętych writerów |
| DP-03 Ports | Repository/UnitOfWork; osobne command/query bez zmiany silnika | Regresja aktualnej aplikacji przechodzi |
| DP-04 Baseline | Spójny snapshot, mapa typów/ID, jawna granica historii | Snapshot hash, liczniki, restore drill |
| DP-05 ES | Atomowy append, CAS, idempotencja, head, outbox/inbox | Retry, crash, gap, concurrent writers, rollback |
| DP-06 Projection | Odtwarzalny read model i checkpoint; wersjonowany projector | Rebuild porównany z bieżącym stanem |
| DP-07 Logs | Zgodny audit bez dopisywania payload, własny error catalog | Pin, upstream conformance, mapping evidence |
| DP-08 Transports | Jedna warstwa usług dla CLI/REST/GraphQL/MCP | Te same uprawnienia i rezultaty domenowe |
| DP-09 Hybrid | Relay SQLite↔PG w wybranym kierunku, bounded batches | Target commit przed source ACK; duplikat bez drugiego skutku |
| DP-10 GraphQL | Źródła, aliasy encji, batch resolvers, freshness | Test N+1, tenant boundary, unavailable ≠ empty |
| DP-11 Memory | Jeden proces/pule, Redis off, małe porcje i cache | Idle/peak, replay i join test na rzeczywistym runtime |
| DP-12 Cutover | Freeze/drain, verified head, receipts, epoch/fence | Brak aktywnego starego writera; kontrolowany nowy writer |

Nie wdrażaj wszystkich adapterów/storage jednocześnie, jeśli nie są potrzebne. Reuse istniejących repozytoriów i jednej instancji PG ma pierwszeństwo przed uruchamianiem osobnej bazy dla każdej małej paczki. Wybór SQLite jest pełnoprawny, jeśli spełnia invariants i ograniczenia wdrożenia.

Zapis w starej tabeli plus event musi być w tej samej transakcji. Jeżeli stara tabela pozostaje źródłem prawdy na etapie capture, oznacz etap transitional i zakończ go dopiero po przejściu command handlerów na ES. Nie nazywaj row-level triggera pełnym domenowym ES bez jawnego kontraktu znaczenia.

Na końcu raportuj: standard przyjęty / kod / conformance / realne DB / pomiar RAM / migracja / deployment. Test dwóch SQLite nie zastępuje testu PostgreSQL ani testu produkcyjnego GUI agenta. Nie uruchamiaj podczas replay ponownie zewnętrznych skutków.
