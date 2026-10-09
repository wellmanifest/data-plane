# Repozytorium i publikacja

Proponowana nazwa: `wellmanifest/data-plane`. Paczka zawiera źródła oraz `repository.bundle` z lokalnym commitem wydania. Bundle dodano do archiwum jako artefakt dystrybucji; nie jest plikiem śledzonym przez samo repozytorium.

Po rozpakowaniu:

```bash
git clone /sciezka/wellmanifest-data-plane-0.2.0/repository.bundle data-plane
cd data-plane
python3 -m venv .venv
.venv/bin/pip install -r requirements-qa.txt
make check test PYTHON=.venv/bin/python
```

Nie utworzono zdalnego repozytorium ani nie wykonano push. Publikujący maintainer powinien zastosować rzeczywiste wymagania governance organizacji, wskazać właściciela standardu oraz zatwierdzić nazwę/wersję. Wygenerowany manifest nie udaje oficjalnej adopcji ani uprawnień organizacji.

Repozytorium adoptera przypina wersję/commit tego standardu i upstream.lock.json. Nowe implementacje runtime pozostają w swoich repozytoriach, z własnymi testami integracji, uprawnieniami, konfiguracją i sekretami. Nie kopiuj produkcyjnych baz lub logów do repo standardu.
