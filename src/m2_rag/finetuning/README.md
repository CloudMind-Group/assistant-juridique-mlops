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
