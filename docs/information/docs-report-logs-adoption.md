---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "docs-report-logs-adoption",
  "kind": "information",
  "version": 1,
  "title": "Zgodność data-plane ze standardami logs, docs i report",
  "status": "proposed",
  "owner": "wellmanifest/data-plane",
  "created": "2026-10-12",
  "updated": "2026-10-12",
  "review_after": "2026-10-26",
  "source_revision": "52f9d4bcdf7c8e7ef4df615fcc16538e4c468282",
  "affected_repositories": [
    "wellmanifest/data-plane"
  ],
  "evidence": [
    "https://github.com/wellmanifest/docs/blob/ebe7501063ef4f3e63ded610c2d3183010ca636e/docs/standard/POLICY.md",
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

Reguły pochodzą z przypiętych rewizji: docs 0.1.1 (`ebe7501`), report 0.1.0
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

Checker docs nie jest podłączony do `.github/workflows/conformance.yml` ani do
chronionego CI/OneDev; przypięcie i lokalna kontrola nie dowodzą egzekwowania.
Standard report jest kandydatem bez wydania i adopcji przez konsumentów.
Profil docs 0.1.1 nie obejmuje kompaktowego formatu v2 z nowszych wydań docs.
Checker docs nie ocenia prawdziwości treści; przegląd merytoryczny pozostaje wymagany.

<!-- docs:section next_actions -->
## Next actions

Właściciel standardu podłącza checker docs do chronionego CI/OneDev i dodaje
negatywne canary (brak adopcji, rozbieżny pin, brak indeksu). Przy zmianie
`STANDARD.md` lub `qa/REPORT.md` należy je przenieść do profilu i podnieść wersję.
Decyzja o przejściu na nowszy profil docs wymaga osobnej adopcji i nowego pinu.
