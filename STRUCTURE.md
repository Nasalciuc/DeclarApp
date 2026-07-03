# Structura proiectului — Customs Declaration Analyzer

> Monorepo: `backend/` (Python, Lambda), `infra/` (AWS SAM), `web/` (Next.js 16),
> `scripts/` (operațiuni). Designul sistemului e în `ARCHITECTURE.md`; aici e
> harta fișierelor: ce conține fiecare și în ce fază se construiește.
>
> Legendă: **[✔]** există deja · **[F1]** pipeline determinist · **[F2]** semantic + web
> · **[F3]** sugestie cod + HITL complet.

## 1. Arborele complet

```
customs-analyzer/
├── README.md                        # setup în 5 pași: budgets → sam deploy → seed → smoke → web
├── ARCHITECTURE.md                  # designul sistemului                      [✔]
├── STRUCTURE.md                     # acest fișier                             [✔]
├── .gitignore                       # .env*, .aws-sam/, node_modules, seed/data
│
├── backend/
│   ├── requirements.txt             # boto3 · dev: moto, pytest
│   ├── cli/
│   │   └── extract_declaration.py   # CLI local: PDF → JSON (unealtă de dev)   [✔]
│   ├── src/
│   │   ├── common/
│   │   │   ├── __init__.py
│   │   │   ├── models.py            # TypedDict-uri + enums de status          [F1]
│   │   │   ├── codes.py             # normalize_code, validări structurale     [F1]
│   │   │   ├── fiscal.py            # run_fiscal_check — motorul fiscal        [F1]*
│   │   │   └── dynamo.py            # acces tabele + optimistic locking        [F1]
│   │   ├── prompts/
│   │   │   ├── extraction.py        # schema SAD + promptul de extracție       [F1]
│   │   │   └── semantic.py          # promptul descriere ↔ cod                 [F2]
│   │   ├── handlers/
│   │   │   ├── extract_handler.py   # S3 input/ → Bedrock → extracted/         [F1]
│   │   │   ├── validate_handler.py  # 4 verificări → reports/ + verdict        [F1–F2]
│   │   │   ├── hitl_correction.py   # corectare cod + refiscal (testat)        [✔]
│   │   │   └── suggest_handler.py   # S3 Vectors + agent sugestie cod          [F3]
│   │   └── seed/
│   │       ├── seed_tariff_codes.py # nomenclator + taxe → DynamoDB            [F1]
│   │       └── data/                # tariful brut (xlsx/csv) — gitignored
│   └── tests/
│       ├── test_fiscal.py           # motorul fiscal, funcții pure             [F1]
│       ├── test_hitl_correction.py  # fluxul HITL pe moto                      [✔]
│       ├── test_validate_handler.py # cele 4 verificări pe fixture             [F1–F2]
│       └── fixtures/
│           └── declaration_sample.json
│
├── infra/
│   ├── template.yaml                # SAM: bucket + events, tabele, lambde, IAM [F1]
│   └── samconfig.toml               # regiune, stack name, parametri
│
├── web/                                                                        [F2–F3]
│   ├── package.json · next.config.ts · .env.example
│   └── src/
│       ├── app/
│       │   ├── layout.tsx · page.tsx            # dashboard: lista declarațiilor
│       │   ├── upload/page.tsx                  # drag & drop
│       │   └── declarations/[id]/page.tsx       # ecranul de detaliu (HITL)
│       ├── actions/
│       │   ├── upload.ts                        # presigned PUT către input/
│       │   ├── declarations.ts                  # listă + get (polling)
│       │   └── corrections.ts                   # invocă Lambda hitl-correction
│       ├── components/
│       │   ├── declaration-table.tsx · upload-dropzone.tsx
│       │   ├── checks-panel.tsx                 # panoul celor 4 verificări
│       │   └── pdf-preview.tsx
│       └── lib/aws.ts                           # clienți SDK (S3, DynamoDB, Lambda)
│
└── scripts/
    ├── set_budgets.sh               # alerte $20/$50/$100 — SE RULEAZĂ PRIMUL   [F1]
    └── smoke_test.sh                # upload sample → poll status → afișează raportul
```

\* `fiscal.py` se extrage din `hitl_correction.py` — funcția `run_fiscal_check`
există deja și e testată; doar se mută în `common/` și se importă din ambele locuri.

## 2. `backend/src/common/` — nucleul fără I/O extern

**`models.py`** — vocabularul întregului sistem, într-un singur loc:
`GoodsItem`, `Declaration`, `TariffEntry`, `CheckResult`, `Report` (TypedDict),
plus enums: `DeclarationStatus` (EXTRACTED / VALIDATED / FLAGGED / ERROR),
`CheckStatus` (PASS / FAIL / UNCERTAIN), `SemanticStatus` (MATCH / MISMATCH /
UNCERTAIN). Orice handler vorbește în termenii ăștia.

**`codes.py`** — `normalize_code()` (există în hitl, se mută aici),
`is_tariff_line()` (8–9 cifre), validări ISO-3166 (țări) și ISO-4217 (monede)
pe seturi statice. Zero dependențe de rețea.

**`fiscal.py`** — `run_fiscal_check(goods_item, tariff_entry) -> dict`.
Recalcul taxă vamală (ad-valorem), acciz (procent sau per-kg), TVA pe baza
corectă (valoare în vamă + taxă + acciz), comparație cu caseta 47, toleranță
±0.5% sau ±1 MDL. Funcție pură — de-asta e testabilă fără AWS.

**`dynamo.py`** — `get_declaration()`, `put_declaration_versioned()`
(optimistic locking pe `version`, ridică `ConflictError`), `get_tariff_entry()`.
Numele tabelelor din env. Singurul loc care știe de DynamoDB.

## 3. `backend/src/prompts/` — prompturile ca fișiere separate

Separate de handlere ca să fie versionabile și review-uibile independent:
un diff pe prompt nu se pierde într-un diff de cod.

**`extraction.py`** — `OUTPUT_SCHEMA` + `PROMPT` (există în CLI, se mută aici):
schema pe casetele SAD, reguli anti-halucinare (null când nu poate citi,
digits-only la cod, numere fără separatori).

**`semantic.py`** — promptul verificării descriere ↔ cod: primește descrierea
mărfii (caseta 31), descrierea oficială a codului declarat + notele de capitol,
și cere JSON strict: `{status, confidence, reasoning, candidate_codes[]}`.
Instruit explicit să semnaleze subclasificări plauzibil-intenționate.

## 4. `backend/src/handlers/` — cele 4 Lambde

**`extract_handler.py` [F1]** — trigger: S3 event pe `input/`.
Ia PDF-ul, apelează Bedrock Converse cu `document` block + promptul din
`prompts/extraction.py`, parsează JSON-ul robust (logica din CLI), scrie
`extracted/{id}.json` + item nou în `declarations` (`status=EXTRACTED`,
`version=0`). La eroare: `status=ERROR` cu mesaj, nu excepție tăcută.

**`validate_handler.py` [F1–F2]** — trigger: S3 event pe `extracted/`.
Per marfă rulează: format (`codes.py` + cod există în `tariff_codes`),
fiscal (`common/fiscal.py`), consistență (masa netă ≤ brută, sumă articole ≈
total facturat, unitate suplimentară prezentă, preferință DCFTA doar cu
origine eligibilă) și — controlat de `ENABLE_SEMANTIC=1` din F2 — semantica
prin Bedrock. Agregă verdictul, scrie `reports/{id}.json` + update în
`declarations`. F1 livrează primele 3 verificări; F2 doar aprinde flagul.

**`hitl_correction.py` [✔]** — livrat și testat (4 teste pe moto): validează
noul cod, îl scrie în marfă, re-rulează fiscal, marchează semantica drept
rezolvată uman, audit trail, locking, rescrie raportul S3. Singura schimbare
la refactor: `from common.fiscal import run_fiscal_check`.

**`suggest_handler.py` [F3]** — chemat când semantica dă MISMATCH: embedding
pe descriere (Titan/Cohere pe Bedrock) → k-NN în S3 Vectors peste descrierile
nomenclatorului → Claude ordonează candidații cu impactul de taxă al fiecăruia
→ `suggested_codes[]` în raport. De-abia aici apare vector store-ul.

## 5. `backend/src/seed/` + `backend/tests/`

**`seed_tariff_codes.py`** — citește Tariful Vamal Integrat (export
xlsx/csv de la Serviciul Vamal, pus în `seed/data/`), normalizează codurile,
validează ratele, `batch_write` idempotent în `tariff_codes`. Rulabil parțial
(pe capitole) ca să poți testa cu capitolele 84–85 înainte să încarci tot.

**Teste** — `test_fiscal.py` (aritmetica pură: toleranțe, acciz per-kg, TVA pe
bază compusă), `test_hitl_correction.py` [✔], `test_validate_handler.py`
(cele 4 verificări pe `fixtures/declaration_sample.json` — o declarație
anonimizată reală ca fixture canonic). Toate pe moto, zero cost.

## 6. `infra/template.yaml` — un singur stack SAM

Resurse declarate: bucketul principal cu notificări filtrate pe prefix
(`input/` → extract, `extracted/` → validate), cele două tabele DynamoDB
(`PAY_PER_REQUEST`), cele 3 Lambde F1 (+ Function URL cu auth `AWS_IAM`
pentru `hitl-correction`), roluri IAM minimale per funcție
(`bedrock:InvokeModel`, S3 pe prefixele proprii, DynamoDB pe tabelele proprii),
retenție CloudWatch Logs 7 zile (grupuri statice prin
`LoggingConfig`, fără cursa „already exists" la primul deploy), coadă SQS
pentru evenimentele eșuate după retry-uri (`FailedEventsQueue`) și origine
CORS parametrizabilă (`WebOrigin`). Deploy: `sam build && sam deploy --guided`
o dată, apoi doar `sam deploy`.

De ce SAM și nu Terraform aici: un singur fișier, nativ pentru Lambda + events,
și rămâi în ecosistemul Python/AWS pe care-l folosești deja.

## 7. `web/` — Next.js 16 (App Router)

**`actions/upload.ts`** — server action: cere presigned PUT pe
`input/{uuid}.pdf`, browserul urcă direct în S3; pipeline-ul pornește singur.
**`actions/declarations.ts`** — listă (Query pe GSI `status-created_at`) +
`getDeclaration(id)` pentru polling la 2–3s până statusul iese din EXTRACTED.
**`actions/corrections.ts`** — `InvokeCommand` către `hitl-correction` cu
`{declaration_id, item_number, new_code, corrected_by}`; răspunsul (fiscal
recalculat + verdict) se randează direct în `checks-panel.tsx`.
**`components/checks-panel.tsx`** — panoul celor 4 verificări din mockup:
chips PASS/FAIL/MISMATCH, detaliile fiscale (așteptat vs declarat), butoanele
Corectează / Aprobă / Respinge.
**`lib/aws.ts`** — clienți SDK creați o dată, credențiale din env-ul
serverului (niciodată în client).

Hosting: **Vercel free tier**. Amplify Hosting suportă oficial SSR doar până
la Next.js 15 (pe 16 doar SSG, care ne-ar tăia server actions), iar creditele
AWS oricum se consumă pe Bedrock, nu pe hosting. Reevaluează Amplify când
adoptă Adapter API-ul (stabil din 16.2).

Note Next.js 16 pentru codul nostru: `params` e Promise în
`declarations/[id]/page.tsx` (`const { id } = await params`); eventualul
middleware se numește `proxy.ts`; caching-ul explicit (totul dinamic by
default) e exact ce vrem — statusul din polling nu poate fi servit stale.

## 8. Variabile de mediu

| Variabilă | Folosită de | Descriere |
|---|---|---|
| `BUCKET` | handlers, web | bucketul unic (input/extracted/reports) |
| `DECLARATIONS_TABLE` | handlers, web | default `declarations` |
| `TARIFF_TABLE` | handlers, seed | default `tariff_codes` |
| `REPORTS_BUCKET` | hitl_correction | = `BUCKET` în template |
| `BEDROCK_MODEL_ID` | extract, validate | cu prefix inference profile (`eu.`) |
| `ENABLE_SEMANTIC` | validate_handler | `0` în F1, `1` din F2 |
| `AWS_REGION` | tot | `eu-central-1` |

## 9. Convenții

Cod, identificatori și comentarii în engleză; documente și UI în RO (+RU în
UI mai târziu). Bani exclusiv în `Decimal`. Statusurile doar din enums
(`models.py`), niciodată string-uri ad-hoc. Un singur bucket cu prefixe, nu
trei buckete. Orice scriere în `declarations` trece prin
`put_declaration_versioned`. Conținutul declarațiilor nu se loghează
(date comerciale/personale). Orice modul nou vine cu test pe moto.

## 10. Ordinea de implementare (F1)

1. `scripts/set_budgets.sh` — plasa de siguranță, înainte de orice resursă.
2. `infra/template.yaml` minimal (bucket + tabele) → `sam deploy`.
3. `common/` (mutarea `fiscal.py` + `codes.py`, `models.py`, `dynamo.py`) —
   testele existente trebuie să treacă neschimbate.
4. `seed_tariff_codes.py` cu capitolele 84–85 pentru început.
5. `extract_handler.py` (portarea CLI-ului) + event pe `input/`.
6. `validate_handler.py` determinist + event pe `extracted/`.
7. `hitl_correction.py` în stack + Function URL.
8. `scripts/smoke_test.sh`: un PDF real intră, raportul iese — F1 închis.
