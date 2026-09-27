from pyspark import pipelines as dp
from pyspark.sql.functions import col
from pathlib import Path
import importlib.util

datasets_dir = str(Path(importlib.util.find_spec("flight_analytics").origin).parents[2] / "datasets")


@dp.table(name="dev_flight_analytics.bronze.aircrafts", table_properties={"quality": "bronze"})
def load_aircrafts():
    aircrafts_dataset_path = f"{datasets_dir}/aircrafts.csv"
    df = spark.read.csv(aircrafts_dataset_path, header=True, inferSchema=True)
    return df


@dp.table(name="dev_flight_analytics.bronze.airlines", table_properties={"quality": "bronze"})
def load_airlines():
    airlines_dataset_path = f"{datasets_dir}/airlines.csv"
    df = spark.read.csv(airlines_dataset_path, header=True, inferSchema=True)
    return df


@dp.table(name="dev_flight_analytics.bronze.airports", table_properties={"quality": "bronze"})
def load_airports():
    airports_dataset_path = f"{datasets_dir}/airports.csv"
    df = spark.read.csv(airports_dataset_path, header=True, inferSchema=True)
    return df


@dp.table(name="dev_flight_analytics.bronze.passengers", table_properties={"quality": "bronze"})
def load_passengers():
    passengers_dataset_path = f"{datasets_dir}/passengers.csv"
    df = spark.read.csv(passengers_dataset_path, header=True, inferSchema=True)
    return df