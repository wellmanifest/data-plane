---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "docs-report-logs-adoption",
  "kind": "information",
  "version": 3,
  "title": "Zgodność data-plane ze standardami logs, docs i report",
  "status": "proposed",
  "owner": "wellmanifest/data-plane",
  "scope": "repository",
  "created": "2026-10-12",
  "updated": "2026-10-13",
  "review_after": "2026-10-27",
  "source_revision": "8eeafd4e7871295c56429e6360a135926838ff20",
  "affected_repositories": [
    "wellmanifest/data-plane"
  ],
  "evidence": [
    "https://github.com/wellmanifest/docs/blob/19efafbeb18923cfd51cc69bd519330488500137/docs/standard/POLICY.md",
    "https://github.com/wellmanifest/report/blob/340244d0d150c1467c134ce072378fbed26d5c4f/docs/information/report-standard.md",
    "https://github.com/wellmanifest/logs/blob/cd9d9558e09b9135ef92712096eb951fd524aa75/docs/ARCHITECTURE.md",
    "https://github.com/wellmanifest/data-plane/blob/52f9d4bcdf7c8e7ef4df615fcc16538e4c468282/spec/LOGS_ADOPTION.md"
  ]
}
---

# Zgodność data-plane ze standardami logs, docs i report

<!-- docs:section purpose -->
## Purpose

Wskazuje, jak repozytorium standardu Data Plane stosuje trzy standardy
Wellmanifest: `docs` (miejsce i metadane dokumentów), `report` (manifest
końcowego raportu) i `logs` (kanoniczny audyt oraz katalog błędów). Dokument
rozdziela te obowiązki, aby jeden wynik miał jednego właściciela i jedno miejsce.

<!-- docs:section scope -->
## Scope

Dotyczy nowych i merytorycznie zmienianych informacji, analiz, planów
refaktoryzacji i decyzji w `wellmanifest/data-plane`. Nie zmienia treści
`STANDARD.md`, kontraktów, profili ani bajtów zdarzeń. Status dokumentu nie jest
zgodą na wdrożenie, merge, odczyt sekretów ani usunięcie danych.

<!-- docs:section evidence -->
## Evidence

Reguły pochodzą z przypiętych rewizji: docs 0.6.0 (`19efafb`; wcześniej 0.1.1 `ebe7501`), report 0.1.0
(`340244d`, kandydat lokalny, status proposed) i logs 0.5.0 (`cd9d955`, ten sam
pin co `upstream.lock.json`). Stan wyjściowy to `52f9d4b`; jego pomiar opisuje
analiza [Audyt zgodności ze standardami](../analysis/standards-alignment-audit.md).

<!-- docs:section content -->
## Content

**Docs.** Nowy wynik trafia do `docs/information/<id>.md`,
`docs/analysis/<id>.md`, `docs/refactoring/<id>.md` albo `docs/decisions/<id>.md`
i jest wpisany do `docs/README.md`. Nagłówek JSON zawiera właściciela
`wellmanifest/data-plane`, wersję, status, daty, pełny `source_revision` i
dowody. Zmiana ustaleń zwiększa `version`. Rewizję i digest polityki wskazuje
`.governance/docs.json`; zaufane CI podaje je checkerowi, PR nie wybiera słabszego
standardu. Końcowy wynik nie może istnieć wyłącznie w `/tmp`, stanie sesji,
czacie ani `project/ticket-*`.

`make docs-check` (`tools/check_docs.py`) pobiera checker z rewizji
`DOCS_STANDARD_REVISION`, sprawdza HEAD i digest polityki względem adopcji,
uruchamia bramę z `DOCS_BASE_SHA` oraz cztery negatywne canary na kopiach drzewa:
brak adopcji, rozbieżny digest polityki, brak indeksu i błędna rewizja standardu.
Brak rewizji lub canary przyjęty przez checker zatrzymuje kontrolę.

**Report.** Końcowa analiza ma obok dokumentu sidecar
`docs/analysis/<id>.report.json` (`wellmanifest.report/manifest/v1`).
`document.sha256` wiąże dokładne bajty dokumentu. Fakty, hipotezy i
rekomendacje są oddzielone; wynik testu to `PASS`, `FAIL`, `SKIP` lub `NOT_RUN`,
a niewykonana kontrola nie jest zaliczeniem. Manifest ma `authority=none`, nie
dowodzi publikacji i podlega lokalnej kontroli
`conformance.py <manifest> --root <repo>` przypiętego checkera report.

**Logs.** Obowiązują bez zmian LOG-020…023 i
[adopcja logs](https://github.com/wellmanifest/data-plane/blob/52f9d4bcdf7c8e7ef4df615fcc16538e4c468282/spec/LOGS_ADOPTION.md).
Dokument docs lub manifest report nie jest zdarzeniem `wellmanifest.logs/event/v1`
i nie zastępuje audytu. Raport może wskazać hash lub receipt, nie wstawia surowych
logów, transkrypcji, backupów ani sekretów. Runbooki błędów pozostają w
`errors/{CODE}.md` z namespace `DP`.

**Dokumenty historyczne.** `STANDARD.md`, `spec/`, `errors/`, `docs/*.md`,
`SOURCES.md`, `LLM_REFACTORING.md` i `qa/REPORT.md` zachowano bez zmian.
Migracja do profilu następuje przy ich następnej merytorycznej zmianie.

<!-- docs:section limitations -->
## Limitations

Krok `make docs-check` w `.github/workflows/conformance.yml` jest kontrolą
doradczą: PR może zmienić ten workflow, a reguła gałęzi nie wymaga jego wyniku.
Bez chronionego CI/OneDev lub wymaganego checku nie ma dowodu egzekwowania.
Push nowej gałęzi nie ma bazy i wykonuje tylko audyt.
Standard report jest kandydatem bez wydania i adopcji przez konsumentów.
Pin 0.6.0 to commit na `main` wellmanifest/docs, nie oznaczone wydanie; ostatnie wydanie to v0.1.0.
Checker docs nie ocenia prawdziwości treści; przegląd merytoryczny pozostaje wymagany.

<!-- docs:section next_actions -->
## Next actions

Właściciel repozytorium ustawia zmienną `DOCS_STANDARD_REVISION` i wymaga
checku `conformance` w regule gałęzi `main` albo w chronionym profilu OneDev. Przy zmianie
`STANDARD.md` lub `qa/REPORT.md` należy je przenieść do profilu i podnieść wersję.
Pin docs zmieniono z 0.1.1 na 0.6.0, bo checker 0.1.1 odrzuca zarządzane kopie dokumentów pakietu wellmanifest/new-project w `.governance/docs/`. Od 0.6.0 checker pomija pliki wymienione w `.governance/managed-copies.json` po weryfikacji ich SHA-256. Kolejna zmiana pinu wymaga osobnej adopcji.
