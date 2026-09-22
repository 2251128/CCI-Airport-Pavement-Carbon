# -*- coding: utf-8 -*-

import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ============================================================

# ============================================================


BASE_DIR = Path(__file__).resolve().parents[1]
AIRPORT_FOLDER = str(BASE_DIR / 'data' / 'demo_airport')
MODEL_ATTR_PATH = str(BASE_DIR / 'data' / 'aircraft_emission_factors.xlsx')
FREQUENCY_PATH = str(BASE_DIR / 'data' / 'national_aircraft_frequency.xlsx')
OUTPUT_ROOT = str(BASE_DIR / 'outputs' / 'national_emission_inventory')


TARGET_YEAR = 2019


SPEED_THRESHOLD_KMH = 36.0



AREA_MULTIPLIER = {
    "跑道": 1.0,
    "滑行道": 2.0,
    "停机坪": 2.0,
    "快滑道": 2.0,
    "联络道": 2.0,
 }

AREAS = ["跑道", "滑行道", "停机坪", "快滑道", "联络道"]
POLLUTANTS = ["HC", "CO", "NOx", "nvPM", "CO2"]

os.makedirs(OUTPUT_ROOT, exist_ok=True)


# ============================================================

# ============================================================

def normalize_text(x):
    if pd.isna(x):
        return ""
    return str(x).strip()


def normalize_model_name(x):
    return normalize_text(x).replace("（", "(").replace("）", ")")


def clean_area_name(x):
    s = normalize_text(x)
    s = pd.Series([s]).str.replace(r"（.*?）|\(.*?\)", "", regex=True).iloc[0]
    return s.strip()


def extract_airport_codes(airport_folder, output_file):
    airport_info = []

    for filename in sorted(os.listdir(airport_folder)):
        if filename.lower().endswith(".xlsx") and not filename.startswith("~$"):
            airport_name = os.path.splitext(filename)[0]
            airport_code = airport_name[:3].upper()

            airport_info.append({
                "机场完整文件名": filename,
                "机场名称": airport_name,
                "机场代码": airport_code,
            })

    airport_df = pd.DataFrame(airport_info)
    airport_df.to_excel(output_file, index=False, engine="openpyxl")

    print(f"✅机场代码提取完成，共 {len(airport_df)} 个机场")
    return airport_df


def find_header_row(raw_df):
    max_rows = min(5, len(raw_df))

    for i in range(max_rows):
        vals = [normalize_text(v) for v in raw_df.iloc[i].tolist()]
        vals_set = set(vals)
        if {"分属区域", "速度", "MJ"}.issubset(vals_set):
            return i

    return None


def standardize_airport_sheet(raw_df):
    raw_df = raw_df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)

    if raw_df.empty:
        raise ValueError("工作表为空")

    header_row = find_header_row(raw_df)
    if header_row is None:
        raise ValueError("未找到表头：至少需要包含‘分属区域’、‘速度’和‘MJ’")

    columns = [normalize_text(x) for x in raw_df.iloc[header_row].tolist()]
    data = raw_df.iloc[header_row + 1:].copy().reset_index(drop=True)
    data.columns = columns

    required = ["分属区域", "速度", "MJ"]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"缺少必要字段：{missing}")

    data = data.dropna(subset=["分属区域"]).copy()
    data["分属区域"] = data["分属区域"].apply(clean_area_name)
    data["速度"] = pd.to_numeric(data["速度"], errors="coerce")
    data["MJ"] = pd.to_numeric(data["MJ"], errors="coerce")

    
    data = data.dropna(subset=["速度", "MJ"]).copy()

    
    data = data[data["分属区域"].isin(AREAS)].copy()

    
    data["排放阶段"] = np.where(
        data["速度"] < SPEED_THRESHOLD_KMH,
        "滑行阶段",
        "起飞阶段"
    )

    return data


# ============================================================

# ============================================================

def load_model_attributes(path):
    df = pd.read_excel(path, sheet_name="Sheet1", engine="openpyxl")
    df.columns = [normalize_text(c) for c in df.columns]

    required_cols = ["飞机型号"]
    for p in POLLUTANTS:
        required_cols.append(f"起飞条件下{p}")
        required_cols.append(f"怠速条件下{p}")

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            "不同机型属性表缺少以下字段：\n" + "\n".join(missing)
        )

    df = df[required_cols].copy()
    df["飞机型号_标准"] = df["飞机型号"].apply(normalize_model_name)

    
    for p in POLLUTANTS:
        df[f"起飞条件下{p}"] = pd.to_numeric(df[f"起飞条件下{p}"], errors="coerce")
        df[f"怠速条件下{p}"] = pd.to_numeric(df[f"怠速条件下{p}"], errors="coerce")

    print(f"✅机型排放属性读取完成：{len(df)} 种机型")
    return df


# ============================================================

# ============================================================

def load_frequency(path, target_year):
    freq = pd.read_excel(path, sheet_name="Sheet1", engine="openpyxl")

    required = ["Time series", "Dep Airport Code", "Specific Aircraft Name", "Frequency"]
    missing = [c for c in required if c not in freq.columns]
    if missing:
        raise ValueError(f"频次表缺少字段：{missing}")

    freq = freq[freq["Time series"] == target_year].copy()
    freq = freq.rename(columns={
        "Dep Airport Code": "机场代码",
        "Specific Aircraft Name": "飞机型号",
        "Frequency": "起飞频次",
    })

    freq = freq[["机场代码", "飞机型号", "起飞频次"]].copy()
    freq["机场代码"] = freq["机场代码"].astype(str).str.strip().str.upper()
    freq["飞机型号_标准"] = freq["飞机型号"].apply(normalize_model_name)
    freq["起飞频次"] = pd.to_numeric(freq["起飞频次"], errors="coerce").fillna(0)

    
    freq = (
        freq.groupby(["机场代码", "飞机型号_标准"], as_index=False)["起飞频次"]
        .sum()
    )

    print(f"✅{target_year}年频次数据读取完成：{len(freq)} 条机场-机型记录")
    return freq


def get_frequency(frequency_df, airport_code, model_std):
    matched = frequency_df[
        (frequency_df["机场代码"] == airport_code)
        & (frequency_df["飞机型号_标准"] == model_std)
    ]

    if matched.empty:
        
        
        return 1.0, False

    return float(matched["起飞频次"].iloc[0]), True


# ============================================================

# ============================================================

def calculate_model_emission(table, model, factor_row, frequency):
    detail = table.copy()
    detail.insert(0, "机型", model)

    detail["区域倍率"] = detail["分属区域"].map(AREA_MULTIPLIER).fillna(1.0)
    detail["起飞频次"] = frequency

    
    for p in POLLUTANTS:
        takeoff_factor = float(factor_row[f"起飞条件下{p}"])
        idle_factor = float(factor_row[f"怠速条件下{p}"])

        detail[f"{p}排放因子"] = np.where(
            detail["速度"] < SPEED_THRESHOLD_KMH,
            idle_factor,
            takeoff_factor
        )

        
        detail[f"{p}分段排放_原始"] = detail["MJ"] * detail[f"{p}排放因子"]

        
        detail[f"{p}分段排放"] = (
            detail[f"{p}分段排放_原始"] * detail["区域倍率"]
        )

        
        detail[f"{p}分段排放_含频次"] = (
            detail[f"{p}分段排放"] * frequency
        )

    
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
            row[p] = sub[f"{p}分段排放"].sum()
            row[f"{p}_含频次"] = sub[f"{p}分段排放_含频次"].sum()

        rows.append(row)

    summary = pd.DataFrame(rows)
    return summary, detail


# ============================================================

# ============================================================

def process_airport(
    airport_file,
    airport_code,
    airport_full_name,
    frequency_2019,
    model_attr,
    missing_factor_records,
    missing_frequency_records,
):
    print("\n" + "=" * 78)
    print(f"开始处理机场：{airport_full_name}")
    print(f"机场代码：{airport_code}")
    print("=" * 78)

    try:
        sheets = pd.read_excel(
            airport_file,
            sheet_name=None,
            header=None,
            engine="openpyxl"
        )
        print(f"包含机型数量：{len(sheets)}")
    except Exception as e:
        print(f"❌机场文件读取失败：{e}")
        return None

    airport_output_dir = os.path.join(OUTPUT_ROOT, airport_full_name)
    os.makedirs(airport_output_dir, exist_ok=True)

    all_model_area = []
    all_segment_detail = []

    for sheet_name, raw_data in sheets.items():
        # ==================================================
        
        
        # ==================================================
        if raw_data.empty:
            print(f"⚠️ 工作表 {sheet_name} 为空，跳过")
            continue

        model = normalize_text(raw_data.iloc[0, 0])

        if model == "":
            print(f"⚠️ 工作表 {sheet_name} 的 A1 为空，无法确定飞机型号，跳过")
            missing_factor_records.append({
                "机场代码": airport_code,
                "机场名称": airport_full_name,
                "工作表名称": sheet_name,
                "飞机型号": "",
                "原因": "A1为空，未读取到飞机型号",
            })
            continue

        model_std = normalize_model_name(model)

        print(f"\n工作表：{sheet_name}")
        print(f"A1读取飞机型号：{model}")

        try:
            
            factor_match = model_attr[model_attr["飞机型号_标准"] == model_std]
            if factor_match.empty:
                print(f"⚠️ {model} 无排放因子，跳过")
                missing_factor_records.append({
                    "机场代码": airport_code,
                    "机场名称": airport_full_name,
                    "飞机型号": model,
                })
                continue

            factor_row = factor_match.iloc[0]

            
            frequency, freq_ok = get_frequency(
                frequency_2019,
                airport_code,
                model_std
            )

            if not freq_ok:
                print("⚠️ 无频次匹配，暂按旧代码默认频次=1")
                missing_frequency_records.append({
                    "机场代码": airport_code,
                    "机场名称": airport_full_name,
                    "飞机型号": model,
                    "临时使用频次": frequency,
                })
            else:
                print(f"起飞频次 = {frequency}")

            
            table = standardize_airport_sheet(raw_data)
            if table.empty:
                print("⚠️ 有效分段为空，跳过")
                continue

            
            model_area, segment_detail = calculate_model_emission(
                table,
                model,
                factor_row,
                frequency,
            )

            all_model_area.append(model_area)
            all_segment_detail.append(segment_detail)

            
            safe_model = model.replace("/", "_").replace("\\", "_").replace(":", "_")
            model_file = os.path.join(
                airport_output_dir,
                f"{safe_model}_排放计算结果.xlsx"
            )

            with pd.ExcelWriter(model_file, engine="openpyxl") as writer:
                model_area.to_excel(
                    writer,
                    sheet_name="区域汇总",
                    index=False
                )
                segment_detail.to_excel(
                    writer,
                    sheet_name="分段明细",
                    index=False
                )

            taxi_count = int((segment_detail["排放阶段"] == "滑行阶段").sum())
            takeoff_count = int((segment_detail["排放阶段"] == "起飞阶段").sum())
            print(
                f"✅ {model} 完成：起飞阶段分段 {takeoff_count} 条，"
                f"滑行阶段分段 {taxi_count} 条"
            )

        except Exception as e:
            print(f"❌ {model} 处理失败：{e}")
            continue

    if not all_model_area:
        print("❌该机场无有效机型结果")
        return None

    area_detail = pd.concat(all_model_area, ignore_index=True)
    segment_detail_all = pd.concat(all_segment_detail, ignore_index=True)

    
    total_single = {p: float(area_detail[p].sum()) for p in POLLUTANTS}
    total_annual = {p: float(area_detail[f"{p}_含频次"].sum()) for p in POLLUTANTS}

    
    area_single = area_detail.groupby("分属区域")[POLLUTANTS].sum().reindex(AREAS).fillna(0)
    annual_cols = [f"{p}_含频次" for p in POLLUTANTS]
    area_annual = (
        area_detail.groupby("分属区域")[annual_cols]
        .sum()
        .reindex(AREAS)
        .fillna(0)
    )
    area_annual.columns = POLLUTANTS

    
    stage_mj = (
        segment_detail_all.groupby("排放阶段")["MJ"]
        .sum()
        .reindex(["起飞阶段", "滑行阶段"])
        .fillna(0)
        .reset_index()
    )

    summary_file = os.path.join(
        airport_output_dir,
        f"{airport_full_name}_排放汇总.xlsx"
    )

    with pd.ExcelWriter(summary_file, engine="openpyxl") as writer:
        pd.DataFrame([total_single]).to_excel(
            writer,
            sheet_name="1单次排放",
            index=False
        )
        pd.DataFrame([total_annual]).to_excel(
            writer,
            sheet_name="2年度排放含频次",
            index=False
        )
        area_single.to_excel(
            writer,
            sheet_name="3区域单次排放"
        )
        area_annual.to_excel(
            writer,
            sheet_name="4区域年度排放"
        )
        area_detail.to_excel(
            writer,
            sheet_name="5机型区域明细",
            index=False
        )
        stage_mj.to_excel(
            writer,
            sheet_name="6阶段MJ汇总",
            index=False
        )
        segment_detail_all.to_excel(
            writer,
            sheet_name="7全部分段明细",
            index=False
        )

    print(f"✅ {airport_full_name} 汇总完成")

    
    return {
        "机场名称": airport_full_name,
        "机场代码": airport_code,
        "总排放（不含频次）": total_single,
        "总排放（含频次）": total_annual,
        "区域排放（不含频次）": area_single.to_dict(orient="index"),
        "区域排放（含频次）": area_annual.to_dict(orient="index"),
    }


# ============================================================

# ============================================================

def main():
    print("=" * 78)
    print("236机场污染物排放计算：36 km/h 分阶段版")
    print(f"速度 < {SPEED_THRESHOLD_KMH} km/h：滑行阶段 → 怠速条件因子")
    print(f"速度 >= {SPEED_THRESHOLD_KMH} km/h：起飞阶段 → 起飞条件因子")
    print("=" * 78)

    
    for path, label in [
        (AIRPORT_FOLDER, "机场数据文件夹"),
        (MODEL_ATTR_PATH, "不同机型属性表"),
        (FREQUENCY_PATH, "频次表"),
    ]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"{label}不存在：{path}")

    
    model_attr = load_model_attributes(MODEL_ATTR_PATH)
    frequency_2019 = load_frequency(FREQUENCY_PATH, TARGET_YEAR)

    airport_code_file = os.path.join(OUTPUT_ROOT, "所有机场代码清单.xlsx")
    airport_code_df = extract_airport_codes(
        AIRPORT_FOLDER,
        airport_code_file
    )

    print("\n" + "=" * 78)
    print("开始批量计算机场排放")
    print("=" * 78)

    all_airport_results = []
    missing_factor_records = []
    missing_frequency_records = []

    total_airports = len(airport_code_df)

    for idx, row in airport_code_df.iterrows():
        print("\n" + "#" * 78)
        print(f"当前进度：{idx + 1}/{total_airports}")
        print("#" * 78)

        airport_file = os.path.join(
            AIRPORT_FOLDER,
            row["机场完整文件名"]
        )

        result = process_airport(
            airport_file=airport_file,
            airport_code=row["机场代码"],
            airport_full_name=row["机场名称"],
            frequency_2019=frequency_2019,
            model_attr=model_attr,
            missing_factor_records=missing_factor_records,
            missing_frequency_records=missing_frequency_records,
        )

        if result is not None:
            all_airport_results.append(result)

    
    check_file = os.path.join(OUTPUT_ROOT, "未匹配检查清单.xlsx")
    with pd.ExcelWriter(check_file, engine="openpyxl") as writer:
        pd.DataFrame(missing_factor_records).to_excel(
            writer,
            sheet_name="无排放因子机型",
            index=False
        )
        pd.DataFrame(missing_frequency_records).to_excel(
            writer,
            sheet_name="无频次匹配",
            index=False
        )

    if not all_airport_results:
        print("❌没有有效机场结果")
        return

    # ========================================================
    
    # ========================================================
    global_total = {p: 0.0 for p in POLLUTANTS}
    global_total_freq = {p: 0.0 for p in POLLUTANTS}

    global_area = {
        area: {p: 0.0 for p in POLLUTANTS}
        for area in AREAS
    }
    global_area_freq = {
        area: {p: 0.0 for p in POLLUTANTS}
        for area in AREAS
    }

    airport_detail = []

    for res in all_airport_results:
        for p in POLLUTANTS:
            global_total[p] += res["总排放（不含频次）"][p]
            global_total_freq[p] += res["总排放（含频次）"][p]

        for area in AREAS:
            for p in POLLUTANTS:
                global_area[area][p] += (
                    res["区域排放（不含频次）"]
                    .get(area, {})
                    .get(p, 0.0)
                )
                global_area_freq[area][p] += (
                    res["区域排放（含频次）"]
                    .get(area, {})
                    .get(p, 0.0)
                )

        detail = {
            "机场名称": res["机场名称"],
            "机场代码": res["机场代码"],
        }
        for p in POLLUTANTS:
            detail[p] = res["总排放（含频次）"][p]
        airport_detail.append(detail)

    airport_detail_df = pd.DataFrame(airport_detail)

    global_file = os.path.join(
        OUTPUT_ROOT,
        "所有机场全局排放汇总.xlsx"
    )

    with pd.ExcelWriter(global_file, engine="openpyxl") as writer:
        pd.DataFrame([global_total]).to_excel(
            writer,
            sheet_name="1单次总排放",
            index=False
        )
        pd.DataFrame([global_total_freq]).to_excel(
            writer,
            sheet_name="2年度总排放",
            index=False
        )
        pd.DataFrame(global_area).T.to_excel(
            writer,
            sheet_name="3区域单次排放"
        )
        pd.DataFrame(global_area_freq).T.to_excel(
            writer,
            sheet_name="4区域年度排放"
        )
        airport_detail_df.to_excel(
            writer,
            sheet_name="5机场排放明细",
            index=False
        )
        airport_code_df[["机场名称", "机场代码"]].to_excel(
            writer,
            sheet_name="6机场代码清单",
            index=False
        )
        pd.DataFrame({
            "参数": [
                "速度阈值(km/h)",
                "小于阈值阶段",
                "大于等于阈值阶段",
                "目标年份",
                "跑道倍率",
                "滑行道倍率",
                "停机坪倍率",
                "快滑道倍率",
                "联络道倍率",
            ],
            "取值": [
                SPEED_THRESHOLD_KMH,
                "滑行阶段/怠速因子",
                "起飞阶段/起飞因子",
                TARGET_YEAR,
                AREA_MULTIPLIER["跑道"],
                AREA_MULTIPLIER["滑行道"],
                AREA_MULTIPLIER["停机坪"],
                AREA_MULTIPLIER["快滑道"],
                AREA_MULTIPLIER["联络道"],
            ]
        }).to_excel(
            writer,
            sheet_name="7计算口径",
            index=False
        )

    print("\n" + "=" * 78)
    print("✅所有机场全局排放汇总完成")
    print(f"成功处理机场数量：{len(all_airport_results)}")
    print(f"无排放因子机型记录：{len(missing_factor_records)}")
    print(f"无频次匹配记录：{len(missing_frequency_records)}")
    print(f"全局汇总：{global_file}")
    print(f"未匹配检查：{check_file}")
    print("=" * 78)


if __name__ == "__main__":
    main()
