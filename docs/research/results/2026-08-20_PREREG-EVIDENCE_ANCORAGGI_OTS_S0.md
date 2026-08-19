# Ancoraggi OpenTimestamps della Stagione 0 — evidenza e ricetta di verifica

**Data**: 2026-08-20 · **Repo**: `traderLab` · **Commit di riferimento**: `14d4ee1`
**Origine**: rito T0 (igiene), passo 4, chiuso in STOP; rito T0-BIS, via (b)
ratificata dall'owner il 20/08/2026.

Questo documento fissa **quali byte** i tre timbri OpenTimestamps del record di
Stagione 0 certificano, **perché** due dei tre non coincidono con il blob a
`HEAD`, e **come** si verifica ciascuno dei tre da qualunque macchina. È
un'evidenza pre-registrata: la ricetta è dichiarata qui prima di essere usata
in qualunque verdetto.

---

## 1. I tre target

| # | Timbro | Target | Commit di introduzione |
| --- | --- | --- | --- |
| 1 | `docs/PREREG_LAB_S0.md.ots` | `docs/PREREG_LAB_S0.md` | `b1ee4d8` |
| 2 | `manifests/trader_v0_freeze_manifest.json.ots` | `manifests/trader_v0_freeze_manifest.json` | `b1ee4d8` |
| 3 | `MANIFEST_S0.json.ots` | `MANIFEST_S0.json` | `34939d2` |

I digest sono letti dai file `.ots` all'**offset 33**. La struttura del
preambolo, verificata byte per byte in questo rito su tutti e tre i file, è:

- offset 0–30 (31 byte): magic `\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94`;
- offset 31 (1 byte): versione `\x01`;
- offset 32 (1 byte): byte d'operazione `\x08` = SHA-256;
- offset 33–64 (32 byte): il digest timbrato.

---

## 2. Tabella dei tre target — digest timbrato contro blob a `HEAD`

Tutti i valori sono `sha256`, ricalcolati **in questo rito** (20/08/2026) sul
commit `14d4ee1`. Il blob è letto con `git cat-file blob HEAD:<path>`, cioè i
byte come stanno nella storia, indipendenti dalla macchina.

| Target | digest timbrato (OTS) | `sha256` del blob a `HEAD` | esito |
| --- | --- | --- | --- |
| `docs/PREREG_LAB_S0.md` | `f0a22924a24fdd27f251d8da645664cc8fcf0e75607e2ca18388c4e1e41628d4` | `f0a22924a24fdd27f251d8da645664cc8fcf0e75607e2ca18388c4e1e41628d4` | **coincide** |
| `manifests/trader_v0_freeze_manifest.json` | `429186db0eabc30e5fbb55b5b402a59995d7756fb5eea33a251aa28a0f1b98e8` | `6c61ed42d24b0596e76ac6e3b2a0a4a073413c02fc2cfbca1d442130ced0a50f` | **diverge** |
| `MANIFEST_S0.json` | `ced493a7b3ea36168d6b3c7a4fe7aa81bfada0bd318928dd2a6d552cb8c27275` | `38b67fc81167e169739e6c926b7b92d5f0049a74b218e068f8729072ad4596fe` | **diverge** |

Dimensioni misurate nello stesso rito, che dicono da sole di che scarto si
tratta:

| Target | byte del blob | byte del working tree | differenza |
| --- | --- | --- | --- |
| `docs/PREREG_LAB_S0.md` | 6 045 | 6 045 | 0 |
| `manifests/trader_v0_freeze_manifest.json` | 2 048 | 2 088 | +40 |
| `MANIFEST_S0.json` | 7 716 | 7 968 | +252 |

I +40 e i +252 byte sono esattamente il numero di righe dei due JSON: un `CR`
per riga. Nessun byte di contenuto è diverso.

---

## 3. La causa, isolata: i fine-riga, e nient'altro

`core.autocrlf` è `true` nella configurazione **locale** di questo repo. I tre
timbri **non furono apposti nella stessa condizione**:

- il timbro di `PREREG_LAB_S0.md` fu apposto sui byte **del blob**;
- i timbri dei due JSON furono apposti sui byte **del working tree convertito**
  (LF→CRLF in checkout).

La prova che la causa è solo questa: applicando al blob la trasformazione
LF→CRLF si ottiene esattamente il digest timbrato, per entrambi i JSON.

### 3.1 Verifica di equivalenza, rieseguita in questo rito (20/08/2026)

Trasformazione applicata: normalizzazione a LF (rimozione dei `CR` che
precedono un `LF`) seguita da LF→CRLF. È idempotente, ed è la stessa che `git`
esegue in checkout con `core.autocrlf=true`.

**`manifests/trader_v0_freeze_manifest.json`**
- `sha256(blob)` = `6c61ed42d24b0596e76ac6e3b2a0a4a073413c02fc2cfbca1d442130ced0a50f`
- `sha256(crlf(blob))` = `429186db0eabc30e5fbb55b5b402a59995d7756fb5eea33a251aa28a0f1b98e8`
- digest timbrato = `429186db0eabc30e5fbb55b5b402a59995d7756fb5eea33a251aa28a0f1b98e8`
- **`sha256(crlf(blob)) == digest timbrato` → vero**

**`MANIFEST_S0.json`**
- `sha256(blob)` = `38b67fc81167e169739e6c926b7b92d5f0049a74b218e068f8729072ad4596fe`
- `sha256(crlf(blob))` = `ced493a7b3ea36168d6b3c7a4fe7aa81bfada0bd318928dd2a6d552cb8c27275`
- digest timbrato = `ced493a7b3ea36168d6b3c7a4fe7aa81bfada0bd318928dd2a6d552cb8c27275`
- **`sha256(crlf(blob)) == digest timbrato` → vero**

**`docs/PREREG_LAB_S0.md`** (controprova nel verso opposto)
- `sha256(blob)` = `f0a22924a24fdd27f251d8da645664cc8fcf0e75607e2ca18388c4e1e41628d4` = digest timbrato → **vero**
- `sha256(crlf(blob))` = `0df16b193d9afcc812755055292346b6eac2e9f4410528ead82791b1d2cf5120` ≠ digest timbrato → **falso**

Il `.md` si verifica sul blob e **solo** sul blob; i due JSON si verificano
sulla trasformata CRLF del blob e **solo** su quella. Le due condizioni si
escludono a vicenda.

---

## 4. L'esito dei due cloni del rito T0 (20/08/2026)

Due cloni locali del repo, entrambi da `file:///c/Users/vadim.chilinciuc/git/traderLab`,
in directory temporanee, con `core.longpaths=true` (senza il quale il checkout
fallisce su `docs/research/Degenerate_Verbalized_Confidence_…_Remedies.md`,
nome troppo lungo) e con `core.autocrlf` forzato rispettivamente a `true` e a
`false`. Entrambi risultavano `git status` pulito; le directory sono state
rimosse a fine rito.

| Target | clone `autocrlf=true` | clone `autocrlf=false` | quale dei due torna |
| --- | --- | --- | --- |
| `docs/PREREG_LAB_S0.md` | `0df16b193d9afcc812755055292346b6eac2e9f4410528ead82791b1d2cf5120` | `f0a22924a24fdd27f251d8da645664cc8fcf0e75607e2ca18388c4e1e41628d4` | **`false`** |
| `manifests/trader_v0_freeze_manifest.json` | `429186db0eabc30e5fbb55b5b402a59995d7756fb5eea33a251aa28a0f1b98e8` | `6c61ed42d24b0596e76ac6e3b2a0a4a073413c02fc2cfbca1d442130ced0a50f` | **`true`** |
| `MANIFEST_S0.json` | `ced493a7b3ea36168d6b3c7a4fe7aa81bfada0bd318928dd2a6d552cb8c27275` | `38b67fc81167e169739e6c926b7b92d5f0049a74b218e068f8729072ad4596fe` | **`true`** |

**Nessuna configurazione di checkout riproduce tutti e tre i timbri.** Il `.md`
torna solo con `autocrlf=false`; i due JSON tornano solo con `autocrlf=true`.
Prima di questo documento, l'unico posto al mondo in cui tutti e tre tornavano
era il working tree dell'owner — ed è esattamente ciò che una prova non deve
essere.

La ricetta del §5 elimina la dipendenza dalla macchina: nessuno dei tre
controlli passa più per il checkout.

---

## 5. Ricetta di verifica, per target

La ricetta lavora **sui byte del blob**, letti con `git cat-file`. Non dipende
da `core.autocrlf`, da `.gitattributes`, dal sistema operativo né dallo stato
del working tree: dà lo stesso risultato su qualunque macchina e su qualunque
clone.

### 5.1 `docs/PREREG_LAB_S0.md` — si verifica **sul blob**

```sh
git cat-file blob HEAD:docs/PREREG_LAB_S0.md > target
sha256sum target
# atteso: f0a22924a24fdd27f251d8da645664cc8fcf0e75607e2ca18388c4e1e41628d4
ots verify -f target docs/PREREG_LAB_S0.md.ots
```

### 5.2 I due JSON — si verificano applicando al blob la trasformazione LF→CRLF

Lo script `crlf.py` usato qui sotto è una riga sola, ed è la trasformazione
descritta al §3.1:

```python
import sys
b = sys.stdin.buffer.read()
sys.stdout.buffer.write(b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
```

```sh
# manifests/trader_v0_freeze_manifest.json
git cat-file blob HEAD:manifests/trader_v0_freeze_manifest.json | python crlf.py > target
sha256sum target
# atteso: 429186db0eabc30e5fbb55b5b402a59995d7756fb5eea33a251aa28a0f1b98e8
ots verify -f target manifests/trader_v0_freeze_manifest.json.ots

# MANIFEST_S0.json
git cat-file blob HEAD:MANIFEST_S0.json | python crlf.py > target
sha256sum target
# atteso: ced493a7b3ea36168d6b3c7a4fe7aa81bfada0bd318928dd2a6d552cb8c27275
ots verify -f target MANIFEST_S0.json.ots
```

**Due parti, due condizioni d'esecuzione.** Il confronto `sha256` è la parte
offline: si esegue sempre, senza rete, ed è quella eseguita in questo rito. Il
comando `ots verify` interroga la blockchain e richiede rete: si esegue fuori
dai riti a rete vietata. Un `sha256` che coincide dimostra che i byte
ricostruiti sono quelli timbrati; `ots verify` dimostra quando furono timbrati.

Se `sha256` coincide e `ots verify` fallisce, il problema è la prova Bitcoin,
non i byte. Se `sha256` non coincide, non si esegue `ots verify`: si è
ricostruito il file sbagliato.

---

## 6. Cosa questo documento decide, e cosa non tocca

La decisione dell'owner del 20/08/2026 è la **via (b)**: si annota, non si
riscrive. Le alternative erano due, e la scartata va detta per intero:

- **via (a), scartata**: ricommittare i due JSON con i fine-riga CRLF che
  furono timbrati, così da portare il blob a coincidere col digest. Avrebbe
  cambiato il blob sha di `manifests/trader_v0_freeze_manifest.json` (percorso
  di verdetto) e di `MANIFEST_S0.json` (manifesto degli hash del record di
  Stagione 0), cioè grandezze che altri documenti citano;
- **via (b), ratificata**: dichiarare quali byte sono timbrati, scrivere la
  ricetta che li ricostruisce da qualunque macchina, e lasciare la storia
  intatta.

I tre artefatti congelati e i loro `.ots` **non sono stati toccati** da questo
rito: non un byte, né nel working tree né nella storia.

**I timbri certificano gli stessi byte di contenuto; la storia si annota, non
si riscrive (decisione owner 20/08, via b).**

---

## 7. Regola per il futuro

Incisa anche in `CLAUDE.md`:

> Ogni timbro OTS si appone sui byte del **blob** (`git cat-file`), mai su una
> copia del working tree; ogni file da ancorare nasce coperto da
> `.gitattributes` **prima** dello stamp.

Le sedi ancorate — `docs/**` e `manifests/**` — sono coperte da `-text` in
`.gitattributes` a partire da questo rito: ogni file che vi nascerà d'ora in
poi si materializza in ogni clone con i byte del blob, e il caso qui
documentato non si ripete. I due artefatti congelati restano l'eccezione
dichiarata, con la ricetta del §5 al posto del confronto diretto.

`.gitattributes` porta anche sei eccezioni di eredità: documenti `docs/**`
pre-esistenti, **non ancorati**, committati con blob LF e presenti nel working
tree con CRLF. Sotto `-text` comparirebbero come modificati senza che nulla sia
cambiato. Nessun timbro è in gioco per loro; quando uno verrà riscritto con
fine-riga LF, la sua riga di eccezione va rimossa e il file torna sotto `-text`.
