# Factures PDF et Claude

Ce projet transforme des factures PDF stockées sur Hyperfluid en données interrogeables
avec Claude : **PDF → Markdown/OCR → Parquet Silver → extraction Ollama → Parquet Gold → DuckDB → MCP**.

Les PDF du bucket `factures` constituent Bronze. Silver et Gold sont sauvegardés sur
Hyperfluid ; le serveur MCP interroge le Gold local.

## Installation

Prérequis : Python 3.12 et Ollama. Depuis le dossier du projet :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
sudo apt-get install -y tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng
```

Si Ollama n’est pas installé :

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Télécharger le modèle :

```bash
ollama pull qwen2.5:3b
```

Si `.env` n’existe pas encore :

```bash
cp .env.example .env
chmod 600 .env
```

Renseigner les clés S3 dans `.env`, puis vérifier l’accès :

```bash
python check_s3.py
```

Ne pas partager ni versionner `.env`.

## Exécuter le pipeline

```bash
# PDF du bucket → Markdown local (texte direct ou OCR)
python pdf_to_md.py

# Markdown → Silver
python markdown_to_parquet.py

# Tester l’extraction sur 3 factures
python extract_features.py --limit 3

# Extraire toutes les factures → Gold
python extract_features.py

# Interroger Gold avec DuckDB
python query_factures.py

# Envoyer Silver et Gold sur Hyperfluid et vérifier les fichiers
python sync_s3.py
```

Les sorties sont `silver/factures_md.parquet` et `gold/factures.parquet`.
L’extraction valide les champs et les totaux, réessaie les erreurs et reprend les résultats
valides depuis le cache. En cas d’échec, consulter `gold/extraction_report.json`.

Commandes complémentaires :

```bash
# Filtrer par fournisseur et dates d’émission incluses
python query_factures.py --fournisseur 'Le Gall' --debut 2026-03-01 --fin 2026-03-31

# Corriger les fournisseurs d’un Gold existant par rapprochement des SIRET
python normalize_suppliers.py

# Recalculer toutes les extractions, sans utiliser le cache
python extract_features.py --force
```

La normalisation des fournisseurs est aussi intégrée à l’extraction. Une correction de
la facture LG-2026-0009 est documentée dans `data/extractions/review_LG-2026-0009.json`.
`--force` recalcule également cette facture : une nouvelle vérification peut être nécessaire.

## Tester avec Claude Desktop

1. Ouvrir **Paramètres → Application de bureau → Extensions → Modifier la configuration**.
2. Ajouter l’entrée `factures` de `claude_desktop_config.example.json` dans `mcpServers`,
   en conservant les réglages existants. Adapter les chemins si le projet est déplacé.
3. Quitter complètement Claude (**Ctrl + Q**), puis le relancer.
4. Vérifier que `factures` apparaît **En cours** dans les serveurs MCP locaux.
5. Dans une nouvelle conversation, demander :

   > Utilise total_factures pour calculer le total TTC des factures émises du 1er au 30 novembre 2026.

   Résultat attendu : **5 factures, soit 34 898,57 € TTC**.

Pour tester l’autre outil :

> Utilise list_factures pour afficher les factures de novembre 2026.

Autoriser les outils si Claude le demande. Claude lance automatiquement `mcp_server.py` :
il n’est pas nécessaire de le démarrer dans un terminal. Cette configuration fonctionne
avec Claude Desktop sur la même machine, pas directement dans le navigateur.

Les totaux sont calculés par devise et date d’émission : ils ne représentent pas forcément
les paiements effectués. Vérifier quelques extractions par rapport aux PDF originaux.

## Tests techniques

```bash
python -m unittest discover -s tests -v
python test_mcp.py
```

Ces tests vérifient les montants, les filtres, la pagination et les appels au serveur MCP.
