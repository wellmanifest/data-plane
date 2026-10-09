# URI, URN i współdzielenie

> Wersja 0.2: URI Data Plane mają /v2. Dodano odrębną tożsamość streamu, eventu i authority, zgodnie z POA_CQRS_ES.md. Zewnętrzny wellmanifest exchange pozostaje osobnym przypiętym kontraktem.

## Trzy różne identyfikatory

| Pojęcie | Przykład | Własność |
|---|---|---|
| Definicja operacji | `process://data-gateway/resource.read/v2` | Dokładny klucz lokalnego rejestru |
| Wersja danych | `urn:uuid:11111111-1111-4111-8111-111111111111` | Niezmienna treść |
| Wykonanie procesu | `urn:uuid:22222222-2222-4222-8222-222222222222` | Tożsamość wykonania ze zmiennym stanem |
| Lokalizacja | `https://gateway.example/v1/resources/...` | Może się zmienić; nie jest tożsamością |

Schemat `process:` jest konwencją aplikacyjną tego profilu, nie twierdzeniem o rejestracji schematu w IANA. Host `data-gateway` jest nazwą w rejestrze, nie wymogiem DNS. Zabronione są query, fragment, userinfo, whitespace i niejawne przekierowanie do shell/HTTP. URI dopuszcza się wyłącznie przez dokładne dopasowanie do rejestru. Nie należy automatycznie „naprawiać” URI wygenerowanego przez model.

UUID jest serializowany małymi literami. Generator może używać UUIDv4; UUIDv7 wymaga świadomej implementacji i oceny ujawniania czasu. Treść zasobu hashuje się jako dokładne bajty UTF-8 lub pliku. `mediaType` opisuje te same bajty. Wersjonowanie zasobów nie jest równoznaczne z automatycznym deduplikowaniem na podstawie hash: ten sam hash w różnych tenantach nie może ujawnić obecności cudzych danych.

Logiczna encja ma `entityId` i wskaźnik `{resourceUrn, revision}`. Aktualizacja treści publikuje nową wersję; osobna operacja CAS przesuwa wskaźnik. Jeśli oba kroki muszą być atomowe biznesowo, dodaj operację domenową wykonującą oba w jednej transakcji. Nie obiecuj transakcyjności dwóch osobnych wywołań sieciowych.

## Resolver i współdzielenie

1. Uwierzytelnij odbiorcę; ustal tenant z tożsamości, nie z pola podanego przez LLM.
2. Rozwiąż URN w zaufanym rejestrze. W profilach federacyjnych stosuj jawny routing; URN UUID nie zawiera adresu właściciela.
3. Sprawdź ACL, klasyfikację i ewentualne cofnięcie udostępnienia przed cache hit.
4. Pobierz bajty, zweryfikuj `sha256`, `byteLength`, `mediaType`; niezgodność daje `INTEGRITY_ERROR`.
5. Zwróć ograniczoną treść albo krótkotrwały lokator. Lokator podpisany jest sekretem; nie zapisuj go jako trwałej tożsamości w promptach/logach.

Przekazanie referencji między agentami nie kopiuje automatycznie ACL. Współdzielenie między tenantami wymaga explicit grant lub kontrolowanego importu pod nową lokalną tożsamością. Dopuszczalna jest niezmienna zawartość przy zmiennej polityce dostępu, retencji i dostępności. Usunięcie nie może ponownie przypisać tego samego URN innej treści.

## Zgodność ze wskazanym Wellmanifest

Wzorzec ma profil legacy i opcjonalny `semantic-v1`; ten standard wybiera nowy model wymiany `uri-urn-exchange-v1`. `reference/process-exchange.schema.json` jest wyodrębniony bez zmian z przypiętego commita. Schemat bazowego Data Plane i ten schemat nie są zamienne.

| Wellmanifest | Data Plane / reguła adaptera |
|---|---|
| operation | URI z katalogu operacji |
| contractDigest | Digest **zadeklarowanego kontraktu Wellmanifest**, nie dowolnie hash katalogu |
| inputs / outputs | Zweryfikowane referencje `{urn,sha256,mediaType}`; usuń rozszerzenia niedopuszczone przez schemat |
| messageUrn / requestUrn | Identyfikatory wiadomości; request ma równe oba pola, result ma nowy messageUrn |
| effects | Z kontraktu, nigdy z decyzji modelu |
| context / admission | Dowody z rzeczywistego kontrolera i repozytorium, gdy wymaga tego profil |
| completed | Wykonana deklarowana operacja; submit oznacza przyjęcie, nie ukończenie pracy procesu |

Adapter MUSI walidować także warunki między wiadomościami: powiązanie request/result, zgodność URI/digest/effects/inputs/context i uprawnienia. JSON Schema pojedynczej wiadomości tego nie dowodzi. Dla mutacji w profilu governed nie wolno fabrykować ticketów, scopeHash, admission receipts, fencing tokenów ani verification/completion refs. Gdy integracja nie ma kontrolera, nie może deklarować pełnej zgodności z governed exchange. Może używać bazowego profilu Data Plane z własną autoryzacją.

NL → kontrakt → typowany plan → walidacja → wykonanie → weryfikacja. Stany `clarify` i `unsupported` nie uruchamiają mutacji. Prawidłowy JSON nie gwarantuje poprawnej intencji ani bezpiecznych skutków.
