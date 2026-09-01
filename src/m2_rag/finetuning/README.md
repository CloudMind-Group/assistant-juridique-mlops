# Préparation LoRA / QLoRA

Ce dossier définit uniquement le contrat d'entrée d'un futur entraînement PEFT.
Aucun dataset QA annoté réel, entraînement, adaptateur ou poids de modèle n'est
présent dans le dépôt. Il est donc interdit de présenter M2 comme « fine-tuné ».

Chaque ligne JSONL doit contenir :

```json
{"question":"...","answer":"...","context":["passage sourcé"],"source_doc_ids":["doc-id-opaque"],"language":"fr"}
```

Avant tout entraînement réel, le dataset doit être annoté, revu juridiquement,
séparé en jeux train/validation/test et versionné par le processus convenu avec M1/M3.
Les poids et caches de modèles ne doivent jamais être commités.

**Not trained — annotated dataset unavailable.**

Validation JSONL et prévisualisation déterministe du split, sans écriture :

```bash
python -m src.m2_rag.finetuning.prepare annotated.jsonl --validation-ratio 0.1 --seed 42
```

`LoRAConfig` couvre modèle de base, rang, alpha, dropout, modules cibles,
learning rate, époques, batch et accumulation. `quantization_bits=4` ou `8`
active QLoRA. Le futur job d'entraînement GPU M3/M4 devra consommer ce contrat
après approbation du dataset ; aucun faux entraînement n'est livré ici.
