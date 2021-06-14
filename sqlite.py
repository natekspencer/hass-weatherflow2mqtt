import json
import sqlite3
import datetime
import time
import os.path
from datetime import timezone
from sqlite3 import Error as SQLError
from typing import OrderedDict
import logging

from const import (
    DATABASE,
    PRESSURE_TREND_TIMER,
    STORAGE_ID,
    STORAGE_FILE,
    STRIKE_COUNT_TIMER,
    TABLE_LIGHTNING,
    TABLE_PRESSURE,
    TABLE_STORAGE,
)

_LOGGER = logging.getLogger(__name__)


class SQLFunctions:
    """Class to handle SQLLite functions."""

    def __init__(self):
        self.connection = None

    async def create_connection(self, db_file):
        """ create a database connection to a SQLite database """
        try:
            self.connection = sqlite3.connect(db_file)

        except SQLError as e:
            _LOGGER.error("Could not create SQL Database. Error: %s", e)


    async def create_table(self, create_table_sql):
        """ create a table from the create_table_sql statement
        :param conn: Connection object
        :param create_table_sql: a CREATE TABLE statement
        :return:
        """
        try:
            c = self.connection.cursor()
            c.execute(create_table_sql)
        except SQLError as e:
            _LOGGER.error("Could not create SQL Table. Error: %s", e)

    async def create_storage_row(self, rowdata):
        """
        Create a new storage row into the storage table
        :param conn:
        :param rowdata:
        :return: project id
        """
        sql = '''   INSERT INTO storage(id, rain_today, rain_yesterday, rain_start, rain_duration_today,
                    rain_duration_yesterday, lightning_count, lightning_count_today, last_lightning_time,
                    last_lightning_distance, last_lightning_energy)
                    VALUES(?, ?,?,?,?,?,?,?,?,?,?) '''
        try:
            cur = self.connection.cursor()
            cur.execute(sql, rowdata)
            self.connection.commit()
            return cur.lastrowid
        except SQLError as e:
            _LOGGER.error("Could not Insert data in table storage. Error: %s", e)

    async def readStorage(self):
        """Returns data from the storage table as JSON."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"SELECT * FROM storage WHERE id = {STORAGE_ID};")
            data = cursor.fetchall()
            
            for row in data:
                storage_json = {
                    "rain_today": row[1],
                    "rain_yesterday": row[2],
                    "rain_start": row[3],
                    "rain_duration_today": row[4],
                    "rain_duration_yesterday": row[5],
                    "lightning_count": row[6],
                    "lightning_count_today": row[7],
                    "last_lightning_time": row[8],
                    "last_lightning_distance": row[9],
                    "last_lightning_energy": row[10],
                }

            return storage_json         

        except SQLError as e:
            _LOGGER.error("Could not access storage data. Error: %s", e)

    async def writeStorage(self, json_data: OrderedDict):
        """Stores data in the storage table from JSON."""

        try:
            cursor = self.connection.cursor()
            sql_statement = """UPDATE storage
                               SET  rain_today=?,
                                    rain_yesterday=?,
                                    rain_start=?,
                                    rain_duration_today=?,
                                    rain_duration_yesterday=?,
                                    lightning_count=?,
                                    lightning_count_today=?,
                                    last_lightning_time=?,
                                    last_lightning_distance=?,
                                    last_lightning_energy=?
                                WHERE ID = ?
                                """

            rowdata = (json_data["rain_today"],json_data["rain_yesterday"],json_data["rain_start"],json_data["rain_duration_today"],
                        json_data["rain_duration_yesterday"],json_data["lightning_count"],json_data["lightning_count_today"],
                        json_data["last_lightning_time"],json_data["last_lightning_distance"],json_data["last_lightning_energy"], 
                        STORAGE_ID)

            cursor.execute(sql_statement, rowdata)
            self.connection.commit()

        except SQLError as e:
            _LOGGER.error("Could not update storage data. Error: %s", e)

    async def readPressureTrend(self, new_pressure):
        """Returns the Pressure Trend."""
        try:
            time_point = time.time() - PRESSURE_TREND_TIMER
            cursor = self.connection.cursor()
            cursor.execute(f"SELECT pressure FROM pressure WHERE timestamp < {time_point} ORDER BY timestamp DESC LIMIT 1;")
            old_pressure = cursor.fetchone()
            if old_pressure is None:
                old_pressure = new_pressure
            else:
                old_pressure = float(old_pressure[0])
            pressure_delta = new_pressure - old_pressure
            return pressure_delta

        except SQLError as e:
            _LOGGER.error("Could not access storage data. Error: %s", e)

    async def readPressureData(self):
        """Returns the formatted pressure data."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"SELECT * FROM pressure;")
            data = cursor.fetchall()

            for row in data:
                tid = datetime.datetime.fromtimestamp(row[0]).isoformat()
                print(tid, row[1])

        except SQLError as e:
            _LOGGER.error("Could not access storage data. Error: %s", e)

    async def writePressure(self, pressure):
        """Adds an entry to the Pressure Table."""

        try:
            cur = self.connection.cursor()
            cur.execute(f"INSERT INTO pressure(timestamp, pressure) VALUES({time.time()}, {pressure});")
            self.connection.commit()
            return True
        except SQLError as e:
            _LOGGER.error("Could not Insert data in table Pressure. Error: %s", e)
            return False
        except Exception as e:
            _LOGGER.debug("Could write to Pressure Table. Error message: %s", e)
            return False

    async def readLightningCount(self):
        """Returns the number of Lightning Strikes in the last 3 hours."""
        try:
            time_point = time.time() - STRIKE_COUNT_TIMER
            cursor = self.connection.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM lightning WHERE timestamp > {time_point};")
            data = cursor.fetchone()[0]
            
            return data

        except SQLError as e:
            _LOGGER.error("Could not access storage data. Error: %s", e)

    async def writeLightning(self):
        """Adds an entry to the Lightning Table."""

        try:
            cur = self.connection.cursor()
            cur.execute(f"INSERT INTO lightning(timestamp) VALUES({time.time()});")
            self.connection.commit()
            return True
        except SQLError as e:
            _LOGGER.error("Could not Insert data in table Lightning. Error: %s", e)
            return False
        except Exception as e:
            _LOGGER.debug("Could write to Lightning Table. Error message: %s", e)
            return False

    async def migrateStorageFile(self):
        """Migrates the old .storage.json file to the database."""

        try:
            with open(STORAGE_FILE, "r") as jsonFile:
                old_data = json.load(jsonFile)
                
                # We need to convert the Rain Start to timestamp
                dt = datetime.datetime.strptime(old_data["rain_start"], "%Y-%m-%dT%H:%M:%S")
                timestamp = dt.replace(tzinfo=timezone.utc).timestamp()

                storage_json = {
                    "rain_today": old_data["rain_today"],
                    "rain_yesterday": old_data["rain_yesterday"],
                    "rain_start": timestamp,
                    "rain_duration_today": old_data["rain_duration_today"],
                    "rain_duration_yesterday": old_data["rain_duration_yesterday"],
                    "lightning_count": old_data["lightning_count"],
                    "lightning_count_today": old_data["lightning_count_today"],
                    "last_lightning_time": old_data["last_lightning_time"],
                    "last_lightning_distance": old_data["last_lightning_distance"],
                    "last_lightning_energy": old_data["last_lightning_energy"],
                }
                
                await self.writeStorage(storage_json)

        except FileNotFoundError as e:
            _LOGGER.debug("Could not find old storage file. Error message: %s", e)
        except Exception as e:
            _LOGGER.debug("Could not Read storage file. Error message: %s", e)

    async def createInitialDataset(self):
        """Setup the Initial database, and migrate data if needed."""

        try:
            with self.connection:
                # Create Empty Tables
                await self.create_table(TABLE_STORAGE)
                await self.create_table(TABLE_LIGHTNING)
                await self.create_table(TABLE_PRESSURE)

                # Store Initial Data
                storage = (STORAGE_ID,0,0,0,0,0,0,0,0,0,0)
                await self.create_storage_row(storage)

                # Migrate data if they exist
                if os.path.isfile(STORAGE_FILE):
                    await self.migrateStorageFile()

        except Exception as e:
            _LOGGER.debug("Could not Read storage file. Error message: %s", e)
