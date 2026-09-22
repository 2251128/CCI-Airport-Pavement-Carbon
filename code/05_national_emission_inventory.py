# -*- coding: utf-8 -*-
"""National airport emission inventory (phase-specific emission factors).

Key safeguards in this repository version
------------------------------------------
1. Paths are resolved relative to the repository root; no local absolute paths.
2. The emission-factor workbook may use either the English public column names
   or the original Chinese column names.
3. A missing airport-aircraft frequency is NEVER replaced by frequency=1.
   The record is logged and skipped.
4. Declared emission-factor units are interpreted explicitly. All reported
   pollutant masses are converted to grams. For example, a factor declared as
   mg/MJ is divided by 1000 before multiplication by energy (MJ).
5. Missing emission factors are logged and skipped rather than silently imputed.

The bundled repository contains only a demonstration airport. Point
AIRPORT_FOLDER to the full airport-input directory for the manuscript-scale run.
"""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# -----------------------------------------------------------------------------
# Paths and analysis settings
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
AIRPORT_FOLDER = BASE_DIR / "data" / "demo_airport"
MODEL_ATTR_PATH = BASE_DIR / "data" / "aircraft_emission_factors.xlsx"
FREQUENCY_PATH = BASE_DIR / "data" / "national_aircraft_frequency.xlsx"
OUTPUT_ROOT = BASE_DIR / "outputs" / "national_emission_inventory"

TARGET_YEAR = 2019
SPEED_THRESHOLD_KMH = 36.0

AREA_MULTIPLIER = {
    "跑道": 1.0,
    "滑行道": 2.0,
    "停机坪": 2.0,
    "快滑道": 2.0,
    "联络道": 2.0,
}
AREAS = list(AREA_MULTIPLIER)
POLLUTANTS = ["HC", "CO", "NOx", "nvPM", "CO2"]

# Public workbook aliases -> internal canonical names.
MODEL_COLUMN_ALIASES = ["飞机型号", "Aircraft Model"]
TAKEOFF_COLUMN_ALIASES = {
    "HC": ["起飞条件下HC", "HC at Takeoff Condition"],
    "CO": ["起飞条件下CO", "CO at Takeoff Condition"],
    "NOx": ["起飞条件下NOx", "起飞条件下NOₓ", "NOx at Takeoff Condition", "NOₓ at Takeoff Condition"],
    "nvPM": ["起飞条件下nvPM", "nvPM at Takeoff Condition"],
    "CO2": ["起飞条件下CO2", "起飞条件下CO₂", "CO2 at Takeoff Condition", "CO₂ at Takeoff Condition"],
}
IDLE_COLUMN_ALIASES = {
    "HC": ["怠速条件下HC", "HC at Idle Condition"],
    "CO": ["怠速条件下CO", "CO at Idle Condition"],
    "NOx": ["怠速条件下NOx", "怠速条件下NOₓ", "NOx at Idle Condition", "NOₓ at Idle Condition"],
    "nvPM": ["怠速条件下nvPM", "nvPM at Idle Condition"],
    "CO2": ["怠速条件下CO2", "怠速条件下CO₂", "CO2 at Idle Condition", "CO₂ at Idle Condition"],
}

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def normalize_text(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def normalize_model_name(x) -> str:
    return re.sub(r"\s+", " ", normalize_text(x).replace("（", "(").replace("）", ")")).strip()


def clean_area_name(x) -> str:
    s = normalize_text(x)
    s = re.sub(r"（.*?）|\(.*?\)", "", s)
    return s.strip()


def first_existing(columns, aliases):
    for name in aliases:
        if name in columns:
            return name
    return None


def normalize_unit(x) -> str:
    """Normalize factor-unit text to 'g/MJ', 'mg/MJ', or ''."""
    s = normalize_text(x).replace(" ", "").lower()
    s = s.replace("·", "/").replace("mj-1", "/mj").replace("mj^-1", "/mj")
    if "mg/mj" in s:
        return "mg/MJ"
    if "g/mj" in s:
        return "g/MJ"
    return ""


def to_g_per_mj(values: pd.Series, unit: str) -> pd.Series:
    out = pd.to_numeric(values, errors="coerce")
    if unit == "mg/MJ":
        out = out / 1000.0
    elif unit not in ("g/MJ", ""):
        raise ValueError(f"Unsupported emission-factor unit: {unit}")
    return out


def extract_airport_codes(airport_folder: Path, output_file: Path) -> pd.DataFrame:
    airport_info = []
    for path in sorted(airport_folder.glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        airport_name = path.stem
        airport_code = airport_name[:3].upper()
        airport_info.append({
            "机场完整文件名": path.name,
            "机场名称": airport_name,
            "机场代码": airport_code,
        })
    airport_df = pd.DataFrame(airport_info)
    airport_df.to_excel(output_file, index=False, engine="openpyxl")
    print(f"Airport list created: {len(airport_df)} file(s)")
    return airport_df


def find_header_row(raw_df: pd.DataFrame):
    for i in range(min(5, len(raw_df))):
        vals = {normalize_text(v) for v in raw_df.iloc[i].tolist()}
        if {"分属区域", "速度", "MJ"}.issubset(vals):
            return i
    return None


def standardize_airport_sheet(raw_df: pd.DataFrame) -> pd.DataFrame:
    raw_df = raw_df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    if raw_df.empty:
        raise ValueError("Airport worksheet is empty.")

    header_row = find_header_row(raw_df)
    if header_row is None:
        raise ValueError("Header not found; required fields are 分属区域, 速度, and MJ.")

    data = raw_df.iloc[header_row + 1 :].copy().reset_index(drop=True)
    data.columns = [normalize_text(x) for x in raw_df.iloc[header_row].tolist()]

    required = ["分属区域", "速度", "MJ"]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Missing required airport fields: {missing}")

    data = data.dropna(subset=["分属区域"]).copy()
    data["分属区域"] = data["分属区域"].map(clean_area_name)
    data["速度"] = pd.to_numeric(data["速度"], errors="coerce")
    data["MJ"] = pd.to_numeric(data["MJ"], errors="coerce")
    data = data.dropna(subset=["速度", "MJ"])
    data = data[data["分属区域"].isin(AREAS)].copy()
    data["排放阶段"] = np.where(
        data["速度"] < SPEED_THRESHOLD_KMH, "滑行阶段", "起飞阶段"
    )
    return data


def load_model_attributes(path: Path) -> pd.DataFrame:
    """Read public emission-factor workbook and return factors in g/MJ."""
    raw = pd.read_excel(path, sheet_name="Sheet1", engine="openpyxl")
    raw.columns = [normalize_text(c) for c in raw.columns]

    model_col = first_existing(raw.columns, MODEL_COLUMN_ALIASES)
    if model_col is None:
        raise ValueError(f"No aircraft-model column found. Expected one of {MODEL_COLUMN_ALIASES}")

    selected: Dict[str, str] = {"model": model_col}
    for p in POLLUTANTS:
        t = first_existing(raw.columns, TAKEOFF_COLUMN_ALIASES[p])
        i = first_existing(raw.columns, IDLE_COLUMN_ALIASES[p])
        if t is None or i is None:
            raise ValueError(f"Missing emission-factor columns for {p}: takeoff={t}, idle={i}")
        selected[f"takeoff_{p}"] = t
        selected[f"idle_{p}"] = i

    # The first data row in the public workbook contains units such as (g/MJ)
    # and (mg/MJ). Read units before dropping that row.
    units: Dict[Tuple[str, str], str] = {}
    for p in POLLUTANTS:
        for phase in ("takeoff", "idle"):
            col = selected[f"{phase}_{p}"]
            units[(phase, p)] = normalize_unit(raw[col].iloc[0]) if len(raw) else ""

    df = pd.DataFrame({"飞机型号": raw[model_col]})
    df = df[df["飞机型号"].notna()].copy()
    df["飞机型号"] = df["飞机型号"].map(normalize_model_name)
    df["飞机型号_标准"] = df["飞机型号"]

    for p in POLLUTANTS:
        for phase, zh in (("takeoff", "起飞条件下"), ("idle", "怠速条件下")):
            source_col = selected[f"{phase}_{p}"]
            unit = units[(phase, p)]
            # If a workbook does not provide a unit row, g/MJ is assumed only
            # for backward compatibility and is stated in the console output.
            if unit == "":
                unit = "g/MJ"
                print(f"WARNING: no unit detected for {source_col}; assuming g/MJ.")
            df[f"{zh}{p}"] = to_g_per_mj(raw.loc[df.index, source_col], unit)

    factor_cols = ["飞机型号", "飞机型号_标准"] + [
        f"{phase}{p}" for p in POLLUTANTS for phase in ("起飞条件下", "怠速条件下")
    ]
    df = df[factor_cols].dropna(subset=["飞机型号_标准"]).reset_index(drop=True)
    print(f"Emission factors loaded: {len(df)} aircraft model(s); all factors normalized to g/MJ.")
    return df


def load_frequency(path: Path, target_year: int) -> pd.DataFrame:
    freq = pd.read_excel(path, sheet_name="Sheet1", engine="openpyxl")
    required = ["Time series", "Dep Airport Code", "Specific Aircraft Name", "Frequency"]
    missing = [c for c in required if c not in freq.columns]
    if missing:
        raise ValueError(f"Frequency workbook missing fields: {missing}")

    freq = freq[freq["Time series"] == target_year].copy()
    freq = freq.rename(columns={
        "Dep Airport Code": "机场代码",
        "Specific Aircraft Name": "飞机型号",
        "Frequency": "起飞频次",
    })
    freq = freq[["机场代码", "飞机型号", "起飞频次"]].copy()
    freq["机场代码"] = freq["机场代码"].astype(str).str.strip().str.upper()
    freq["飞机型号_标准"] = freq["飞机型号"].map(normalize_model_name)
    freq["起飞频次"] = pd.to_numeric(freq["起飞频次"], errors="coerce").fillna(0)
    freq = freq.groupby(["机场代码", "飞机型号_标准"], as_index=False)["起飞频次"].sum()
    print(f"{target_year} frequency data loaded: {len(freq)} airport-aircraft pair(s)")
    return freq


def get_frequency(frequency_df: pd.DataFrame, airport_code: str, model_std: str):
    matched = frequency_df[
        (frequency_df["机场代码"] == airport_code)
        & (frequency_df["飞机型号_标准"] == model_std)
    ]
    if matched.empty:
        return None, False
    return float(matched["起飞频次"].iloc[0]), True


def calculate_model_emission(table, model, factor_row, frequency):
    detail = table.copy()
    detail.insert(0, "机型", model)
    detail["区域倍率"] = detail["分属区域"].map(AREA_MULTIPLIER).fillna(1.0)
    detail["起飞频次"] = frequency

    for p in POLLUTANTS:
        takeoff_factor = float(factor_row[f"起飞条件下{p}"])
        idle_factor = float(factor_row[f"怠速条件下{p}"])
        detail[f"{p}排放因子_g_per_MJ"] = np.where(
            detail["速度"] < SPEED_THRESHOLD_KMH, idle_factor, takeoff_factor
        )
        detail[f"{p}分段排放_g_原始"] = detail["MJ"] * detail[f"{p}排放因子_g_per_MJ"]
        detail[f"{p}分段排放_g"] = detail[f"{p}分段排放_g_原始"] * detail["区域倍率"]
        detail[f"{p}分段排放_g_含频次"] = detail[f"{p}分段排放_g"] * frequency

    rows = []
    for area in AREAS:
        sub = detail[detail["分属区域"] == area].copy()
        row = {
            "机型": model,
            "分属区域": area,
            "起飞阶段MJ": sub.loc[sub["排放阶段"] == "起飞阶段", "MJ"].sum(),
            "滑行阶段MJ": sub.loc[sub["排放阶段"] == "滑行阶段", "MJ"].sum(),
            "总MJ": sub["MJ"].sum(),
            "区域倍率": AREA_MULTIPLIER[area],
            "起飞频次": frequency,
        }
        for p in POLLUTANTS:
            row[p] = sub[f"{p}分段排放_g"].sum()
            row[f"{p}_含频次"] = sub[f"{p}分段排放_g_含频次"].sum()
        rows.append(row)
    return pd.DataFrame(rows), detail


def process_airport(
    airport_file: Path,
    airport_code: str,
    airport_full_name: str,
    frequency_2019: pd.DataFrame,
    model_attr: pd.DataFrame,
    missing_factor_records: list,
    missing_frequency_records: list,
):
    print("\n" + "=" * 78)
    print(f"Airport: {airport_full_name} ({airport_code})")
    print("=" * 78)

    try:
        sheets = pd.read_excel(airport_file, sheet_name=None, header=None, engine="openpyxl")
    except Exception as exc:
        print(f"ERROR: cannot read airport workbook: {exc}")
        return None

    airport_output_dir = OUTPUT_ROOT / airport_full_name
    airport_output_dir.mkdir(parents=True, exist_ok=True)
    all_model_area = []
    all_segment_detail = []

    for sheet_name, raw_data in sheets.items():
        if raw_data.empty:
            continue
        model = normalize_text(raw_data.iloc[0, 0])
        model_std = normalize_model_name(model)
        if not model_std:
            missing_factor_records.append({
                "机场代码": airport_code,
                "机场名称": airport_full_name,
                "工作表名称": sheet_name,
                "飞机型号": "",
                "原因": "A1为空，未读取到飞机型号",
            })
            continue

        factor_match = model_attr[model_attr["飞机型号_标准"] == model_std]
        if factor_match.empty:
            print(f"SKIP {model}: no emission factor match")
            missing_factor_records.append({
                "机场代码": airport_code,
                "机场名称": airport_full_name,
                "工作表名称": sheet_name,
                "飞机型号": model,
                "原因": "无排放因子匹配",
            })
            continue

        frequency, freq_ok = get_frequency(frequency_2019, airport_code, model_std)
        if not freq_ok:
            print(f"SKIP {model}: no {TARGET_YEAR} frequency match (no default frequency is used)")
            missing_frequency_records.append({
                "机场代码": airport_code,
                "机场名称": airport_full_name,
                "工作表名称": sheet_name,
                "飞机型号": model,
                "原因": f"{TARGET_YEAR}年无频次匹配；已跳过",
            })
            continue
        if frequency <= 0:
            print(f"SKIP {model}: matched frequency is {frequency}")
            continue

        try:
            table = standardize_airport_sheet(raw_data)
            if table.empty:
                print(f"SKIP {model}: no valid segments")
                continue
            model_area, segment_detail = calculate_model_emission(
                table, model, factor_match.iloc[0], frequency
            )
        except Exception as exc:
            print(f"ERROR processing {model}: {exc}")
            continue

        all_model_area.append(model_area)
        all_segment_detail.append(segment_detail)

        safe_model = re.sub(r"[\\/:*?\"<>|]", "_", model)
        model_file = airport_output_dir / f"{safe_model}_排放计算结果.xlsx"
        with pd.ExcelWriter(model_file, engine="openpyxl") as writer:
            model_area.to_excel(writer, sheet_name="区域汇总", index=False)
            segment_detail.to_excel(writer, sheet_name="分段明细", index=False)

    if not all_model_area:
        print("No valid aircraft results for this airport.")
        return None

    area_detail = pd.concat(all_model_area, ignore_index=True)
    segment_detail_all = pd.concat(all_segment_detail, ignore_index=True)
    total_single = {p: float(area_detail[p].sum()) for p in POLLUTANTS}
    total_annual = {p: float(area_detail[f"{p}_含频次"].sum()) for p in POLLUTANTS}

    area_single = area_detail.groupby("分属区域")[POLLUTANTS].sum().reindex(AREAS).fillna(0)
    annual_cols = [f"{p}_含频次" for p in POLLUTANTS]
    area_annual = area_detail.groupby("分属区域")[annual_cols].sum().reindex(AREAS).fillna(0)
    area_annual.columns = POLLUTANTS
    stage_mj = (
        segment_detail_all.groupby("排放阶段")["MJ"].sum()
        .reindex(["起飞阶段", "滑行阶段"]).fillna(0).reset_index()
    )

    summary_file = airport_output_dir / f"{airport_full_name}_排放汇总.xlsx"
    with pd.ExcelWriter(summary_file, engine="openpyxl") as writer:
        pd.DataFrame([total_single]).to_excel(writer, sheet_name="1单次排放_g", index=False)
        pd.DataFrame([total_annual]).to_excel(writer, sheet_name="2年度排放_g", index=False)
        area_single.to_excel(writer, sheet_name="3区域单次排放_g")
        area_annual.to_excel(writer, sheet_name="4区域年度排放_g")
        area_detail.to_excel(writer, sheet_name="5机型区域明细", index=False)
        stage_mj.to_excel(writer, sheet_name="6阶段MJ汇总", index=False)
        segment_detail_all.to_excel(writer, sheet_name="7全部分段明细", index=False)

    return {
        "机场名称": airport_full_name,
        "机场代码": airport_code,
        "总排放（不含频次）": total_single,
        "总排放（含频次）": total_annual,
        "区域排放（不含频次）": area_single.to_dict(orient="index"),
        "区域排放（含频次）": area_annual.to_dict(orient="index"),
    }


def main():
    print("=" * 78)
    print("Airport emission inventory: phase-specific factors")
    print(f"Speed < {SPEED_THRESHOLD_KMH} km/h -> idle/low-thrust factors")
    print(f"Speed >= {SPEED_THRESHOLD_KMH} km/h -> take-off factors")
    print("All reported pollutant masses are in grams.")
    print("=" * 78)

    for path, label in [
        (AIRPORT_FOLDER, "airport data folder"),
        (MODEL_ATTR_PATH, "emission-factor workbook"),
        (FREQUENCY_PATH, "frequency workbook"),
    ]:
        if not path.exists():
            raise FileNotFoundError(f"{label} not found: {path}")

    model_attr = load_model_attributes(MODEL_ATTR_PATH)
    frequency_2019 = load_frequency(FREQUENCY_PATH, TARGET_YEAR)
    airport_code_df = extract_airport_codes(AIRPORT_FOLDER, OUTPUT_ROOT / "所有机场代码清单.xlsx")

    all_airport_results = []
    missing_factor_records = []
    missing_frequency_records = []

    for idx, row in airport_code_df.iterrows():
        print(f"\nProgress: {idx + 1}/{len(airport_code_df)}")
        result = process_airport(
            airport_file=AIRPORT_FOLDER / row["机场完整文件名"],
            airport_code=row["机场代码"],
            airport_full_name=row["机场名称"],
            frequency_2019=frequency_2019,
            model_attr=model_attr,
            missing_factor_records=missing_factor_records,
            missing_frequency_records=missing_frequency_records,
        )
        if result is not None:
            all_airport_results.append(result)

    with pd.ExcelWriter(OUTPUT_ROOT / "未匹配检查清单.xlsx", engine="openpyxl") as writer:
        pd.DataFrame(missing_factor_records).to_excel(writer, sheet_name="无排放因子机型", index=False)
        pd.DataFrame(missing_frequency_records).to_excel(writer, sheet_name="无频次匹配", index=False)

    if not all_airport_results:
        print("No valid airport results were produced.")
        return

    global_total = {p: 0.0 for p in POLLUTANTS}
    global_total_freq = {p: 0.0 for p in POLLUTANTS}
    global_area = {area: {p: 0.0 for p in POLLUTANTS} for area in AREAS}
    global_area_freq = {area: {p: 0.0 for p in POLLUTANTS} for area in AREAS}
    airport_detail = []

    for res in all_airport_results:
        for p in POLLUTANTS:
            global_total[p] += res["总排放（不含频次）"][p]
            global_total_freq[p] += res["总排放（含频次）"][p]
        for area in AREAS:
            for p in POLLUTANTS:
                global_area[area][p] += res["区域排放（不含频次）"].get(area, {}).get(p, 0.0)
                global_area_freq[area][p] += res["区域排放（含频次）"].get(area, {}).get(p, 0.0)
        detail = {"机场名称": res["机场名称"], "机场代码": res["机场代码"]}
        for p in POLLUTANTS:
            detail[f"{p} (g)"] = res["总排放（含频次）"][p]
        airport_detail.append(detail)

    global_file = OUTPUT_ROOT / "所有机场全局排放汇总.xlsx"
    with pd.ExcelWriter(global_file, engine="openpyxl") as writer:
        pd.DataFrame([global_total]).to_excel(writer, sheet_name="1单次总排放_g", index=False)
        pd.DataFrame([global_total_freq]).to_excel(writer, sheet_name="2年度总排放_g", index=False)
        pd.DataFrame(global_area).T.to_excel(writer, sheet_name="3区域单次排放_g")
        pd.DataFrame(global_area_freq).T.to_excel(writer, sheet_name="4区域年度排放_g")
        pd.DataFrame(airport_detail).to_excel(writer, sheet_name="5机场排放明细", index=False)
        airport_code_df[["机场名称", "机场代码"]].to_excel(writer, sheet_name="6机场代码清单", index=False)
        pd.DataFrame({
            "参数": [
                "速度阈值(km/h)", "小于阈值阶段", "大于等于阈值阶段", "目标年份",
                "跑道倍率", "滑行道倍率", "停机坪倍率", "快滑道倍率", "联络道倍率",
                "排放输出单位",
            ],
            "取值": [
                SPEED_THRESHOLD_KMH, "滑行阶段/怠速因子", "起飞阶段/起飞因子", TARGET_YEAR,
                AREA_MULTIPLIER["跑道"], AREA_MULTIPLIER["滑行道"], AREA_MULTIPLIER["停机坪"],
                AREA_MULTIPLIER["快滑道"], AREA_MULTIPLIER["联络道"], "g",
            ],
        }).to_excel(writer, sheet_name="7计算口径", index=False)

    print("\nCompleted.")
    print(f"Airports successfully processed: {len(all_airport_results)}")
    print(f"Missing factor records: {len(missing_factor_records)}")
    print(f"Missing frequency records: {len(missing_frequency_records)}")
    print(f"Global output: {global_file}")


if __name__ == "__main__":
    main()
