---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "standards-alignment-audit",
  "kind": "analysis",
  "version": 2,
  "title": "Audyt zgodności data-plane ze standardami logs, docs i report",
  "status": "proposed",
  "owner": "wellmanifest/data-plane",
  "scope": "repository",
  "created": "2026-10-12",
  "updated": "2026-10-13",
  "review_after": "2026-10-27",
  "source_revision": "43b95191080e3f07a450850383d727d865e85f31",
  "affected_repositories": [
    "wellmanifest/data-plane"
  ],
  "evidence": [
    "receipt:sha256:66d809598709ef9e04f05ae2edd73832406563da523afa3afe318ba407197231",
    "receipt:sha256:37b012775795e9ba09eca5d47b561313577b1b9032715e1620665feb76c3c468",
    "receipt:sha256:129603ce9c67ce85e56a5ef0188065038ee93f1d9569a1c04afc376cd663ff0b",
    "receipt:sha256:b5a474db573d05093df23b42cf22604e36348beffd4faa7b590b679fc482700a",
    "receipt:sha256:5b07b2aad385fa7698bc73d0ec4edf88e4591463f56a4d68201b8338ee7ec298",
    "receipt:sha256:2434d9b90e3c89cc720e490cfdd967e7e4910385524e228050c2d9897899c877"
  ]
}
---

# Analiza: Audyt zgodności data-plane ze standardami logs, docs i report

<!-- docs:section question -->
## Question

Czy opublikowane repozytorium `wellmanifest/data-plane` w rewizji `52f9d4b` spełnia
wymagania standardów `logs`, `docs` i `report` oraz co zmienia jego dostosowanie
w rewizji `ac9bda2`?

<!-- docs:section scope -->
## Scope

Jedno repozytorium. Standardy w przypiętych rewizjach: docs 0.1.1 (`ebe7501`),
logs 0.5.0 (`cd9d955`), report 0.1.0 (`340244d`, kandydat bez wydania).
Poza zakresem: runtime, PostgreSQL/Redis, Docker, chronione CI i publikacja.

<!-- docs:section method -->
## Method

Uruchomiono lokalnie checker docs (z `--base` i jawnym `--deliverable`), upstream
check logs z lokalnym checkoutem w pinie, `make check test` oraz dwa testy
negatywne: błędny pin standardu i zmianę `STANDARD.md`. Wyjścia zapisano jako
artefakty w `qa/standards-alignment/`. Manifest report zawiera ich digesty.

<!-- docs:section evidence -->
## Evidence

Artefakty `qa/standards-alignment/*` oraz źródła w rewizji `ac9bda2`:
`.governance/docs.json`, `docs/README.md`, `upstream.lock.json`, `tools/check_logs.py`
i `tests/`. Powiązania i digesty są w
[manifeście report](standards-alignment-audit.report.json).

<!-- docs:section facts -->
## Facts

- W `52f9d4b` checker docs zwrócił `ok: false`: `DOCS_ADOPTION` (brak `.governance/docs.json`) i `DOCS_INDEX` (brak `docs/README.md`).
- W `ac9bda2` ten sam checker zwraca `ok: true`, 1 dokument, bez uwag. Błędny pin standardu daje `DOCS_ADOPTION`.
- Zmiana `STANDARD.md` kończy się `DOCS_METADATA`: plik nie jest wyłączony z wykrywania i nie ma metadanych profilu.
- Logs: upstream `cd9d955`, 2 strumienie i 18 eventów bez uwag, 4 definicje błędów `DP` bez uwag, 1 fixture audytu; `runtimeAdoptionProven: false`.
- `make check` kończy się kodem 0; 30 testów OK (Python 3.13.12).
- `qa/REPORT.md` jest końcowym raportem poza `docs/analysis/`, bez metadanych profilu; pozostawiono go bez zmian.

<!-- docs:section hypotheses -->
## Hypotheses

Zmiana `spec/*.md` lub `errors/*.md` zakończy się tak samo jak zmiana
`STANDARD.md`, bo nie ma ich na liście wyłączeń reguł wykrywania docs 0.1.1.
Nie wykonano tej próby.

<!-- docs:section limitations -->
## Limitations

Checker docs nie jest wpięty do chronionego CI, więc zgodność jest zmierzona tylko
lokalnie. Checker i manifest report nie dowodzą prawdziwości treści ani publikacji.
Rewizja `ac9bda2` jest na gałęzi roboczej; po squash-merge jej SHA się zmieni.
Standard report jest kandydatem bez wydania. Redakcja nie była skanowana.

<!-- docs:section recommendations -->
## Recommendations

1. Podłączyć checker docs do chronionego CI/OneDev z negatywnymi canary (brak adopcji, błędny pin, brak indeksu).
2. Przy następnej zmianie `STANDARD.md`, `spec/` lub `qa/REPORT.md` przenieść je do profilu i podnieść wersję.
3. Decyzję o nowszym profilu docs (v2) podjąć osobną adopcją i nowym pinem.
