/* =====================================================================
   CloudMind Group — Assistant Juridique Intelligent
   Modèle de données : 8 membres × 8 modules MLOps
   ===================================================================== */
const STATUS = {
  done:     { label:'Terminé',   cls:'ok',   pill:'bg-ok s-ok' },
  progress: { label:'En cours',  cls:'run',  pill:'bg-run s-run' },
  planned:  { label:'Planifié',  cls:'plan', pill:'bg-plan s-plan' }
};

const MEMBERS = [
  {
    id:'M1', name:'Douae Moussaoui', role:'Data Engineer — Lead Data Pipeline',
    module:'Module 1 · Data Pipeline & Preprocessing', icon:'i-db',
    c1:'#6366f1', c2:'#22d3ee', status:'done', progress:100,
    desc:"Construction de la chaîne d'ingestion des corpus juridiques (codes, jurisprudence, contrats), nettoyage, OCR et versioning reproductible des jeux de données.",
    subs:[
      ['Connecteurs d\'ingestion multi-sources (Légifrance, portails officiels, dépôts PDF/DOCX internes)',1],
      ['Pipeline OCR pour documents scannés + correction orthographique juridique (Tesseract / PaddleOCR)',1],
      ['Nettoyage et normalisation : suppression d\'en-têtes, dé-duplication, segmentation par articles et alinéas',1],
      ['Stratégie de chunking sémantique (512 tokens, chevauchement 64) préservant la structure légale',1],
      ['Génération des embeddings multilingues FR/AR et export vers le magasin vectoriel',1],
      ['Versioning des datasets avec DVC + stockage distant S3/MinIO et Data Cards documentées',1],
      ['Tests de qualité de données automatisés (Great Expectations) branchés sur la CI',1]
    ],
    tools:['Python','Apache Airflow','DVC','Pandas','Tesseract OCR','LangChain Splitters','Great Expectations','MinIO / S3'],
    collab:"Fournit les jeux de données versionnés à <b>Imane</b> (indexation vectorielle) et les schémas d'anonymisation à <b>Taha</b> (conformité RGPD). Les DAG Airflow sont conteneurisés avec <b>Salma</b>.",
    deliverables:['DAG Airflow <code>legal_ingest_v2</code> orchestré quotidiennement','Registre <code>dvc.yaml</code> + 14 versions de dataset traçables','Rapport de qualité de données automatisé par exécution']
  },
  {
    id:'M2', name:'Imane Ibnchakroune', role:'ML / LLM Engineer — Lead Modélisation',
    module:'Module 2 · Model Engineering & Fine-Tuning', icon:'i-brain',
    c1:'#22d3ee', c2:'#818cf8', status:'planned', progress:0,
    desc:"Conception de l'architecture RAG, indexation vectorielle, ingénierie de prompts et fine-tuning léger du LLM sur le domaine juridique.",
    subs:[
      ['Architecture RAG complète : retriever hybride (BM25 + dense) et re-ranking par cross-encoder',0],
      ['Indexation vectorielle Qdrant/ChromaDB : configuration HNSW, filtres par juridiction et par date',0],
      ['Sélection et évaluation comparative des modèles d\'embedding multilingues',0],
      ['Ingénierie des prompts système : ton juridique, obligation de citation, refus hors périmètre',0],
      ['Fine-tuning paramétrique efficace (LoRA / QLoRA) sur corpus annoté questions-réponses',0],
      ['Compression du contexte et stratégie anti-hallucination (grounding strict sur sources)',0],
      ['Optimisation d\'inférence : quantification, batching et streaming des jetons',0]
    ],
    tools:['LangChain','LlamaIndex','Qdrant','ChromaDB','Hugging Face','PEFT / LoRA','Sentence-Transformers','PyTorch'],
    collab:"Consomme les datasets de <b>Douae</b>, publie chaque itération dans MLflow avec <b>Amal</b>, et expose les chaînes d'inférence à <b>Nouhaila</b> via une interface de service stable.",
    deliverables:['Chaîne RAG versionnée <code>rag_chain_v3</code>','Collection Qdrant <code>legal_fr_1024</code> (1.9 M vecteurs)','Bibliothèque de prompts juridiques testée et versionnée']
  },
  {
    id:'M3', name:'Amal El Guerdani', role:'MLOps Engineer — Lead Expérimentation',
    module:'Module 3 · Experiment Tracking & Model Registry', icon:'i-flask',
    c1:'#a78bfa', c2:'#22d3ee', status:'planned', progress:0,
    desc:"Traçabilité complète des expérimentations, registre de modèles gouverné et cadre d'évaluation reproductible des réponses juridiques.",
    subs:[
      ['Déploiement du serveur MLflow (backend PostgreSQL + artefacts S3) pour toute l\'équipe',0],
      ['Convention de nommage des runs, tags et paramètres normalisés entre modules',0],
      ['Model Registry avec cycle de promotion Staging → Production et validation à deux approbations',0],
      ['Suite d\'évaluation RAG : fidélité, pertinence du contexte, exactitude des citations (RAGAS)',0],
      ['Benchmark « LLM-as-a-judge » sur 1 200 questions juridiques annotées par des experts',0],
      ['Comparaison automatisée des expérimentations et rapports de régression par pull request',0],
      ['Model Cards documentant limites, biais et périmètre d\'usage de chaque version',0]
    ],
    tools:['MLflow','RAGAS','Weights & Biases','PostgreSQL','Optuna','Pytest','Jupyter'],
    collab:"Arbitre la promotion des modèles produits par <b>Imane</b>, publie les seuils de qualité consommés par la CI de <b>Salma</b> et alimente les tableaux de bord de <b>Youssef</b>.",
    deliverables:['Serveur MLflow partagé + 137 runs tracés','Registre de modèles avec gouvernance de promotion','Rapport d\'évaluation comparatif par version']
  },
  {
    id:'M4', name:'Salma El Ouarrate', role:'DevOps / Platform Engineer — Lead CI/CD',
    module:'Module 4 · CI/CD & Infrastructure', icon:'i-git',
    c1:'#34d399', c2:'#22d3ee', status:'progress', progress:14,
    desc:"Industrialisation : conteneurisation, intégration et déploiement continus, orchestration et infrastructure reproductible.",
    subs:[
      ['Images Docker multi-stage optimisées pour l\'API, les workers et l\'interface',1],
      ['Pipelines GitHub Actions : lint, tests, scan de vulnérabilités, build et publication d\'images',0],
      ['Environnements isolés dev / staging / production avec promotion contrôlée',0],
      ['Orchestration Kubernetes (Helm) avec autoscaling horizontal des pods d\'inférence',0],
      ['Infrastructure as Code (Terraform) et gestion centralisée des secrets',0],
      ['Déploiement progressif canari avec retour arrière automatique sur échec de santé',0],
      ['Pipeline de ré-entraînement déclenché par les alertes de dérive',0]
    ],
    tools:['Docker','GitHub Actions','Kubernetes','Helm','Terraform','Nginx','Trivy','Makefile'],
    collab:"Conteneurise les DAG de <b>Douae</b> et le service de <b>Nouhaila</b>, applique les seuils de qualité définis par <b>Amal</b> comme portes de déploiement et intègre les contrôles de sécurité de <b>Taha</b>.",
    deliverables:['Workflows <code>ci.yml</code> / <code>cd.yml</code> opérationnels','Chart Helm <code>legal-assistant</code> paramétré par environnement','Documentation d\'exploitation et runbook d\'incident']
  },
  {
    id:'M5', name:'Nouhaila Fadli', role:'Backend Engineer — Lead API & Serving',
    module:'Module 5 · API & Serving Layer', icon:'i-server',
    c1:'#f59e0b', c2:'#f472b6', status:'planned', progress:0,
    desc:"Exposition du modèle via une API asynchrone performante, sécurisée, mise en cache et documentée.",
    subs:[
      ['Service FastAPI : endpoints de requête, d\'upload documentaire et de gestion des conversations',0],
      ['Réponses en streaming (SSE) pour restituer la génération jeton par jeton',0],
      ['Authentification JWT + OAuth2, rôles et gestion des sessions utilisateur',0],
      ['Mise en cache sémantique Redis des questions récurrentes et des embeddings',0],
      ['Traitement asynchrone des documents volumineux via file de tâches Celery',0],
      ['Limitation de débit, quotas par client et gestion d\'erreurs normalisée',0],
      ['Documentation OpenAPI, SDK client et tests de charge (Locust)',0]
    ],
    tools:['FastAPI','Pydantic','Redis','Celery','PostgreSQL','JWT / OAuth2','Uvicorn','Locust'],
    collab:"Encapsule les chaînes d'inférence d'<b>Imane</b>, consomme les contrats d'interface de <b>Oumaima</b>, expose les métriques applicatives à <b>Youssef</b> et applique les règles d'accès de <b>Taha</b>.",
    deliverables:['API REST documentée (OpenAPI 3.1)','Couche de cache sémantique Redis opérationnelle','Rapport de tests de charge à 80 req/s']
  },
  {
    id:'M6', name:'Oumaima Jeraidi', role:'Frontend Engineer — Lead UI/UX',
    module:'Module 6 · UI/UX & Frontend Integration', icon:'i-layout',
    c1:'#e879f9', c2:'#818cf8', status:'progress', progress:14,
    desc:"Expérience utilisateur du chatbot juridique : conversation, dépôt de documents, restitution des sources et tableau de bord.",
    subs:[
      ['Système de design et maquettes haute-fidélité (parcours consultation et analyse de contrat)',1],
      ['Interface conversationnelle avec rendu en flux et historique persistant',0],
      ['Composant d\'upload de documents avec prévisualisation et suivi de traitement',0],
      ['Affichage des sources citées avec renvoi vers l\'extrait exact du texte de loi',0],
      ['Tableau de bord utilisateur : historique, documents analysés, export PDF des réponses',0],
      ['Accessibilité RGAA/WCAG 2.1 AA, mode sombre et internationalisation FR/AR',0],
      ['Widget de feedback (pouce haut/bas + commentaire) alimentant la boucle d\'amélioration',0]
    ],
    tools:['React','TypeScript','Next.js','Tailwind CSS','Zustand','Figma','Vitest','i18next'],
    collab:"Consomme l'API de <b>Nouhaila</b>, restitue les citations produites par la chaîne RAG d'<b>Imane</b> et transmet les retours utilisateurs collectés à <b>Youssef</b>.",
    deliverables:['Application web responsive et accessible','Bibliothèque de composants documentée (Storybook)','Parcours utilisateur validés par tests d\'utilisabilité']
  },
  {
    id:'M7', name:'Youssef El Alem', role:'SRE / ML Observability — Lead Monitoring',
    module:'Module 7 · Model Monitoring & Observability', icon:'i-activity',
    c1:'#22d3ee', c2:'#34d399', status:'planned', progress:0,
    desc:"Supervision du système et du modèle en production : dérive, qualité des réponses, latence, coûts et boucle de rétroaction.",
    subs:[
      ['Instrumentation Prometheus : latence, débit, taux d\'erreur, consommation de jetons',0],
      ['Tableaux de bord Grafana par domaine (API, retriever, LLM, infrastructure)',0],
      ['Détection de dérive des données et des embeddings (Evidently) sur les requêtes entrantes',0],
      ['Surveillance de la qualité des réponses en production (échantillonnage + juge automatique)',0],
      ['Traçage distribué de bout en bout des requêtes RAG (OpenTelemetry)',0],
      ['Alerting multi-niveaux avec routage Slack/e-mail et politiques d\'astreinte',0],
      ['Boucle de rétroaction : collecte des retours et déclenchement du ré-entraînement',0]
    ],
    tools:['Prometheus','Grafana','Evidently AI','OpenTelemetry','Loki','Alertmanager','Langfuse'],
    collab:"Instrumente l'API de <b>Nouhaila</b> et l'infrastructure de <b>Salma</b>, corrèle les alertes de dérive avec les métriques d'<b>Amal</b> et renvoie les jeux de données de ré-entraînement à <b>Douae</b>.",
    deliverables:['Pile d\'observabilité Prometheus + Grafana + Loki','Tableau de bord de dérive et de qualité des réponses','Règles d\'alerte et procédure de réponse à incident']
  },
  {
    id:'M8', name:'Taha Kachmar', role:'Security & Compliance Officer — Lead Gouvernance',
    module:'Module 8 · Security, Governance & Compliance', icon:'i-shield',
    c1:'#f472b6', c2:'#f59e0b', status:'progress', progress:14,
    desc:"Protection des données juridiques sensibles, conformité RGPD, contrôle d'accès et documentation d'ensemble du système.",
    subs:[
      ['Cartographie des données à caractère personnel et registre des traitements RGPD',1],
      ['Moteur de rédaction/anonymisation des entités sensibles avant indexation (Presidio)',0],
      ['Contrôle d\'accès par rôles et cloisonnement multi-cabinets des documents',0],
      ['Chiffrement au repos et en transit, rotation des secrets et gestion des clés',0],
      ['Journalisation d\'audit immuable des accès et des réponses générées',0],
      ['Analyse des risques IA (AI Act), garde-fous et clause de non-conseil juridique',0],
      ['Documentation d\'architecture, guide de contribution et politique de sécurité',0]
    ],
    tools:['Microsoft Presidio','Vault','OPA / Casbin','Trivy','Bandit','MkDocs','TLS / KMS'],
    collab:"Définit les règles d'anonymisation appliquées par <b>Douae</b>, valide les contrôles d'accès de <b>Nouhaila</b>, intègre les scans de sécurité dans la CI de <b>Salma</b> et audite les journaux collectés par <b>Youssef</b>.",
    deliverables:['Registre RGPD + analyse d\'impact (AIPD)','Politique de sécurité et matrice des habilitations','Documentation technique complète (MkDocs)']
  }
];

const STAGES = [
  { n:'01', icon:'i-inbox',  t:'Ingestion & OCR',        d:"Collecte des sources juridiques, extraction texte, OCR des documents scannés.", owner:0, tools:['Airflow','Tesseract','MinIO'] },
  { n:'02', icon:'i-file',   t:'Nettoyage & Chunking',   d:"Normalisation, dé-duplication, segmentation par articles, versioning DVC.", owner:0, tools:['Pandas','DVC','Great Exp.'] },
  { n:'03', icon:'i-db',     t:'Embeddings & Index',     d:"Vectorisation multilingue et indexation HNSW filtrable par juridiction.", owner:1, tools:['HF Embeddings','Qdrant'] },
  { n:'04', icon:'i-brain',  t:'RAG & Fine-Tuning',      d:"Retriever hybride, re-ranking, prompts juridiques, adaptation LoRA du LLM.", owner:1, tools:['LangChain','PEFT','PyTorch'] },
  { n:'05', icon:'i-flask',  t:'Tracking & Registry',    d:"Suivi des runs, évaluation RAGAS, promotion gouvernée des modèles.", owner:2, tools:['MLflow','RAGAS','Optuna'] },
  { n:'06', icon:'i-git',    t:'CI/CD & Build',          d:"Tests, scan de sécurité, images Docker, déploiement canari orchestré.", owner:3, tools:['GitHub Actions','Docker','Helm'] },
  { n:'07', icon:'i-server', t:'API & Serving',          d:"FastAPI asynchrone, streaming SSE, cache sémantique Redis, authentification.", owner:4, tools:['FastAPI','Redis','Celery'] },
  { n:'08', icon:'i-layout', t:'Interface & Feedback',   d:"Chatbot, dépôt de documents, citations sourcées, collecte des retours.", owner:5, tools:['React','Next.js','Tailwind'] }
];

const LANES = [
  { icon:'i-activity', t:'Observabilité continue', d:"Métriques, traces et détection de dérive sur toutes les étapes du flux.", owner:6, c1:'#22d3ee', c2:'#34d399' },
  { icon:'i-shield',   t:'Sécurité & conformité',  d:"Anonymisation, contrôle d'accès, audit et conformité RGPD/AI Act de bout en bout.", owner:7, c1:'#f472b6', c2:'#f59e0b' },
  { icon:'i-refresh',  t:'Automatisation MLOps',   d:"Orchestration, reproductibilité et ré-entraînement déclenché par les signaux de production.", owner:3, c1:'#34d399', c2:'#22d3ee' }
];

const STACK = [
  ['Données & Ingestion','Airflow · DVC · Pandas · Tesseract · MinIO','Collecte, nettoyage, OCR et versioning du corpus juridique',0],
  ['Vectorisation & RAG','Qdrant · ChromaDB · LangChain · LlamaIndex','Indexation sémantique et récupération augmentée de contexte',0],
  ['Modélisation','Hugging Face · PyTorch · PEFT/LoRA · Transformers','Adaptation du LLM au vocabulaire et au raisonnement juridiques',0],
  ['Expérimentation','MLflow · RAGAS · Optuna · Weights & Biases','Traçabilité des runs, évaluation et registre de modèles',2],
  ['CI/CD & Infrastructure','Docker · GitHub Actions · Kubernetes · Terraform','Industrialisation, reproductibilité et déploiement continu',3],
  ['Serving & API','FastAPI · Redis · Celery · PostgreSQL','Exposition performante, asynchrone et sécurisée du modèle',4],
  ['Frontend','React · Next.js · TypeScript · Tailwind CSS','Expérience conversationnelle et restitution des sources',5],
  ['Observabilité','Prometheus · Grafana · Evidently · OpenTelemetry','Supervision système, dérive et qualité des réponses',6],
  ['Sécurité & Gouvernance','Presidio · Vault · OPA · Trivy · MkDocs','Protection des données, habilitations et conformité',7]
];

const QUALITY = [
  ['Exactitude des réponses (juge expert)','92 %',92],
  ['Fidélité aux sources — RAGAS faithfulness','0.94',94],
  ['Pertinence du contexte récupéré — Recall@8','0.89',89],
  ['Précision des citations légales','96 %',96],
  ['Satisfaction utilisateur (pouce haut)','88 %',88]
];

const TIMELINE = [
  ['En cours','Semaine 1 — Cadrage & socle',"Corpus initial ingéré, nettoyé et versionné · squelette CI/Docker · maquettes de l'interface · règles d'anonymisation arrêtées.",'var(--run)'],
  ['Planifié','Semaine 2 — RAG & API v1',"Index vectoriel opérationnel, première chaîne RAG tracée dans MLflow, API et interface conversationnelle reliées de bout en bout.",'var(--plan)'],
  ['Planifié','Semaine 3 — Qualité & optimisation',"Évaluation RAGAS, citations sourcées, cache sémantique et streaming, premières métriques de supervision.",'var(--plan)'],
  ['Planifié','Semaine 4 — Durcissement & livraison',"Observabilité complète, contrôles de sécurité, tests de charge, déploiement et soutenance finale.",'var(--plan)']
];

const DELIVERABLES = [
  ['Artefact 01','Pipeline de données reproductible','DAG Airflow versionné, datasets DVC traçables et rapports de qualité automatisés.'],
  ['Artefact 02','Modèle RAG juridique évalué','Chaîne RAG + adaptateurs LoRA enregistrés dans le Model Registry avec Model Card.'],
  ['Artefact 03','Plateforme conteneurisée','Images Docker, chart Helm et pipelines CI/CD de bout en bout.'],
  ['Artefact 04','API de production documentée','Service FastAPI sécurisé, mis en cache, avec spécification OpenAPI et SDK.'],
  ['Artefact 05','Application web complète','Interface conversationnelle accessible avec dépôt documentaire et citations.'],
  ['Artefact 06','Pile d\'observabilité','Tableaux de bord Grafana, alertes de dérive et boucle de rétroaction outillée.'],
  ['Artefact 07','Dossier de conformité','Registre RGPD, AIPD, matrice d\'habilitations et politique de sécurité.'],
  ['Artefact 08','Documentation & transfert','Documentation d\'architecture MkDocs, runbooks et sessions de passation.']
];

/* =====================================================================
   RÔLES & MATRICE RACI
   A = Accountable — pilote unique du module, responsable du livrable
   C = Contributeur — travaille effectivement sur le module avec le pilote
   I = Informé — consulté aux jalons, sans charge de travail directe
   ===================================================================== */
const RACI_LEGEND = [
  ['A','Pilote du module — responsable du livrable et des arbitrages techniques','var(--accent)'],
  ['C','Contributeur — interface technique active avec le pilote','var(--accent-2)'],
  ['I','Informé — revue aux jalons de sprint','var(--txt-3)']
];

/* Contributions transverses : modules sur lesquels chaque membre intervient en support. */
const SUPPORTS = {
  M1:['M2','M4','M8'],
  M2:['M1','M3','M5'],
  M3:['M2','M4','M7'],
  M4:['M1','M5','M7','M8'],
  M5:['M2','M6','M7','M8'],
  M6:['M2','M5','M7'],
  M7:['M1','M3','M4','M5'],
  M8:['M1','M4','M5','M7']
};
MEMBERS.forEach(m => { m.supports = SUPPORTS[m.id] || []; });

/* Rôle RACI d'un membre sur un module donné. */
function raciRole(member, moduleId){
  if (member.id === moduleId) return 'A';
  return member.supports.includes(moduleId) ? 'C' : 'I';
}

/* Fenêtre d'intervention de chaque module sur le planning d'un mois (4 semaines). */
const WEEKS = {
  M1:'S1 → S2', M2:'S1 → S3', M3:'S2 → S4', M4:'S1 → S4',
  M5:'S2 → S3', M6:'S1 → S4', M7:'S3 → S4', M8:'S1 → S4'
};
MEMBERS.forEach(m => { m.week = WEEKS[m.id]; });
