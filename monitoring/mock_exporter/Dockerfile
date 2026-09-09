# Image du simulateur de métriques. Multi-étapes : les dépendances sont
# installées dans une couche isolée, l'image finale ne contient ni pip cache
# ni chaîne de compilation.

FROM python:3.11-slim AS build

WORKDIR /install
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/deps -r requirements.txt

FROM python:3.11-slim

# Exécution sans privilèges : exigence de M8, applicable dès maintenant.
RUN useradd --create-home --uid 10001 exporteur
USER exporteur

WORKDIR /app
COPY --from=build /install/deps /usr/local
COPY exporter.py .

ENV PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["python", "exporter.py"]
