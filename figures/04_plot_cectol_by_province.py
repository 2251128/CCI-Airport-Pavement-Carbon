from pathlib import Path
import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Map
from pyecharts.globals import ThemeType

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "data" / "supplementary_data_6_aggregated_results.xlsx"
OUT_DIR = ROOT / "outputs"

province_en2cn = {
    "Shanghai":"上海市", "Yunnan Province":"云南省", "Inner Mongolia Autonomous Region":"内蒙古自治区",
    "Beijing":"北京市", "Jilin Province":"吉林省", "Sichuan Province":"四川省", "Tianjin":"天津市",
    "Ningxia Hui Autonomous Region":"宁夏回族自治区", "Anhui Province":"安徽省", "Shandong Province":"山东省",
    "Shanxi Province":"山西省", "Guangdong Province":"广东省", "Guangxi Zhuang Autonomous Region":"广西壮族自治区",
    "Xinjiang Uygur Autonomous Region":"新疆维吾尔自治区", "Jiangsu Province":"江苏省", "Jiangxi Province":"江西省",
    "Hebei Province":"河北省", "Henan Province":"河南省", "Zhejiang Province":"浙江省", "Hainan Province":"海南省",
    "Hubei Province":"湖北省", "Hunan Province":"湖南省", "Gansu Province":"甘肃省", "Fujian Province":"福建省",
    "Xizang Autonomous Region":"西藏自治区", "Guizhou Province":"贵州省", "Liaoning Province":"辽宁省",
    "Chongqing Municipality":"重庆市", "Shaanxi Province":"陕西省", "Qinghai Province":"青海省", "Heilongjiang Province":"黑龙江省"
}

def build_map(values, title, output_name):
    bins = pd.qcut(values, q=5, labels=range(1,6), duplicates="drop")
    data=[]
    for province, tier in zip(df["Province"], bins):
        if province in province_en2cn:
            data.append((province_en2cn[province], int(tier)))
    data.append(("台湾省", 6))
    colors=["#FFFF00","#86E57F","#55C8CB","#6698E7","#1133FF","#FFFACD"]
    pieces=[{"min":i,"max":i,"label":f"Tier {i}","color":colors[i-1]} for i in range(1,6)]
    pieces.append({"min":6,"max":6,"label":"no data","color":colors[5]})
    chart=(Map(init_opts=opts.InitOpts(theme=ThemeType.LIGHT,width="1200px",height="800px"))
           .add(title,data,"china",label_opts=opts.LabelOpts(is_show=False),is_map_symbol_show=False)
           .set_global_opts(title_opts=opts.TitleOpts(title=title),visualmap_opts=opts.VisualMapOpts(is_piecewise=True,pieces=pieces,pos_right="5%",pos_top="50%")))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    chart.render(str(OUT_DIR/output_name))

df = pd.read_excel(INPUT_FILE, sheet_name="CEctol by Province")
build_map(pd.to_numeric(df["CEctol (dimensionless)"], errors="coerce"), "Provincial CEctol groups (2019)", "cectol_by_province.html")
build_map(pd.to_numeric(df["Per capita CEctol"], errors="coerce"), "Per-capita CEctol groups (2019)", "per_capita_cectol_by_province.html")
print(f"Saved maps to: {OUT_DIR}")
