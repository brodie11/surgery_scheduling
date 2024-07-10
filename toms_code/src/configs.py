import os

this_path = os.path.abspath(os.path.dirname(__file__))


DATABASE_DIR = os.path.abspath(os.path.join(this_path, os.pardir, 'data'))
OUTPUT_DIR = os.path.abspath(os.path.join(this_path, os.pardir, 'output'))
OUTPUT_DB_DIR = os.path.abspath(os.path.join(OUTPUT_DIR, 'databases/experiments'))
OUTPUT_FIG_DIR = os.path.abspath(os.path.join(OUTPUT_DIR, 'figures'))

DATA_FILE = os.path.join(DATABASE_DIR, 'surgery_data.db')
