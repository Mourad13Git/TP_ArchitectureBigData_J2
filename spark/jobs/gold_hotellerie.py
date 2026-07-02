"""Job Spark Gold — a executer sur le cluster (equiv. pandas local)."""
# Usage cluster: spark-submit spark/jobs/gold_hotellerie.py

from pyspark.sql import SparkSession


def main():
    spark = (
        SparkSession.builder.appName("bce_gold_hotellerie")
        .config("spark.mongodb.input.uri", "mongodb://localhost:27017/bce_ingestion.hotel_gold")
        .config("spark.mongodb.output.uri", "mongodb://localhost:27017/bce_ingestion.hotel_gold")
        .getOrCreate()
    )

    # Sur cluster: lire HDFS /data/bronze/nbb/csvs/{bce}/{year}/*.csv
    # Parser PCMN, calculer ratios, upsert hotel_gold via connector MongoDB
    # En local: preferer scripts/run_gold_pipeline.py (pandas)

    print("Spark Gold job — implementer parsing PCMN distribue sur le cluster.")
    print("Fallback local: python ingestion_bronze/scripts/run_gold_pipeline.py")
    spark.stop()


if __name__ == "__main__":
    main()
