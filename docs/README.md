# Dokumentacja data-plane

Indeks dokumentów repozytorium `wellmanifest/data-plane`. Miejsce, metadane i
indeks określa [wellmanifest/docs 0.6.0](https://github.com/wellmanifest/docs/blob/19efafbeb18923cfd51cc69bd519330488500137/docs/standard/POLICY.md);
przypięcie jest w `.governance/docs.json`.

## Dokumenty zarządzane

- [Zgodność ze standardami logs, docs i report](information/docs-report-logs-adoption.md) — gdzie trafiają dokumenty, raporty i dowody oraz jak pozostają rozdzielone od audytu logs.
- [Jednoliniowy format data-plane.line/v1](information/line-format.md) — `typ: obiekt {zmienne}` dla shell, REST, gRPC, MCP i logów; przykłady w [examples/lines](../examples/lines/examples.line).
- [Audyt zgodności ze standardami logs, docs i report](analysis/standards-alignment-audit.md) — wyniki lokalnych kontroli, [manifest report](analysis/standards-alignment-audit.report.json) i artefakty w [qa/standards-alignment](../qa/standards-alignment/).

## Dokumenty historyczne

Poniższe dokumenty poprzedzają przyjęcie profilu docs. Zachowano je bez zmian;
migracja następuje przy ich następnej merytorycznej zmianie.

- [Status implementacji 0.2.0](IMPLEMENTATION_STATUS.md)
- [Zadania LLM 0.2](LLM_TASKS_V02.md)
- [Repozytorium i publikacja](REPOSITORY.md)
- [Raport weryfikacji 0.2.0](../qa/REPORT.md) — pomiary i surowe wyniki w `qa/`.
- [SQLite, grupowe zatwierdzanie, PostgreSQL i PGlite](analysis/storage-engines.md) — pomiar silników dla wzorca data-plane, test schematu ES na żywym PostgreSQL 16 i rekomendacje profili.
