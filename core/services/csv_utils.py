import pandas as pd

def load_csv(file_path):
    try:
        return pd.read_csv(file_path)
    except Exception:
        return pd.DataFrame()

def extract_schema(df):
    return {col: str(dtype) for col, dtype in df.dtypes.items()}

def get_numeric_columns(df):
    return [col for col in df.select_dtypes(include='number').columns] 