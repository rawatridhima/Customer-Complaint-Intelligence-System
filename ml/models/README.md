# Model artifacts

Trained weights are **not in Git**. They are hundreds of MB, and this folder's
contents are git-ignored except for this README and `.gitkeep`.

Without them the application still runs: the Celery worker falls back to the
rule-based stub classifier and predictions show model version `stub-v0`. For a
real demo, the classifier weights must be in place.

## What goes here

The backend looks for the classifier at `ml/models/distilbert-v1-512/`
(`CLASSIFIER_DIR_NAME` in `backend/app/services/classifier_service.py`).
Docker mounts `ml/models/` into the worker at `/models` (`MODEL_DIR`).

```
ml/models/
  distilbert-v1-512/
    config.json
    model.safetensors
    tokenizer.json
    tokenizer_config.json
    special_tokens_map.json
    vocab.txt
    labels.json          # category order; must match the training label mapping
    metrics.json         # val/test macro-F1, max_length, mapping version
```

`labels.json` is required. The worker reads it to map output indices to
categories, and fails over to the stub if it is missing.

The sentiment model (`cardiffnlp/twitter-roberta-base-sentiment-latest`) is
**not** stored here. It is pretrained and downloads from Hugging Face on the
worker's first start, cached in the `hf_cache` Docker volume. The first start
needs internet access and takes a minute or two.

## Getting the classifier

### Option A — download the trained model

1. Download `distilbert-v1-512.zip` from: **<ADD SHARED LINK HERE>**
2. Unzip it so that the folder sits at `ml/models/distilbert-v1-512/` with the
   files listed above directly inside it (not nested one level deeper).
3. Restart the worker: `docker compose restart worker`

### Option B — train it yourself

About an hour on a Colab T4. From `ml/src/`, after preparing the data (see the
root README):

```bash
python train_transformer.py --data-dir ../data --max-length 512 --batch-size 16 \
    --out ../models/distilbert-v1-512
```

Pass `--out` explicitly: the script's default is `../models/distilbert-v1`, which
the backend will not find.

## Checking it loaded

```bash
docker compose logs worker | grep -E "loaded classifier|using stub"
```

- `loaded classifier distilbert-v1-512` means the real model is in use.
- `classifier model not found at /models/distilbert-v1-512, using stub` means the
  folder is missing or misnamed.
- `could not load classifier ... using stub` followed by a traceback means the
  folder exists but a file is missing or corrupt.

Submitted complaints should then show `model_version` `distilbert-v1-512`
instead of `stub-v0`.

## Versioning

The folder name is the model version recorded against every prediction (FR-43).
A retrained model gets a new folder name, and `CLASSIFIER_DIR_NAME` is updated in
the same PR. Changing `ml/src/label_mapping.py` invalidates every trained model.
