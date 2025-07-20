import sys
import sqlite3
import time
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QTabWidget, QFormLayout, QComboBox, QMessageBox, QHeaderView,
    QDialog, QDialogButtonBox, QFileDialog
)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
import numpy as np # Ensure numpy is imported for consistency score calculation
import csv # Import csv module for CSV writing
import os # Import os module for path manipulation
import math # Import math for ceil function

# Helper function to format seconds into MM:SS.mmm
def format_seconds_to_mm_ss_mmm(total_seconds):
    if total_seconds is None or total_seconds < 0 or math.isinf(total_seconds):
        return "-"
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    milliseconds = int((total_seconds - int(total_seconds)) * 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

# --- Database Manager ---
class DatabaseManager:
    """
    Manages all interactions with the SQLite database for the RC Scoring App.
    Handles table creation and CRUD operations for drivers, cars, classes,
    events, races, lap data, and race results.
    """
    def __init__(self, db_name="rc_scoring.db"):
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Establishes a connection to the SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()
            print(f"Connected to database: {self.db_name}")
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            QMessageBox.critical(None, "Database Error", f"Could not connect to database: {e}")
            sys.exit(1) # Exit if database connection fails

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")

    def create_tables(self):
        """
        Creates necessary tables in the database if they do not already exist.
        Includes tables for Drivers, Cars, Classes, Events, Races, LapData,
        RaceResults, and AdjustmentsLog.
        """
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS Drivers (
                    driver_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    nickname TEXT,
                    contact_info TEXT,
                    country TEXT,
                    skill_level TEXT,
                    permanent_number TEXT
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS Classes (
                    class_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    ruleset TEXT,
                    color_code TEXT
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS Cars (
                    car_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    driver_id INTEGER NOT NULL,
                    class_id INTEGER NOT NULL,
                    car_name TEXT,
                    transponder_id TEXT UNIQUE, -- Unique ID for transponder (manual input here)
                    manufacturer TEXT,
                    model TEXT,
                    setup_notes TEXT,
                    FOREIGN KEY (driver_id) REFERENCES Drivers(driver_id),
                    FOREIGN KEY (class_id) REFERENCES Classes(class_id)
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS Events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    date TEXT,
                    location TEXT
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS Races (
                    race_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    race_type TEXT NOT NULL, -- e.g., Practice, Qualifier, Main
                    round_number INTEGER,
                    heat_number INTEGER,
                    duration_seconds INTEGER, -- Total duration in seconds
                    start_time TEXT,
                    end_time TEXT,
                    is_active BOOLEAN DEFAULT 0,
                    FOREIGN KEY (event_id) REFERENCES Events(event_id)
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS RaceParticipants (
                    participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    race_id INTEGER NOT NULL,
                    car_id INTEGER NOT NULL,
                    start_position INTEGER,
                    FOREIGN KEY (race_id) REFERENCES Races(race_id),
                    FOREIGN KEY (car_id) REFERENCES Cars(car_id)
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS LapData (
                    lap_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    race_id INTEGER NOT NULL,
                    car_id INTEGER NOT NULL,
                    lap_number INTEGER NOT NULL,
                    lap_time REAL NOT NULL, -- Time for this specific lap
                    timestamp TEXT NOT NULL, -- When the lap was recorded
                    FOREIGN KEY (race_id) REFERENCES Races(race_id),
                    FOREIGN KEY (car_id) REFERENCES Cars(car_id)
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS RaceResults (
                    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    race_id INTEGER NOT NULL,
                    car_id INTEGER NOT NULL,
                    final_position INTEGER,
                    total_laps INTEGER,
                    total_time REAL,
                    fastest_lap_time REAL,
                    points_earned REAL,
                    consistency_score REAL,
                    FOREIGN KEY (race_id) REFERENCES Races(race_id),
                    FOREIGN KEY (car_id) REFERENCES Cars(car_id)
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS AdjustmentsLog (
                    adjustment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    field_name TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    timestamp TEXT NOT NULL,
                    reason TEXT,
                    adjusted_by TEXT
                )
            ''')
            self.conn.commit()
            print("Tables created successfully or already exist.")
        except sqlite3.Error as e:
            print(f"Error creating tables: {e}")
            QMessageBox.critical(None, "Database Error", f"Error creating tables: {e}")

    # --- CRUD operations for Drivers ---
    def add_driver(self, name, nickname="", contact_info="", country="", skill_level="", permanent_number=""):
        """Adds a new driver to the Drivers table."""
        try:
            self.cursor.execute('''
                INSERT INTO Drivers (name, nickname, contact_info, country, skill_level, permanent_number)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, nickname, contact_info, country, skill_level, permanent_number))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            QMessageBox.warning(None, "Input Error", f"Driver '{name}' already exists.")
            return None
        except sqlite3.Error as e:
            print(f"Error adding driver: {e}")
            QMessageBox.critical(None, "Database Error", f"Error adding driver: {e}")
            return None

    def get_drivers(self):
        """Retrieves all drivers from the Drivers table."""
        self.cursor.execute("SELECT driver_id, name FROM Drivers ORDER BY name")
        return self.cursor.fetchall()

    def get_driver_details(self, driver_id):
        """Retrieves details for a specific driver."""
        self.cursor.execute("SELECT * FROM Drivers WHERE driver_id = ?", (driver_id,))
        return self.cursor.fetchone()

    # --- CRUD operations for Classes ---
    def add_class(self, name, ruleset="", color_code=""):
        """Adds a new class to the Classes table."""
        try:
            self.cursor.execute('''
                INSERT INTO Classes (name, ruleset, color_code)
                VALUES (?, ?, ?)
            ''', (name, ruleset, color_code))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            QMessageBox.warning(None, "Input Error", f"Class '{name}' already exists.")
            return None
        except sqlite3.Error as e:
            print(f"Error adding class: {e}")
            QMessageBox.critical(None, "Database Error", f"Error adding class: {e}")
            return None

    def get_classes(self):
        """Retrieves all classes from the Classes table."""
        self.cursor.execute("SELECT class_id, name FROM Classes ORDER BY name")
        return self.cursor.fetchall()

    # --- CRUD operations for Cars ---
    def add_car(self, driver_id, class_id, car_name, transponder_id, manufacturer="", model="", setup_notes=""):
        """Adds a new car to the Cars table."""
        try:
            self.cursor.execute('''
                INSERT INTO Cars (driver_id, class_id, car_name, transponder_id, manufacturer, model, setup_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (driver_id, class_id, car_name, transponder_id, manufacturer, model, setup_notes))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            QMessageBox.warning(None, "Input Error", f"Transponder ID '{transponder_id}' already registered for another car.")
            return None
        except sqlite3.Error as e:
            print(f"Error adding car: {e}")
            QMessageBox.critical(None, "Database Error", f"Error adding car: {e}")
            return None

    def get_cars(self):
        """Retrieves all cars with their associated driver and class names."""
        self.cursor.execute('''
            SELECT
                c.car_id,
                c.car_name,
                d.name AS driver_name,
                cl.name AS class_name,
                c.transponder_id
            FROM Cars c
            JOIN Drivers d ON c.driver_id = d.driver_id
            JOIN Classes cl ON c.class_id = cl.class_id
            ORDER BY d.name, c.car_name
        ''')
        return self.cursor.fetchall()

    def get_car_by_transponder(self, transponder_id):
        """Retrieves car details by transponder ID."""
        self.cursor.execute('''
            SELECT
                c.car_id,
                c.car_name,
                d.name AS driver_name,
                cl.name AS class_name
            FROM Cars c
            JOIN Drivers d ON c.driver_id = d.driver_id
            JOIN Classes cl ON c.class_id = cl.class_id
            WHERE c.transponder_id = ?
        ''', (transponder_id,))
        return self.cursor.fetchone()

    # --- Race Management ---
    def add_event(self, name, date, location=""):
        """Adds a new event."""
        try:
            self.cursor.execute('''
                INSERT INTO Events (name, date, location)
                VALUES (?, ?, ?)
            ''', (name, date, location))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error adding event: {e}")
            QMessageBox.critical(None, "Database Error", f"Error adding event: {e}")
            return None

    def get_events(self):
        """Retrieves all events."""
        self.cursor.execute("SELECT event_id, name, date FROM Events ORDER BY date DESC")
        return self.cursor.fetchall()

    def add_race(self, event_id, race_type, duration_seconds, round_number=None, heat_number=None):
        """Adds a new race within an event."""
        try:
            self.cursor.execute('''
                INSERT INTO Races (event_id, race_type, duration_seconds, round_number, heat_number, is_active)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (event_id, race_type, duration_seconds, round_number, heat_number))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error adding race: {e}")
            QMessageBox.critical(None, "Database Error", f"Error adding race: {e}")
            return None

    def get_races(self, event_id=None):
        """Retrieves races, optionally filtered by event_id."""
        query = '''
            SELECT
                r.race_id,
                e.name AS event_name,
                r.race_type,
                r.round_number,
                r.heat_number,
                r.duration_seconds,
                r.is_active
            FROM Races r
            JOIN Events e ON r.event_id = e.event_id
        '''
        params = []
        if event_id:
            query += " WHERE r.event_id = ?"
            params.append(event_id)
        query += " ORDER BY e.date DESC, r.race_id DESC"
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def set_race_active_status(self, race_id, is_active, start_time=None, end_time=None):
        """Sets the active status of a race and its start/end times."""
        try:
            if is_active:
                self.cursor.execute("UPDATE Races SET is_active = ?, start_time = ? WHERE race_id = ?",
                                    (1, start_time, race_id))
            else:
                self.cursor.execute("UPDATE Races SET is_active = ?, end_time = ? WHERE race_id = ?",
                                    (0, end_time, race_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating race active status: {e}")
            QMessageBox.critical(None, "Database Error", f"Error updating race status: {e}")
            return False

    def get_race_details(self, race_id):
        """Retrieves details for a specific race."""
        self.cursor.execute("SELECT * FROM Races WHERE race_id = ?", (race_id,))
        return self.cursor.fetchone()

    def add_race_participant(self, race_id, car_id, start_position=None):
        """Adds a car as a participant to a specific race."""
        try:
            self.cursor.execute('''
                INSERT INTO RaceParticipants (race_id, car_id, start_position)
                VALUES (?, ?, ?)
            ''', (race_id, car_id, start_position))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            QMessageBox.warning(None, "Input Error", "Car is already a participant in this race.")
            return None
        except sqlite3.Error as e:
            print(f"Error adding race participant: {e}")
            QMessageBox.critical(None, "Database Error", f"Error adding participant: {e}")
            return None

    def get_race_participants(self, race_id):
        """
        Retrieves all participants for a given race, including car and driver details.
        Ordered by start_position if available, otherwise by driver name.
        """
        self.cursor.execute('''
            SELECT
                rp.car_id,
                c.transponder_id,
                c.car_name,
                d.name AS driver_name,
                cl.name AS class_name,
                rp.start_position
            FROM RaceParticipants rp
            JOIN Cars c ON rp.car_id = c.car_id
            JOIN Drivers d ON c.driver_id = d.driver_id
            JOIN Classes cl ON c.class_id = cl.class_id
            WHERE rp.race_id = ?
            ORDER BY rp.start_position ASC, d.name ASC
        ''', (race_id,))
        return self.cursor.fetchall()

    # --- Lap Data ---
    def record_lap(self, race_id, car_id, lap_number, lap_time, timestamp):
        """Records a single lap for a car in a race."""
        try:
            self.cursor.execute('''
                INSERT INTO LapData (race_id, car_id, lap_number, lap_time, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (race_id, car_id, lap_number, lap_time, timestamp))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error recording lap: {e}")
            QMessageBox.critical(None, "Database Error", f"Error recording lap: {e}")
            return None

    def get_laps_for_car_in_race(self, race_id, car_id):
        """Retrieves all laps for a specific car in a specific race."""
        self.cursor.execute('''
            SELECT lap_number, lap_time, timestamp
            FROM LapData
            WHERE race_id = ? AND car_id = ?
            ORDER BY lap_number ASC
        ''', (race_id, car_id))
        return self.cursor.fetchall()

    def get_all_laps_for_race(self, race_id):
        """
        Retrieves all laps for all cars in a specific race,
        including driver name and car name.
        """
        self.cursor.execute('''
            SELECT
                ld.lap_id,
                ld.race_id,
                ld.car_id,
                c.transponder_id,
                d.name AS driver_name,
                c.car_name,
                ld.lap_number,
                ld.lap_time,
                ld.timestamp
            FROM LapData ld
            JOIN Cars c ON ld.car_id = c.car_id
            JOIN Drivers d ON c.driver_id = d.driver_id
            WHERE ld.race_id = ?
            ORDER BY ld.timestamp ASC, d.name ASC, ld.lap_number ASC
        ''', (race_id,))
        return self.cursor.fetchall()

    # --- Race Results ---
    def save_race_result(self, race_id, car_id, final_position, total_laps, total_time, fastest_lap_time, points_earned=0, consistency_score=0):
        """Saves the final result for a car in a race."""
        try:
            self.cursor.execute('''
                INSERT INTO RaceResults (race_id, car_id, final_position, total_laps, total_time, fastest_lap_time, points_earned, consistency_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (race_id, car_id, final_position, total_laps, total_time, fastest_lap_time, points_earned, consistency_score))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error saving race result: {e}")
            QMessageBox.critical(None, "Database Error", f"Error saving race result: {e}")
            return None

    def get_race_results(self, race_id):
        """Retrieves results for a specific race."""
        self.cursor.execute('''
            SELECT
                rr.final_position,
                d.name AS driver_name,
                c.car_name,
                cl.name AS class_name,
                rr.total_laps,
                rr.total_time,
                rr.fastest_lap_time,
                rr.points_earned,
                rr.consistency_score
            FROM RaceResults rr
            JOIN Cars c ON rr.car_id = c.car_id
            JOIN Drivers d ON c.driver_id = d.driver_id
            JOIN Classes cl ON c.class_id = cl.class_id
            WHERE rr.race_id = ?
            ORDER BY rr.final_position ASC
        ''', (race_id,))
        return self.cursor.fetchall()

    # --- Adjustments Log ---
    def log_adjustment(self, table_name, record_id, field_name, old_value, new_value, reason, adjusted_by="System"):
        """Logs any manual adjustment made to data."""
        try:
            timestamp = datetime.now().isoformat()
            self.cursor.execute('''
                INSERT INTO AdjustmentsLog (table_name, record_id, field_name, old_value, new_value, timestamp, reason, adjusted_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (table_name, record_id, field_name, str(old_value), str(new_value), timestamp, reason, adjusted_by))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error logging adjustment: {e}")
            # Do not show critical message for logging, as it might be a secondary error

# --- Main Application ---
class RCScoringApp(QMainWindow):
    """
    Main application window for the RC Scoring system.
    Manages UI, race logic, and interacts with the DatabaseManager.
    """
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.setWindowTitle("RC Scoring System (macOS)")
        self.setGeometry(100, 100, 1200, 800) # Increased size for better layout

        self.current_race_id = None
        self.race_start_time = None
        self.race_end_time = None
        self.race_duration_seconds = 0
        self.race_active = False
        self.lap_times = {} # Stores {car_id: [(lap_number, lap_time, timestamp), ...]}
        self.car_current_lap_number = {} # Stores {car_id: current_lap_number}
        self.car_last_lap_timestamp = {} # Stores {car_id: last_lap_timestamp}
        self.race_participants_data = {} # Stores {car_id: {'driver_name': '', 'car_name': '', 'transponder_id': ''}}
        self.keyboard_car_map = {} # Maps keyboard digit (str) to car_id (int)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_race_timer)

        self.init_ui()
        # Set focus policy to ensure the main window receives key events
        self.setFocusPolicy(Qt.StrongFocus)

    def init_ui(self):
        """Initializes the main user interface with tabs."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        # Create tabs - ensure all tabs and their widgets are created BEFORE loading data
        self.create_race_setup_tab()
        self.create_live_scoring_tab()
        self.create_data_management_tab()
        self.create_reports_tab()

        self.tab_widget.addTab(self.race_setup_tab, "Race Setup")
        self.tab_widget.addTab(self.live_scoring_tab, "Live Scoring")
        self.tab_widget.addTab(self.data_management_tab, "Data Management")
        self.tab_widget.addTab(self.reports_tab, "Reports")

        # Set initial tab
        self.tab_widget.setCurrentIndex(0)

        # Load initial data AFTER all UI components are guaranteed to be created
        self.load_events_to_combo()
        self.load_cars_to_combo() # This also loads cars for the participant selector
        self.load_drivers_to_table()
        self.load_classes_to_table()
        self.load_cars_to_table()
        self.load_drivers_to_car_combo()
        self.load_classes_to_car_combo()
        self.load_races_to_report_combo()


    def create_race_setup_tab(self):
        """Creates the Race Setup tab UI."""
        self.race_setup_tab = QWidget()
        layout = QVBoxLayout(self.race_setup_tab)

        # Event Management Section
        event_group_box = self._create_group_box("Event Management")
        event_layout = QFormLayout(event_group_box)
        self.event_name_input = QLineEdit()
        self.event_date_input = QLineEdit(datetime.now().strftime("%Y-%m-%d")) # Default to today
        self.event_location_input = QLineEdit()
        self.add_event_button = QPushButton("Add New Event")
        self.add_event_button.clicked.connect(self.add_new_event)
        event_layout.addRow("Event Name:", self.event_name_input)
        event_layout.addRow("Date (YYYY-MM-DD):", self.event_date_input)
        event_layout.addRow("Location:", self.event_location_input)
        event_layout.addRow(self.add_event_button)

        self.event_selector_combo = QComboBox()
        self.event_selector_combo.currentIndexChanged.connect(self.load_races_for_selected_event)
        event_layout.addRow("Select Event:", self.event_selector_combo)
        layout.addWidget(event_group_box)

        # Race Configuration Section
        race_config_group_box = self._create_group_box("Race Configuration")
        race_config_layout = QFormLayout(race_config_group_box)
        self.race_type_input = QComboBox()
        self.race_type_input.addItems(["Practice", "Qualifier", "Main", "Endurance"])
        self.race_round_input = QLineEdit("1")
        self.race_heat_input = QLineEdit("1")
        self.race_duration_input = QLineEdit("300") # Default 5 minutes (300 seconds)
        self.add_race_button = QPushButton("Create New Race")
        self.add_race_button.clicked.connect(self.create_new_race)
        race_config_layout.addRow("Race Type:", self.race_type_input)
        race_config_layout.addRow("Round Number:", self.race_round_input)
        race_config_layout.addRow("Heat Number:", self.race_heat_input)
        race_config_layout.addRow("Duration (seconds):", self.race_duration_input)
        race_config_layout.addRow(self.add_race_button)

        self.race_selector_combo = QComboBox()
        self.race_selector_combo.currentIndexChanged.connect(self.load_participants_for_selected_race)
        race_config_layout.addRow("Select Race:", self.race_selector_combo)
        layout.addWidget(race_config_group_box)

        # Participants Management Section
        participants_group_box = self._create_group_box("Race Participants")
        participants_layout = QVBoxLayout(participants_group_box)

        add_participant_layout = QHBoxLayout()
        self.car_selector_combo = QComboBox()
        self.add_participant_button = QPushButton("Add Car to Race")
        self.add_participant_button.clicked.connect(self.add_car_to_race)
        add_participant_layout.addWidget(QLabel("Select Car:"))
        add_participant_layout.addWidget(self.car_selector_combo)
        add_participant_layout.addWidget(self.add_participant_button)
        participants_layout.addLayout(add_participant_layout)

        self.race_participants_table = QTableWidget()
        self.race_participants_table.setColumnCount(4)
        self.race_participants_table.setHorizontalHeaderLabels(["Car ID", "Transponder ID", "Driver Name", "Car Name"])
        self.race_participants_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        participants_layout.addWidget(self.race_participants_table)

        layout.addWidget(participants_group_box)

        # Start Race Section (Stop button moved from here)
        start_race_group_box = self._create_group_box("Start Race")
        start_race_layout = QHBoxLayout(start_race_group_box)
        self.start_race_button = QPushButton("Start Selected Race")
        self.start_race_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.start_race_button.clicked.connect(self.start_race)
        start_race_layout.addWidget(self.start_race_button)
        layout.addWidget(start_race_group_box)

        layout.addStretch(1) # Pushes content to the top

    def create_live_scoring_tab(self):
        """Creates the Live Scoring tab UI."""
        self.live_scoring_tab = QWidget()
        layout = QVBoxLayout(self.live_scoring_tab)

        # Race Info Display
        race_info_layout = QHBoxLayout()
        self.current_race_label = QLabel("Current Race: None")
        self.race_timer_label = QLabel("Time Left: 00:00.000") # Updated for milliseconds
        self.current_race_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.race_timer_label.setStyleSheet("font-size: 18px; font-weight: bold; color: blue;")
        race_info_layout.addWidget(self.current_race_label)
        race_info_layout.addStretch(1)
        race_info_layout.addWidget(self.race_timer_label)
        layout.addLayout(race_info_layout)

        # Manual Lap Input Buttons (dynamically generated)
        self.lap_input_buttons_layout = QVBoxLayout()
        layout.addLayout(self.lap_input_buttons_layout)

        # Live Scoring Table (added 8th column for Pace)
        self.live_scoring_table = QTableWidget()
        self.live_scoring_table.setColumnCount(8) # Still 8 columns
        self.live_scoring_table.setHorizontalHeaderLabels([
            "Pos", "Driver", "Car", "Class", "Laps", "Last Lap", "Best Lap", "Pace (Laps / MM:SS.mmm)" # Changed header
        ])
        self.live_scoring_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.live_scoring_table)

        # Stop Race Button (Moved here from Race Setup)
        stop_race_layout = QHBoxLayout()
        self.stop_race_button = QPushButton("Stop Current Race")
        self.stop_race_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.stop_race_button.clicked.connect(self.stop_race)
        self.stop_race_button.setEnabled(False) # Disabled until a race starts
        stop_race_layout.addStretch(1)
        stop_race_layout.addWidget(self.stop_race_button)
        stop_race_layout.addStretch(1)
        layout.addLayout(stop_race_layout)


    def create_data_management_tab(self):
        """Creates the Data Management tab UI for Drivers, Cars, and Classes."""
        self.data_management_tab = QWidget()
        layout = QHBoxLayout(self.data_management_tab)

        # Drivers Section
        driver_group_box = self._create_group_box("Drivers")
        driver_layout = QVBoxLayout(driver_group_box)
        driver_form_layout = QFormLayout()
        self.driver_name_input = QLineEdit()
        self.driver_nickname_input = QLineEdit()
        self.add_driver_button = QPushButton("Add Driver")
        self.add_driver_button.clicked.connect(self.add_new_driver)
        driver_form_layout.addRow("Name:", self.driver_name_input)
        driver_form_layout.addRow("Nickname:", self.driver_nickname_input)
        driver_layout.addLayout(driver_form_layout)
        driver_layout.addWidget(self.add_driver_button)

        self.driver_list_table = QTableWidget()
        self.driver_list_table.setColumnCount(2)
        self.driver_list_table.setHorizontalHeaderLabels(["ID", "Name"])
        self.driver_list_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        driver_layout.addWidget(self.driver_list_table)
        layout.addWidget(driver_group_box)

        # Classes Section
        class_group_box = self._create_group_box("Classes")
        class_layout = QVBoxLayout(class_group_box)
        class_form_layout = QFormLayout()
        self.class_name_input = QLineEdit()
        self.add_class_button = QPushButton("Add Class")
        self.add_class_button.clicked.connect(self.add_new_class)
        class_form_layout.addRow("Name:", self.class_name_input)
        class_layout.addLayout(class_form_layout)
        class_layout.addWidget(self.add_class_button)

        self.class_list_table = QTableWidget()
        self.class_list_table.setColumnCount(2)
        self.class_list_table.setHorizontalHeaderLabels(["ID", "Name"])
        self.class_list_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        class_layout.addWidget(self.class_list_table)
        layout.addWidget(class_group_box)

        # Cars Section
        car_group_box = self._create_group_box("Cars")
        car_layout = QVBoxLayout(car_group_box)
        car_form_layout = QFormLayout()
        self.car_driver_combo = QComboBox()
        self.car_class_combo = QComboBox()
        self.car_name_input = QLineEdit()
        self.car_transponder_input = QLineEdit()
        self.add_car_button = QPushButton("Add Car")
        self.add_car_button.clicked.connect(self.add_new_car)
        car_form_layout.addRow("Driver:", self.car_driver_combo)
        car_form_layout.addRow("Class:", self.car_class_combo)
        car_form_layout.addRow("Car Name:", self.car_name_input)
        car_form_layout.addRow("Transponder ID:", self.car_transponder_input)
        car_layout.addLayout(car_form_layout)
        car_layout.addWidget(self.add_car_button)

        self.car_list_table = QTableWidget()
        self.car_list_table.setColumnCount(5)
        self.car_list_table.setHorizontalHeaderLabels(["ID", "Car Name", "Driver", "Class", "Transponder ID"])
        self.car_list_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        car_layout.addWidget(self.car_list_table)
        layout.addWidget(car_group_box)

    def create_reports_tab(self):
        """Creates the Reports tab UI."""
        self.reports_tab = QWidget()
        layout = QVBoxLayout(self.reports_tab)

        # Race Report Section
        race_report_layout = QHBoxLayout()
        self.report_race_selector = QComboBox()
        self.generate_report_button = QPushButton("Generate Race Report")
        self.generate_report_button.clicked.connect(self.generate_race_report)

        race_report_layout.addWidget(QLabel("Select Race for Report:"))
        race_report_layout.addWidget(self.report_race_selector)
        race_report_layout.addWidget(self.generate_report_button)
        layout.addLayout(race_report_layout)

        self.report_display_table = QTableWidget()
        # Updated columns for Reports Tab
        self.report_display_table.setColumnCount(6)
        self.report_display_table.setHorizontalHeaderLabels([
            "Pos", "Driver", "Laps/Time", "Top 5 Average", "Fastest Lap", "Avg Lap"
        ])
        self.report_display_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.report_display_table)

        # CSV Lap Report Section
        csv_lap_report_layout = QHBoxLayout()
        self.generate_lap_csv_button = QPushButton("Generate Detailed Lap CSV")
        self.generate_lap_csv_button.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
        self.generate_lap_csv_button.clicked.connect(self.generate_detailed_lap_csv)
        csv_lap_report_layout.addStretch(1) # Push button to the right
        csv_lap_report_layout.addWidget(self.generate_lap_csv_button)
        csv_lap_report_layout.addStretch(1) # Push button to the right
        layout.addLayout(csv_lap_report_layout)


        layout.addStretch(1)

    def _create_group_box(self, title):
        """Helper to create a QGroupBox with a title."""
        from PyQt5.QtWidgets import QGroupBox
        group_box = QGroupBox(title)
        group_box.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }")
        return group_box

    # --- Data Loading for Comboboxes and Tables ---
    def load_events_to_combo(self):
        """Loads events into the event selector combobox."""
        self.event_selector_combo.clear()
        events = self.db.get_events()
        if not events:
            self.event_selector_combo.addItem("No Events Available", None)
            return

        for event_id, name, date in events:
            self.event_selector_combo.addItem(f"{name} ({date})", event_id)

    def load_races_for_selected_event(self):
        """Loads races for the currently selected event into the race selector combobox."""
        # Ensure race_selector_combo exists before clearing
        if not hasattr(self, 'race_selector_combo'):
            return # Or handle this more robustly if needed

        self.race_selector_combo.clear()
        selected_event_id = self.event_selector_combo.currentData()
        if selected_event_id is None:
            self.race_selector_combo.addItem("Select an Event First", None)
            return

        races = self.db.get_races(selected_event_id)
        if not races:
            self.race_selector_combo.addItem("No Races for this Event", None)
            return

        for race_id, event_name, race_type, round_num, heat_num, duration, is_active in races:
            race_display = f"{race_type} R{round_num} H{heat_num} ({duration}s)"
            self.race_selector_combo.addItem(race_display, race_id)

    def load_cars_to_combo(self):
        """Loads cars into the car selector combobox for race participants."""
        self.car_selector_combo.clear()
        cars = self.db.get_cars()
        if not cars:
            self.car_selector_combo.addItem("No Cars Available", None)
            return
        for car_id, car_name, driver_name, class_name, transponder_id in cars:
            self.car_selector_combo.addItem(f"{driver_name} - {car_name} ({transponder_id})", car_id)

    def load_drivers_to_table(self):
        """Loads drivers into the drivers list table."""
        self.driver_list_table.setRowCount(0)
        drivers = self.db.get_drivers()
        for row_idx, (driver_id, name) in enumerate(drivers):
            self.driver_list_table.insertRow(row_idx)
            self.driver_list_table.setItem(row_idx, 0, QTableWidgetItem(str(driver_id)))
            self.driver_list_table.setItem(row_idx, 1, QTableWidgetItem(name))

    def load_classes_to_table(self):
        """Loads classes into the classes list table."""
        self.class_list_table.setRowCount(0)
        classes = self.db.get_classes()
        for row_idx, (class_id, name) in enumerate(classes):
            self.class_list_table.insertRow(row_idx)
            self.class_list_table.setItem(row_idx, 0, QTableWidgetItem(str(class_id)))
            self.class_list_table.setItem(row_idx, 1, QTableWidgetItem(name))

    def load_cars_to_table(self):
        """Loads cars into the cars list table."""
        self.car_list_table.setRowCount(0)
        cars = self.db.get_cars()
        for row_idx, (car_id, car_name, driver_name, class_name, transponder_id) in enumerate(cars):
            self.car_list_table.insertRow(row_idx)
            self.car_list_table.setItem(row_idx, 0, QTableWidgetItem(str(car_id)))
            self.car_list_table.setItem(row_idx, 1, QTableWidgetItem(car_name))
            self.car_list_table.setItem(row_idx, 2, QTableWidgetItem(driver_name))
            self.car_list_table.setItem(row_idx, 3, QTableWidgetItem(class_name))
            self.car_list_table.setItem(row_idx, 4, QTableWidgetItem(transponder_id))

    def load_drivers_to_car_combo(self):
        """Loads drivers into the car creation driver combobox."""
        self.car_driver_combo.clear()
        drivers = self.db.get_drivers()
        if not drivers:
            self.car_driver_combo.addItem("No Drivers", None)
            return
        for driver_id, name in drivers:
            self.car_driver_combo.addItem(name, driver_id)

    def load_classes_to_car_combo(self):
        """Loads classes into the car creation class combobox."""
        self.car_class_combo.clear()
        classes = self.db.get_classes()
        if not classes:
            self.car_class_combo.addItem("No Classes", None)
            return
        for class_id, name in classes:
            self.car_class_combo.addItem(name, class_id)

    def load_participants_for_selected_race(self):
        """Loads participants for the selected race into the participants table."""
        self.race_participants_table.setRowCount(0)
        self.race_participants_data = {} # Clear previous data
        self.keyboard_car_map = {} # Clear previous keyboard map

        selected_race_id = self.race_selector_combo.currentData()
        if selected_race_id is None:
            return

        participants = self.db.get_race_participants(selected_race_id)
        if not participants:
            return

        for row_idx, (car_id, transponder_id, car_name, driver_name, class_name, start_position) in enumerate(participants):
            self.race_participants_table.insertRow(row_idx)
            self.race_participants_table.setItem(row_idx, 0, QTableWidgetItem(str(car_id)))
            self.race_participants_table.setItem(row_idx, 1, QTableWidgetItem(transponder_id))
            self.race_participants_table.setItem(row_idx, 2, QTableWidgetItem(driver_name))
            self.race_participants_table.setItem(row_idx, 3, QTableWidgetItem(car_name))

            # Store participant data for live scoring
            self.race_participants_data[car_id] = {
                'driver_name': driver_name,
                'car_name': car_name,
                'class_name': class_name,
                'transponder_id': transponder_id,
                'start_position': start_position
            }
            # Map keyboard digit to car_id (1-based index, 0 for 10th car)
            key_digit = str((row_idx + 1) % 10) # 1, 2, ..., 9, 0
            self.keyboard_car_map[key_digit] = car_id

        self.generate_lap_input_buttons() # Regenerate buttons based on participants

    def load_races_to_report_combo(self):
        """Loads all races into the report selector combobox."""
        self.report_race_selector.clear()
        races = self.db.get_races()
        if not races:
            self.report_race_selector.addItem("No Races Available", None)
            return
        for race_id, event_name, race_type, round_num, heat_num, duration, is_active in races:
            race_display = f"{event_name} - {race_type} R{round_num} H{heat_num}"
            self.report_race_selector.addItem(race_display, race_id)

    # --- Add New Data Functions ---
    def add_new_event(self):
        """Adds a new event to the database."""
        name = self.event_name_input.text().strip()
        date = self.event_date_input.text().strip()
        location = self.event_location_input.text().strip()
        if not name or not date:
            QMessageBox.warning(self, "Input Error", "Event Name and Date are required.")
            return

        event_id = self.db.add_event(name, date, location)
        if event_id:
            QMessageBox.information(self, "Success", f"Event '{name}' added successfully.")
            self.event_name_input.clear()
            self.event_location_input.clear()
            self.load_events_to_combo()
            self.load_races_to_report_combo() # Update reports combo as well

    def create_new_race(self):
        """Creates a new race for the selected event."""
        event_id = self.event_selector_combo.currentData()
        if event_id is None:
            QMessageBox.warning(self, "Selection Error", "Please select an Event first.")
            return

        race_type = self.race_type_input.currentText()
        try:
            round_number = int(self.race_round_input.text())
            heat_number = int(self.race_heat_input.text())
            duration_seconds = int(self.race_duration_input.text())
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Round, Heat, and Duration must be valid numbers.")
            return

        race_id = self.db.add_race(event_id, race_type, duration_seconds, round_number, heat_number)
        if race_id:
            QMessageBox.information(self, "Success", f"Race created successfully (ID: {race_id}).")
            self.load_races_for_selected_event()
            self.load_races_to_report_combo()

    def add_car_to_race(self):
        """Adds the selected car as a participant to the currently selected race."""
        race_id = self.race_selector_combo.currentData()
        car_id = self.car_selector_combo.currentData()

        if race_id is None:
            QMessageBox.warning(self, "Selection Error", "Please select a Race first.")
            return
        if car_id is None:
            QMessageBox.warning(self, "Selection Error", "Please select a Car to add.")
            return

        # Check if car is already added to this race
        current_participants = [self.race_participants_table.item(i, 0).text() for i in range(self.race_participants_table.rowCount())]
        if str(car_id) in current_participants:
            QMessageBox.warning(self, "Duplicate Entry", "This car is already added to the current race.")
            return

        participant_id = self.db.add_race_participant(race_id, car_id)
        if participant_id:
            QMessageBox.information(self, "Success", "Car added to race participants.")
            self.load_participants_for_selected_race() # Reload participants table and buttons

    def add_new_driver(self):
        """Adds a new driver to the database."""
        name = self.driver_name_input.text().strip()
        nickname = self.driver_nickname_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Driver Name cannot be empty.")
            return
        driver_id = self.db.add_driver(name, nickname)
        if driver_id:
            QMessageBox.information(self, "Success", f"Driver '{name}' added.")
            self.driver_name_input.clear()
            self.driver_nickname_input.clear()
            self.load_drivers_to_table()
            self.load_drivers_to_car_combo() # Update car creation combo

    def add_new_class(self):
        """Adds a new class to the database."""
        name = self.class_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Class Name cannot be empty.")
            return
        class_id = self.db.add_class(name)
        if class_id:
            QMessageBox.information(self, "Success", f"Class '{name}' added.")
            self.class_name_input.clear()
            self.load_classes_to_table()
            self.load_classes_to_car_combo() # Update car creation combo

    def add_new_car(self):
        """Adds a new car to the database."""
        driver_id = self.car_driver_combo.currentData()
        class_id = self.car_class_combo.currentData()
        car_name = self.car_name_input.text().strip()
        transponder_id = self.car_transponder_input.text().strip()

        if not all([driver_id, class_id, car_name, transponder_id]):
            QMessageBox.warning(self, "Input Error", "All car fields are required.")
            return

        car_id = self.db.add_car(driver_id, class_id, car_name, transponder_id)
        if car_id:
            QMessageBox.information(self, "Success", f"Car '{car_name}' added with Transponder ID: {transponder_id}.")
            self.car_name_input.clear()
            self.car_transponder_input.clear()
            self.load_cars_to_table()
            self.load_cars_to_combo() # Update race participants combo

    # --- Race Control Functions ---
    def start_race(self):
        """Starts the selected race."""
        if self.race_active:
            QMessageBox.warning(self, "Race Active", "A race is already in progress. Please stop it first.")
            return

        selected_race_id = self.race_selector_combo.currentData()
        if selected_race_id is None:
            QMessageBox.warning(self, "Selection Error", "Please select a Race to start.")
            return

        participants_count = self.race_participants_table.rowCount()
        if participants_count == 0:
            QMessageBox.warning(self, "Race Error", "No participants added to this race. Please add cars first.")
            return

        race_details = self.db.get_race_details(selected_race_id)
        if not race_details:
            QMessageBox.critical(self, "Error", "Could not retrieve race details for selected race.")
            return

        # Ensure race_duration_seconds is an integer, providing a default if None
        # Corrected index from 6 to 5 for duration_seconds
        duration_from_db = race_details[5]
        if duration_from_db is None:
            QMessageBox.warning(self, "Data Error", "Race duration not found for selected race. Defaulting to 300 seconds.")
            self.race_duration_seconds = 300 # Default to 5 minutes
        else:
            self.race_duration_seconds = int(duration_from_db) # Ensure it's an integer

        self.current_race_id = selected_race_id
        self.race_start_time = datetime.now()
        self.race_active = True
        self.lap_times = {car_id: [] for car_id in self.race_participants_data.keys()}
        self.car_current_lap_number = {car_id: 0 for car_id in self.race_participants_data.keys()}
        self.car_last_lap_timestamp = {car_id: self.race_start_time for car_id in self.race_participants_data.keys()}

        # Update DB status
        self.db.set_race_active_status(self.current_race_id, True, self.race_start_time.isoformat())

        self.current_race_label.setText(f"Current Race: {self.race_selector_combo.currentText()}")
        self.update_race_timer() # Initial timer update
        self.timer.start(1000) # Update every second

        self.start_race_button.setEnabled(False)
        self.stop_race_button.setEnabled(True) # Enable stop button when race starts
        self.tab_widget.setCurrentIndex(1) # Switch to Live Scoring tab

        QMessageBox.information(self, "Race Started", f"Race '{self.race_selector_combo.currentText()}' has started!")

    def stop_race(self):
        """Stops the current race."""
        if not self.race_active:
            QMessageBox.warning(self, "Race Not Active", "No race is currently in progress.")
            return

        self.timer.stop()
        self.race_active = False
        self.race_end_time = datetime.now()

        # Update DB status
        self.db.set_race_active_status(self.current_race_id, False, None, self.race_end_time.isoformat())

        QMessageBox.information(self, "Race Stopped", "Race has been stopped. Calculating results...")
        self.calculate_and_save_results()

        self.current_race_id = None
        self.race_start_time = None
        self.race_end_time = None
        self.race_duration_seconds = 0
        self.lap_times = {}
        self.car_current_lap_number = {}
        self.car_last_lap_timestamp = {}
        self.race_participants_data = {}
        self.keyboard_car_map = {} # Clear keyboard map on race stop

        self.current_race_label.setText("Current Race: None")
        self.race_timer_label.setText("Time Left: 00:00.000") # Reset timer display
        self.live_scoring_table.setRowCount(0) # Clear live scoring table
        self.clear_lap_input_buttons() # Clear lap input buttons

        self.start_race_button.setEnabled(True)
        self.stop_race_button.setEnabled(False) # Disable stop button when race stops

    def update_race_timer(self):
        """Updates the race timer display. Continues counting past race duration."""
        if not self.race_active or not self.race_start_time:
            return

        elapsed_total_seconds = (datetime.now() - self.race_start_time).total_seconds()
        
        # Determine display based on race duration
        if elapsed_total_seconds < self.race_duration_seconds:
            # Counting down to zero
            remaining_time = self.race_duration_seconds - elapsed_total_seconds
            minutes = int(remaining_time // 60)
            seconds = int(remaining_time % 60)
            milliseconds = int((remaining_time - int(remaining_time)) * 1000)
            self.race_timer_label.setText(f"Time Left: {minutes:02d}:{seconds:02d}.{milliseconds:03d}")
        else:
            # Counting up past zero (overtime)
            overtime_seconds = elapsed_total_seconds - self.race_duration_seconds
            minutes = int(overtime_seconds // 60)
            seconds = int(overtime_seconds % 60)
            milliseconds = int((overtime_seconds - int(overtime_seconds)) * 1000)
            self.race_timer_label.setText(f"Time: +{minutes:02d}:{seconds:02d}.{milliseconds:03d}")

        # The race no longer automatically stops here. It waits for the manual stop button.
        self.update_live_scoring_display()

    def generate_lap_input_buttons(self):
        """Generates manual lap input buttons for each participant, including keyboard shortcuts."""
        # Clear existing buttons
        for i in reversed(range(self.lap_input_buttons_layout.count())):
            widget = self.lap_input_buttons_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Clear existing keyboard map before populating
        self.keyboard_car_map = {}

        # Create new buttons
        if not self.race_participants_data:
            self.lap_input_buttons_layout.addWidget(QLabel("No participants loaded for manual scoring."))
            return

        grid_layout = QHBoxLayout() # Use QHBoxLayout for simplicity, could be QGridLayout for more cars
        # Sort participants by start_position if available, otherwise by driver name for consistent keyboard mapping
        sorted_participants = sorted(
            self.race_participants_data.items(),
            key=lambda item: item[1].get('start_position', float('inf')) if item[1].get('start_position') is not None else item[1]['driver_name']
        )

        for idx, (car_id, data) in enumerate(sorted_participants):
            # Assign keyboard digit: 1-9 for first 9 cars, 0 for 10th car
            key_digit = str((idx + 1) % 10) # 1, 2, ..., 9, 0
            self.keyboard_car_map[key_digit] = car_id

            button = QPushButton(f"[{key_digit}] Lap: {data['driver_name']} ({data['transponder_id']})")
            button.setMinimumHeight(40)
            button.setStyleSheet("QPushButton { background-color: #007bff; color: white; border-radius: 5px; padding: 5px; }"
                                 "QPushButton:pressed { background-color: #0056b3; }")
            # Store car_id in button's property for easy access in slot (for direct clicks)
            button.setProperty("car_id", car_id)
            button.clicked.connect(lambda _, c_id=car_id: self.record_manual_lap(car_id=c_id)) # Pass car_id directly
            grid_layout.addWidget(button)
        self.lap_input_buttons_layout.addLayout(grid_layout)

    def clear_lap_input_buttons(self):
        """Clears all dynamic lap input buttons."""
        for i in reversed(range(self.lap_input_buttons_layout.count())):
            widget = self.lap_input_buttons_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    def record_manual_lap(self, car_id):
        """Records a manual lap for the given car_id."""
        if not self.race_active or self.current_race_id is None:
            QMessageBox.warning(self, "Race Not Active", "No race is currently in progress to record laps.")
            return

        if car_id not in self.race_participants_data:
            QMessageBox.warning(self, "Invalid Car", f"Car ID {car_id} is not a participant in the current race.")
            return

        current_timestamp = datetime.now()
        last_lap_timestamp = self.car_last_lap_timestamp.get(car_id, self.race_start_time)

        # Calculate lap time
        lap_time_seconds = (current_timestamp - last_lap_timestamp).total_seconds()

        # Increment lap number
        self.car_current_lap_number[car_id] = self.car_current_lap_number.get(car_id, 0) + 1
        lap_number = self.car_current_lap_number[car_id]

        # Store lap data
        if car_id not in self.lap_times:
            self.lap_times[car_id] = []
        self.lap_times[car_id].append((lap_number, lap_time_seconds, current_timestamp))
        self.car_last_lap_timestamp[car_id] = current_timestamp

        # Record to database
        self.db.record_lap(self.current_race_id, car_id, lap_number, lap_time_seconds, current_timestamp.isoformat())

        # Update live scoring display immediately
        self.update_live_scoring_display()

        # Optional: Provide visual feedback on the button itself after key press
        # This part is tricky as we don't have direct reference to the specific button from keyPressEvent
        # A more advanced UI would update the specific button's text or style.
        # For now, the live scoring table update provides feedback.

    def keyPressEvent(self, event):
        """Handles keyboard press events for manual lap input."""
        if self.race_active and self.current_race_id is not None:
            key_text = event.text()
            if key_text in self.keyboard_car_map:
                car_id_to_lap = self.keyboard_car_map[key_text]
                self.record_manual_lap(car_id=car_id_to_lap)
                event.accept() # Mark event as handled
            else:
                super().keyPressEvent(event) # Pass to default handler
        else:
            super().keyPressEvent(event) # Pass to default handler


    def update_live_scoring_display(self):
        """Updates the live scoring table with current race data, including Pace (Estimated Laps / Time)."""
        if not self.race_active or self.current_race_id is None:
            self.live_scoring_table.setRowCount(0)
            return

        # Calculate current standings
        # List of (car_id, total_laps, total_time, fastest_lap_time, last_lap_time, pace_display_string)
        current_standings = []

        for car_id in self.race_participants_data.keys():
            laps = self.lap_times.get(car_id, [])
            total_laps = len(laps)
            total_time = 0.0
            fastest_lap_time = float('inf')
            average_lap_time = 0.0
            pace_display_string = "-" # Default display for pace

            if total_laps > 0:
                last_lap_ts = self.car_last_lap_timestamp[car_id]
                total_time = (last_lap_ts - self.race_start_time).total_seconds()

                lap_times_only = [lt for _, lt, _ in laps]
                if len(lap_times_only) > 0:
                    fastest_lap_time = min(lap_times_only)
                    average_lap_time = sum(lap_times_only) / total_laps

                    # Calculate Pace: Estimated total laps and total time for those laps
                    if average_lap_time > 0 and self.race_duration_seconds > 0:
                        # Calculate the theoretical number of laps completed exactly at race duration
                        estimated_laps_at_duration = self.race_duration_seconds / average_lap_time

                        # Projected whole laps should be the ceiling of this, ensuring time component >= race duration
                        projected_whole_laps = math.ceil(estimated_laps_at_duration)

                        # Calculate the predicted total time to complete these projected whole laps
                        predicted_time_for_projected_laps = projected_whole_laps * average_lap_time

                        # Format predicted_time_for_projected_laps to MM:SS.mmm
                        formatted_predicted_time = format_seconds_to_mm_ss_mmm(predicted_time_for_projected_laps)

                        # Format for display: "Whole Laps / MM:SS.mmm"
                        pace_display_string = f"{projected_whole_laps} / {formatted_predicted_time}"
                    else:
                        pace_display_string = "-" # Cannot calculate pace if avg_lap_time is zero or race duration is zero
            else:
                fastest_lap_time = 0.0
                average_lap_time = 0.0
                pace_display_string = "-" # No laps yet, no pace

            current_standings.append({
                'car_id': car_id,
                'driver_name': self.race_participants_data[car_id]['driver_name'],
                'car_name': self.race_participants_data[car_id]['car_name'],
                'class_name': self.race_participants_data[car_id]['class_name'],
                'total_laps': total_laps,
                'total_time': total_time,
                'fastest_lap_time': fastest_lap_time,
                'last_lap_time': laps[-1][1] if laps else 0.0,
                'pace_display_string': pace_display_string # Store the formatted pace string
            })

        # Sort standings: Primary by total_laps (desc), secondary by total_time (asc)
        current_standings.sort(key=lambda x: (-x['total_laps'], x['total_time']))

        self.live_scoring_table.setRowCount(len(current_standings))
        for row_idx, result in enumerate(current_standings):
            self.live_scoring_table.setItem(row_idx, 0, QTableWidgetItem(str(row_idx + 1))) # Position
            self.live_scoring_table.setItem(row_idx, 1, QTableWidgetItem(result['driver_name']))
            self.live_scoring_table.setItem(row_idx, 2, QTableWidgetItem(result['car_name']))
            self.live_scoring_table.setItem(row_idx, 3, QTableWidgetItem(result['class_name']))
            self.live_scoring_table.setItem(row_idx, 4, QTableWidgetItem(str(result['total_laps'])))
            self.live_scoring_table.setItem(row_idx, 5, QTableWidgetItem(format_seconds_to_mm_ss_mmm(result['last_lap_time']))) # Formatted MM:SS.mmm
            self.live_scoring_table.setItem(row_idx, 6, QTableWidgetItem(format_seconds_to_mm_ss_mmm(result['fastest_lap_time']))) # Formatted MM:SS.mmm
            # Display Pace (Estimated Laps / Time)
            self.live_scoring_table.setItem(row_idx, 7, QTableWidgetItem(result['pace_display_string']))

    def calculate_and_save_results(self):
        """Calculates final results and saves them to the database."""
        if self.current_race_id is None:
            return

        final_standings = [] # List of (car_id, total_laps, total_time, fastest_lap_time)

        for car_id in self.race_participants_data.keys():
            laps = self.lap_times.get(car_id, [])
            total_laps = len(laps)
            total_time = 0.0
            fastest_lap_time = float('inf')
            consistency_score = 0.0

            if total_laps > 0:
                # Total time is from race start to final race end time or last lap time
                # For timed races, it's the time elapsed when the race ends.
                # For lap-based races, it's the time to complete the required laps.
                # Here, we assume timed race, so total time is from start to end of race.
                if self.race_end_time:
                    total_time = (self.race_end_time - self.race_start_time).total_seconds()
                else: # Fallback if race stopped manually without timer expiry
                    total_time = (datetime.now() - self.race_start_time).total_seconds()

                lap_times_only = [lt for _, lt, _ in laps]
                if len(lap_times_only) > 0:
                    fastest_lap_time = min(lap_times_only)
                    # Simple consistency: standard deviation of lap times
                    if len(lap_times_only) > 1:
                        # Ensure numpy is imported for np.std
                        consistency_score = np.std(lap_times_only)
                    else:
                        consistency_score = 0.0 # Only one lap, perfect consistency
            else:
                fastest_lap_time = 0.0

            final_standings.append({
                'car_id': car_id,
                'total_laps': total_laps,
                'total_time': total_time,
                'fastest_lap_time': fastest_lap_time,
                'consistency_score': consistency_score
            })

        # Sort standings: Primary by total_laps (desc), secondary by total_time (asc)
        final_standings.sort(key=lambda x: (-x['total_laps'], x['total_time']))

        # Save results to DB
        for pos, result in enumerate(final_standings):
            self.db.save_race_result(
                race_id=self.current_race_id,
                car_id=result['car_id'],
                final_position=pos + 1,
                total_laps=result['total_laps'],
                total_time=result['total_time'],
                fastest_lap_time=result['fastest_lap_time'],
                consistency_score=result['consistency_score']
            )
        QMessageBox.information(self, "Results Saved", "Race results have been calculated and saved.")
        self.generate_race_report(self.current_race_id) # Show report immediately

    def calculate_fastest_n_consecutive_laps_average(self, lap_times_list, n=5):
        """
        Calculates the average of the fastest N consecutive laps from a list of lap times.
        lap_times_list: A list of float lap times in chronological order.
        n: The number of consecutive laps to consider (e.g., 5 for Top 5 Average).
        Returns the average of the fastest N consecutive laps, or None if not enough laps.
        """
        if not lap_times_list or len(lap_times_list) < n:
            return None

        min_sum = float('inf')
        for i in range(len(lap_times_list) - n + 1):
            current_sum = sum(lap_times_list[i : i + n])
            if current_sum < min_sum:
                min_sum = current_sum

        if min_sum == float('inf'):
            return None
        return min_sum / n

    def generate_race_report(self, race_id_override=None):
        """Generates and displays a report for the selected race."""
        race_id = race_id_override if race_id_override else self.report_race_selector.currentData()
        if race_id is None:
            QMessageBox.warning(self, "Selection Error", "Please select a Race to generate a report.")
            return

        race_details = self.db.get_race_details(race_id)
        if not race_details:
            QMessageBox.critical(self, "Error", "Could not retrieve race details for selected race.")
            return
        race_duration_seconds = int(race_details[5]) # Duration is at index 5

        results = self.db.get_race_results(race_id)
        self.report_display_table.setRowCount(len(results))
        for row_idx, result in enumerate(results):
            # result structure: (final_position, driver_name, car_name, class_name, total_laps, total_time, fastest_lap_time, points_earned, consistency_score)
            final_position, driver_name, car_name, class_name, total_laps, total_time, fastest_lap_time, points_earned, consistency_score = result

            # Fetch all lap times for this car in this race to calculate Top 5 Average and overall Avg Lap
            # Note: The `get_race_results` query does not return `car_id`.
            # To get individual lap times for a car, we need its `car_id`.
            # We'll need to query the `Cars` table to get the `car_id` from `car_name` and `driver_name`
            # This is a temporary workaround. A more robust solution would be to include `car_id` in `RaceResults` query.
            car_id_for_report = None
            # Fetch car_id from the Cars table based on driver_name and car_name
            self.db.cursor.execute('''
                SELECT c.car_id FROM Cars c
                JOIN Drivers d ON c.driver_id = d.driver_id
                WHERE d.name = ? AND c.car_name = ?
            ''', (driver_name, car_name))
            car_id_row = self.db.cursor.fetchone()
            if car_id_row:
                car_id_for_report = car_id_row[0]

            all_laps_for_this_car = []
            if car_id_for_report:
                laps_data_raw = self.db.get_laps_for_car_in_race(race_id, car_id_for_report)
                all_laps_for_this_car = [lap[1] for lap in laps_data_raw] # Extract only lap_time

            # Calculate Top 5 Average
            top_5_avg = self.calculate_fastest_n_consecutive_laps_average(all_laps_for_this_car, n=5)
            formatted_top_5_avg = format_seconds_to_mm_ss_mmm(top_5_avg)

            # Calculate overall average lap time
            overall_avg_lap_time = sum(all_laps_for_this_car) / len(all_laps_for_this_car) if all_laps_for_this_car else 0.0
            formatted_overall_avg_lap_time = format_seconds_to_mm_ss_mmm(overall_avg_lap_time)

            # Laps/Time for report
            laps_time_display = f"{total_laps} / {format_seconds_to_mm_ss_mmm(total_time)}"

            # Set items in the report_display_table
            self.report_display_table.setItem(row_idx, 0, QTableWidgetItem(str(final_position))) # Pos
            self.report_display_table.setItem(row_idx, 1, QTableWidgetItem(driver_name)) # Driver
            self.report_display_table.setItem(row_idx, 2, QTableWidgetItem(laps_time_display)) # Laps/Time
            self.report_display_table.setItem(row_idx, 3, QTableWidgetItem(formatted_top_5_avg)) # Top 5 Average
            self.report_display_table.setItem(row_idx, 4, QTableWidgetItem(format_seconds_to_mm_ss_mmm(fastest_lap_time))) # Fastest Lap
            self.report_display_table.setItem(row_idx, 5, QTableWidgetItem(formatted_overall_avg_lap_time)) # Avg Lap

        self.tab_widget.setCurrentIndex(3) # Switch to Reports tab

    def generate_detailed_lap_csv(self):
        """
        Generates a CSV file containing all individual lap data for a selected race.
        Includes driver name, car name, transponder ID, lap number, lap time, timestamp, and Pace.
        """
        race_id = self.report_race_selector.currentData()
        if race_id is None:
            QMessageBox.warning(self, "Selection Error", "Please select a Race to generate a detailed lap CSV.")
            return

        race_details = self.db.get_race_details(race_id)
        if not race_details:
            QMessageBox.critical(self, "Error", "Could not retrieve race details for selected race.")
            return
        race_duration_seconds = int(race_details[5]) # Duration is at index 5

        laps_data = self.db.get_all_laps_for_race(race_id)
        if not laps_data:
            QMessageBox.information(self, "No Data", "No lap data found for the selected race.")
            return

        # Get race name for default filename
        race_text = self.report_race_selector.currentText()
        default_filename = f"{race_text.replace(' ', '_').replace('(', '').replace(')', '')}_laps.csv"

        # Open a file dialog to let the user choose where to save the CSV
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Lap Data CSV", default_filename, "CSV Files (*.csv);;All Files (*)")

        if file_path:
            try:
                with open(file_path, 'w', newline='') as csvfile:
                    csv_writer = csv.writer(csvfile)
                    # Write header row
                    csv_writer.writerow([
                        "Race ID", "Driver Name", "Car Name", "Transponder ID",
                        "Lap Number", "Lap Time (s)", "Timestamp", "Cumulative Avg. Lap Time (s)", "Pace (Laps / MM:SS.mmm)"
                    ])
                    
                    # To calculate cumulative average lap time and pace for each lap
                    car_lap_times_history = {} # {car_id: [lap_time1, lap_time2, ...]}

                    for lap in laps_data:
                        # lap structure: (lap_id, race_id, car_id, transponder_id, driver_name, car_name, lap_number, lap_time, timestamp)
                        lap_id, r_id, car_id, transponder_id, driver_name, car_name, lap_number, lap_time_seconds, timestamp = lap

                        if car_id not in car_lap_times_history:
                            car_lap_times_history[car_id] = []
                        car_lap_times_history[car_id].append(lap_time_seconds)

                        cumulative_average_lap_time = 0.0
                        pace_display_string = "-"

                        if len(car_lap_times_history[car_id]) > 0:
                            cumulative_average_lap_time = sum(car_lap_times_history[car_id]) / len(car_lap_times_history[car_id])
                            
                            if cumulative_average_lap_time > 0 and race_duration_seconds > 0:
                                estimated_laps_at_duration = race_duration_seconds / cumulative_average_lap_time
                                projected_whole_laps = math.ceil(estimated_laps_at_duration)
                                predicted_time_for_projected_laps = projected_whole_laps * cumulative_average_lap_time
                                formatted_predicted_time = format_seconds_to_mm_ss_mmm(predicted_time_for_projected_laps)
                                pace_display_string = f"{projected_whole_laps} / {formatted_predicted_time}"

                        csv_writer.writerow([
                            r_id,
                            driver_name,
                            car_name,
                            transponder_id,
                            lap_number,
                            f"{lap_time_seconds:.3f}", # Keep raw seconds for CSV, but formatted
                            timestamp,
                            f"{cumulative_average_lap_time:.3f}", # Keep raw seconds for CSV, but formatted
                            pace_display_string # Pace
                        ])
                QMessageBox.information(self, "CSV Export Success", f"Lap data successfully exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "CSV Export Error", f"An error occurred while saving the CSV file: {e}")
        else:
            QMessageBox.information(self, "CSV Export Cancelled", "CSV export was cancelled.")


    def closeEvent(self, event):
        """Handles application close event to ensure database connection is closed."""
        self.db.close()
        event.accept()

# --- Main Execution ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RCScoringApp()
    window.show()
    sys.exit(app.exec_())

