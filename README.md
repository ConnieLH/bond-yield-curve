# 债券收益率曲线：本地使用说明

## 启动页面

在 PowerShell 或命令提示符中运行：

```powershell
cd C:\Users\liuhu\Desktop\AI\codex\projects\bond-yield-curve
python -m http.server 8000 --bind 127.0.0.1
```

保持终端窗口打开，在浏览器访问：

[本地首页](http://127.0.0.1:8000/index.html)

按 `Ctrl+C` 停止服务器。也可以双击根目录的 `preview.bat` 启动并打开浏览器。Python 需已安装并加入 PATH；仅浏览现有数据无需安装 `requests`。如果提示端口占用，先停止此前启动的服务器。

`--bind 127.0.0.1` 让服务只监听本机。页面使用 `fetch` 读取数据，请通过本地服务器打开首页。

## 文件位置

```text
bond-yield-curve/
├─ index.html            正式首页
├─ README.md             本说明
├─ preview.bat           双击启动本地预览
├─ ci_update.py          抓取数据、生成派生结果的脚本
├─ requirements.txt      更新脚本依赖
├─ data/                 收益率、折现、汇总、实际值和预测 JSON
├─ assets/               图表库、Excel 导出库及离线快照脚本
├─ docs/                 计算公式、机构观点、触发分析、方法说明
│  └─ 原项目说明.md      原始技术说明，保留历史内容
├─ archive/
│  └─ index.original.html 原重复首页快照，仅作备份
├─ tests/                原有自动化测试
└─ .github/workflows/    Pages 部署及手动更新工作流
```

原项目说明和首页快照保留了整理前的路径，供追溯参考；日常使用根目录的 `index.html`。页面、更新脚本、测试和工作流中的实际文件引用已同步到新位置。Python 缓存已清理，`.gitignore` 会忽略后续生成的缓存和本地虚拟环境。

## 查看现有数据与更新数据

首页的收益率图表、折现/溢价计算和预定利率研究值读取 `data/` 内的现有数据，主要图表库与 Excel 导出库存放在 `assets/`，可断网查看和计算。关闭页面不会更新数据；数据日期以页面展示为准。

`docs/trigger_analysis_report.html` 的独立报告仍从 CDN 加载 Chart.js，首次离线打开时图表可能无法显示。外部资料链接、抓取最新市场数据需要联网。

如需主动更新，在项目根目录运行：

```powershell
python -m pip install -r requirements.txt
python ci_update.py
```

脚本依赖 `requests`，直接请求中债收益率接口及外部预定利率模型数据；当前脚本不依赖 `akshare`。执行会改写本地数据文件，是否抓取成功取决于数据源可用性。

只想用现有收益率数据重算派生结果时：

```powershell
python ci_update.py --derived-only
```

此模式跳过市场数据抓取，仍会改写派生文件。`data/actuals.json` 中的历史实际研究值需人工维护；脚本内的 LPR、存款利率表也需随公告核对，不能认为所有指标都会自动获取最新值。

## 移动平均分析

两个移动平均图位于“基础评估曲线”，分别设置“曲线1、曲线2…”，各自默认两条曲线，点击各自的“＋ 添加曲线”可继续增加。时间序列每条曲线独立选择债券、MA 和期限；期限曲线每条曲线独立选择债券、MA 和日期。支持国债、国开债、铁道债、AAA/AA/A 企业债、进出口行债、农发行债及地方政府债。

本区固定读取 `data/` 中各债券的即期收益率数据，不使用寿险模块预先计算的 MA750，也不受上方其他图表的收益率口径选择影响。MA1 为当日即期收益率；MAx 为截至该日最近 x 条原始记录的算术平均，包含当日。自定义支持任意大于等于 1 的整数。

必须具备完整窗口，否则提示“数据不足 x 条”；日期、期限或窗口内数据缺失时留空，不填充、不外推。地方政府债的即期数据由原来源脚本根据到期收益率推导，界面与导出说明会标注来源。

左图的“表格截至日期”只控制左图及其最近10个日期的表格，不影响右图。右图分别展示每条曲线所选日期的期限结构；图例和表头标明各条曲线的期限或日期。差值为各自所选债券、MA、期限或日期下的曲线N−曲线1。

右图导出范围选择“各曲线所选日期”时，按每条曲线自己的日期输出，日期在列名中注明；选择全量或自定义区间时，各条曲线均按导出日期逐日计算。导出全部已设置曲线的 MA、相对曲线1的差值及缺失原因，使用完整历史计算各日期的 MA。

计算验证可运行 `node tests/test_ma_analysis.js`，无需安装 Node 包。

## 仓库及自动化

公开仓库：[ConnieLH/bond-yield-curve](https://github.com/ConnieLH/bond-yield-curve)。本地 `origin` 指向该仓库，`upstream` 保留原来源，用于以后同步。

在线页面：[债券收益率曲线](https://connielh.github.io/bond-yield-curve/)。`deploy-pages.yml` 在推送到 `main` 后验证前端并发布现有静态文件，不抓取数据。原 `update-data.yml` 已移除定时及推送触发，并在 GitHub 中保持禁用；如需恢复抓数，先检查数据来源和该工作流的提交、部署步骤。

复制时未发现 `LICENSE` 文件；本说明不替原项目授予复制或再发布许可。
