from pathlib import Path
import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Map
from pyecharts.globals import ThemeType

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "data" / "supplementary_data_6_aggregated_results.xlsx"
OUTPUT_FILE = ROOT / "outputs" / "cectol_by_region.html"

df = pd.read_excel(INPUT_FILE, sheet_name="CEctol by Region")
region_cectol = dict(zip(df["Geographical region"], pd.to_numeric(df["CEctol"], errors="coerce")))
province_to_region = {
    "辽宁省":"Northeast", "吉林省":"Northeast", "黑龙江省":"Northeast",
    "上海市":"East China", "江苏省":"East China", "浙江省":"East China", "安徽省":"East China", "福建省":"East China", "江西省":"East China", "山东省":"East China",
    "河南省":"Central China", "湖北省":"Central China", "湖南省":"Central China",
    "北京市":"North China", "天津市":"North China", "河北省":"North China", "山西省":"North China", "内蒙古自治区":"North China",
    "广东省":"South China", "广西壮族自治区":"South China", "海南省":"South China",
    "陕西省":"Northwest", "甘肃省":"Northwest", "青海省":"Northwest", "宁夏回族自治区":"Northwest", "新疆维吾尔自治区":"Northwest",
    "重庆市":"Southwest", "四川省":"Southwest", "贵州省":"Southwest", "云南省":"Southwest", "西藏自治区":"Southwest"
}
region_colors = {
    "Northeast":"#FFFF00", "East China":"#86E57F", "Central China":"#33FFCC",
    "North China":"#1133FF", "South China":"#00E5E5", "Northwest":"#55C8CB", "Southwest":"#33CCFF"
}
map_data = [(province, float(region_cectol[region])) for province, region in province_to_region.items()]
max_val = max(region_cectol.values())
taiwan_value = max_val + 1
map_data.append(("台湾省", taiwan_value))
pieces=[]
eps=1e-6
for region, value in region_cectol.items():
    pieces.append({"min":float(value)-eps,"max":float(value)+eps,"label":f"{region}: {value:,.0f}","color":region_colors[region]})
pieces.append({"min":taiwan_value,"max":taiwan_value,"label":"no data","color":"#FFFACD"})
chart=(Map(init_opts=opts.InitOpts(theme=ThemeType.LIGHT,width="1200px",height="800px"))
       .add("Regional CEctol",map_data,"china",label_opts=opts.LabelOpts(is_show=False),is_map_symbol_show=False)
       .set_global_opts(title_opts=opts.TitleOpts(title="CEctol by Chinese geographic region (2019)"),
                        visualmap_opts=opts.VisualMapOpts(is_piecewise=True,pieces=pieces,pos_right="5%",pos_top="50%")))
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
chart.render(str(OUTPUT_FILE))
print(f"Saved: {OUTPUT_FILE}")
