from io import BytesIO
import pandas as pd

REQUIRED = ["return_id", "order_id", "sku", "product_name", "category", "vendor", "return_reason_dropdown", "return_date"]
EVALUATION = ["expected_primary_reason", "expected_sub_reason", "expected_body_area"]
SOURCE = REQUIRED + ["size_ordered", "return_reason_text"]
MAX_ROWS = 10000


def read_upload(content: bytes, filename: str, sheet: str | None = None) -> pd.DataFrame:
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("Please use a file smaller than 10 MB.")
    if filename.lower().endswith(".xlsx"):
        with pd.ExcelFile(BytesIO(content), engine="openpyxl") as book:
            selected = sheet or ("Returns_Data" if "Returns_Data" in book.sheet_names else book.sheet_names[0])
            return pd.read_excel(book, sheet_name=selected, dtype=str, keep_default_na=False, nrows=MAX_ROWS + 1)
    if filename.lower().endswith(".csv"):
        return pd.read_csv(BytesIO(content), dtype=str, keep_default_na=False, nrows=MAX_ROWS + 1, encoding="utf-8-sig")
    raise ValueError("Upload a CSV or .xlsx file.")


def is_other(frame):
    return frame.return_reason_dropdown.astype(str).str.strip().str.casefold().eq("other")


def validate_data(frame: pd.DataFrame) -> list[str]:
    errors = []
    missing = sorted(set(REQUIRED) - set(frame.columns))
    if missing:
        return ["Missing required columns: " + ", ".join(missing)]
    if not len(frame):
        errors.append("The file contains no return records.")
    if len(frame) > MAX_ROWS:
        errors.append(f"Maximum batch size is {MAX_ROWS:,} rows.")
    for column in REQUIRED:
        count = int(frame[column].fillna("").astype(str).str.strip().eq("").sum())
        if count:
            errors.append(f"{column}: {count} missing value(s).")
    if frame.return_id.astype(str).str.strip().duplicated().any():
        errors.append("return_id must be unique (including after trimming whitespace).")
    dates = pd.to_datetime(frame.return_date, errors="coerce", format="mixed")
    if dates.isna().any():
        errors.append(f"return_date: {int(dates.isna().sum())} invalid date(s).")
    text = frame.get("return_reason_text", pd.Series("", index=frame.index)).fillna("").astype(str)
    empty = int((is_other(frame) & text.str.strip().eq("")).sum())
    if empty:
        errors.append(f"{empty} Other record(s) have empty return text.")
    if text.str.len().gt(4000).any():
        errors.append("Return comments must be 4,000 characters or fewer.")
    return errors


def split_data(frame: pd.DataFrame):
    """Allowlist, not a blacklist: annotations and unknown columns never reach inference."""
    source = frame.reindex(columns=SOURCE, fill_value="").fillna("").copy()
    labels = frame.reindex(columns=["return_id"] + EVALUATION, fill_value="").fillna("").copy()
    return source, labels


def model_input(row):
    return {"text": str(row.get("return_reason_text", "")),
            "dropdown": str(row.get("return_reason_dropdown", ""))}
