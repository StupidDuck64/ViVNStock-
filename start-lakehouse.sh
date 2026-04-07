#!/bin/bash


# Chạy core profile

echo "Starting core services..."

docker compose --profile core up -d


# Chạy Airflow

echo "Starting Airflow..."

docker compose --profile airflow up -d


# Chạy exploration tools

echo "Starting exploration tools..."

docker compose --profile explore up -d


# Chạy realistic data generation

echo "Starting datagen..."

docker compose --profile datagen up -d


echo "All profiles started in detached mode."

