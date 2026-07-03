# Customs Declaration Analyzer

Analizor de declarații vamale (SAD / Declarație Vamală) pe AWS serverless.
Urci un PDF sau o imagine → sistemul extrage câmpurile cu Claude pe Bedrock →
rulează patru verificări (format, fiscal, consistență, semantic) → produce un
raport cu verdict. Cele marcate „de verificat" trec printr-un ecran de
corectare umană (HITL).

Cost în repaus: **$0/lună** — totul e pay-per-use. ~$0.03–0.06 per declarație.

- Arhitectura completă: [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- Harta fișierelor: [`STRUCTURE.md`](./STRUCTURE.md)

## Structură

```
backend/    Python — Lambda handlers, motorul de verificări, prompturi, seed
infra/      AWS SAM — un singur stack (bucket, 2 tabele, 3 Lambda)
scripts/    set_budgets.sh (plasă de siguranță), smoke_test.sh (test E2E)
web/        Next.js 16 — încărcare, listă, ecranul HITL
```

## Pornire

Necesare: cont AWS cu credite, `aws` CLI configurat (`aws configure`),
AWS SAM CLI, Node.js 20+, Python 3.12.

Pe Windows: scripturile `.sh` au echivalente native în `scripts/*.ps1`
(`set_budgets.ps1`, `smoke_test.ps1`) — sau rulează-le pe cele `.sh` din
Git Bash.

### 1. Plasa de siguranță — buget + alerte (ÎNAINTE de orice deploy)

```bash
./scripts/set_budgets.sh tu@exemplu.md 200
```

Setează un buget lunar cu alerte pe email la $20 / $50 / $100.

### 2. Activează modelul în Bedrock

În consola AWS → Bedrock → *Model access*, cere acces la Claude în regiunea
ta (ex. `eu-central-1`). Apoi ia ID-ul EXACT al inference profile-ului
(valoarea implicită din template e orientativă, nu garantată):

```bash
aws bedrock list-inference-profiles --region eu-central-1 \
  --query "inferenceProfileSummaries[].inferenceProfileId"
```

Alege profilul `eu.anthropic.claude-...` dorit și dă-l la deploy prin
`BedrockModelId`.

### 3. Deploy infrastructura

```bash
cd infra
sam build
sam deploy --guided \
  --parameter-overrides BedrockModelId=eu.anthropic.claude-sonnet-4-6
```

La final, notează *Outputs*: `BucketName`, `DeclarationsTableName`,
`HitlFunctionName`. Redeploy ulterior: doar `sam deploy`.

Semanticul (verificarea descriere↔cod prin LLM) e oprit implicit. Îl pornești
cu `--parameter-overrides ... EnableSemantic=1`.

### 4. Încarcă nomenclatorul tarifar

Datele incluse sunt **didactice**, nu tariful oficial. Pentru test rapid:

```bash
python backend/src/seed/seed_tariff_codes.py \
  --csv backend/src/seed/sample_tariff.csv
```

Pentru uz real: exportă Tariful Vamal Integrat de la Serviciul Vamal într-un
CSV cu coloanele din antetul `sample_tariff.csv` și încarcă-l la fel
(opțional `--chapters 84,85` ca să încarci pe capitole).

### 5. Rulează testele (opțional, local, fără cost AWS)

```bash
pip install -r backend/requirements-dev.txt
cd backend && python -m pytest tests -q
```

16 teste pe `moto` (S3 + DynamoDB simulate) — nimic real, zero cost.

### 6. Pornește aplicația web

```bash
cd web
cp .env.example .env.local     # completează din Outputs-ul de la pasul 3
npm install
npm run dev                    # http://localhost:3000
```

Credentiale AWS: local prin `aws configure` / `AWS_PROFILE`.

### Operare

Evenimentele care pică de 3 ori (extract/validate) NU se pierd: ajung în
coada SQS din outputs (`FailedEventsQueueUrl`). Dacă o declarație „dispare"
sau rămâne blocată, verifică întâi coada, apoi CloudWatch Logs (retenție 7
zile). La deploy public, setează `WebOrigin` la URL-ul aplicației ca să
strângi CORS-ul de pe bucket.

### 7. Test end-to-end

```bash
./scripts/smoke_test.sh cale/catre/declaratie.pdf
```

Urcă declarația, așteaptă pipeline-ul, afișează raportul.

### 8. Deploy web (Vercel)

1. Creează un IAM user dedicat cu politica din
   [`infra/web-iam-policy.json`](./infra/web-iam-policy.json) (înlocuiește
   `<ACCOUNT_ID>`; dacă ai alt nume de stack, ajustează ARN-urile).
2. Push pe GitHub, importă proiectul în Vercel (root: `web/`).
3. Setează variabilele din `.env.example`, cu cheile IAM în
   `APP_AWS_ACCESS_KEY_ID` / `APP_AWS_SECRET_ACCESS_KEY`.
   **Numele `AWS_*` sunt rezervate de Vercel** — de-asta aplicația citește
   `APP_AWS_*`.
4. Pentru pilot închis fără auth propriu: activează *Deployment Protection*
   în Vercel (parolă / Vercel Authentication) — nimic public fără măcar atât.

> Amplify Hosting suportă oficial SSR doar până la Next.js 15; aplicația
> folosește Next.js 16 cu server actions, deci Vercel e calea directă.

## Gata de lansare? — checklist

Automat, deja verificat în repo: teste backend verzi, template lint-uit,
web typecheck-uit strict. Manual, în ordinea asta, înainte de primul user:

- [ ] `set_budgets.sh` rulat, email de alertă confirmat
- [ ] Model access aprobat în Bedrock + `BedrockModelId` setat cu ID-ul exact
- [ ] `sam build && sam deploy` verde, outputs notate
- [ ] Tarif încărcat (măcar sample-ul pentru pilot; OFICIALUL pentru real)
- [ ] `smoke_test.sh` pe 5–10 declarații reale — verdictele arată sănătos
- [ ] IAM user web creat cu `infra/web-iam-policy.json`
- [ ] Vercel: variabilele `APP_AWS_*` + Deployment Protection activat
- [ ] `WebOrigin` setat la URL-ul Vercel (redeploy cu `--parameter-overrides`)

## Limitări (oneste)

- **Nomenclatorul e didactic.** `sample_tariff.csv` are 10 rânduri
  ilustrative, câteva cu rate marcate „exemplu". Sursa de adevăr fiscală e
  tariful oficial — încarcă-l înainte de orice folosire reală.
- **Fără autentificare (Fază 1).** Oricine ajunge la aplicație vede și
  corectează declarații — și, mai scump: oricine poate încărca fișiere,
  iar fiecare fișier = un apel Bedrock plătit de tine (denial-of-wallet).
  Nu expune public fără auth; extract refuză oricum documente >8 MB.
- **`suggest_handler` (sugestie de cod, Fază 3) e scris dar netestat.** Cere
  S3 Vectors + un index de embeddings peste nomenclator, care nu fac parte din
  stack-ul de Fază 1.
- **Taxe ad-valorem și acciz procent/per-kg** sunt acoperite. Accizele per
  litru/per bucată cer o cantitate care nu e încă în schema de extracție → ies
  ca „incert", nu greșit.
- **Fără bounding boxes.** Verdictele nu sunt ancorate vizual în document;
  grounding-ul vizual e Fază 4 și cere un OCR cu coordonate (Textract/Mistral),
  fiindcă Bedrock Converse nu întoarce poziții.
