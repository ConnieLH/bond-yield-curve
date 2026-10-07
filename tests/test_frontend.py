from pathlib import Path
import unittest


INDEX = Path("index.html")
METHODOLOGY = Path("docs/methodology.html")


class FrontendTests(unittest.TestCase):
    def test_life_discount_json_uses_cacheable_static_request(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("fetch('data/life_discount.json', { cache: 'no-cache' })", text)
        self.assertNotIn("life_discount.json?' + Date.now()", text)

    def test_life_discount_premium_controls_include_terminal_spread_and_premium_curve(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="lifeBenchmarkSelect"', text)
        self.assertIn('id="lifeSpreadBondSelect"', text)
        self.assertIn('id="lifeFrontPremiumSelect"', text)
        self.assertIn('id="lifeLongPremiumSelect"', text)
        self.assertIn('<option value="yearly" selected>前20年逐年差额</option>', text)
        self.assertIn('<option value="10y">第10年溢价</option>', text)
        self.assertIn('<option value="20y">第20年溢价</option>', text)
        self.assertIn('<option value="avg_1_20">前20年平均溢价</option>', text)
        self.assertIn('<option value="40y">40年标的溢价</option>', text)
        self.assertIn('<option value="50y" selected>50年标的溢价</option>', text)
        self.assertIn('<option value="avg_40_50">40-50年平均</option>', text)
        self.assertIn('id="lifeCompareChart"', text)
        self.assertIn('id="lifeDiffBody"', text)
        self.assertNotIn('id="lifeCurveTypeSelect"', text)
        self.assertNotIn("lifeCurveType", text)
        self.assertIn("lifeFrontPremiumMode = this.value", text)
        self.assertIn("function lifeFrontPremiumModeName()", text)
        self.assertIn("function lifeFrontPremiumValue", text)

    def test_base_section_defaults_to_government_spot_detail(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("async function showBaseSection(type)", text)
        self.assertIn("showBaseSection('gov_spot')", text)
        self.assertIn("else showBaseSection();", text)

    def test_section_toggle_is_parallel_with_title_and_bond_selects_are_below_title(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('class="header-actions"', text)
        self.assertIn('<div class="header-actions">', text)
        self.assertIn('<div class="bond-selector" id="bondSelector">', text)
        self.assertIn('id="bondCurveSelect"', text)
        self.assertIn('id="bondRateTypeSelect"', text)
        self.assertIn(".bond-selector { grid-column: 1; grid-row: 2;", text)
        self.assertNotIn('<button class="active" data-bond="gov_spot"', text)

    def test_overview_does_not_flash_before_default_base_detail(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('<div class="view-overview" id="viewOverview" style="display:none;">', text)

    def test_base_summary_is_above_all_detail_charts(self):
        text = INDEX.read_text(encoding="utf-8")
        summary_index = text.index('id="bondSummaryCard"')
        first_grid_index = text.index('<div class="grid-2">')
        chart_index = text.index('id="curveChart"')
        self.assertLess(summary_index, first_grid_index)
        self.assertLess(summary_index, chart_index)

    def test_overview_back_button_is_hidden_from_base_detail(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn(".btn-back { display: none;", text)

    def test_tooltips_show_on_mouse_move_not_click(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("triggerOn: 'mousemove|click'", text)
        self.assertNotIn("triggerOn: 'click'", text)

    def test_preset_section_uses_reference_layout(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="viewPreset"', text)
        self.assertIn('id="cardLatestValue"', text)
        self.assertIn('id="cardMaxRate"', text)
        self.assertIn('id="cardGap"', text)
        self.assertIn('id="cardNextPred"', text)
        self.assertIn("最新公布研究值", text)
        self.assertIn("预定利率最高值", text)
        self.assertIn("最高值 - 研究值", text)
        self.assertIn("下一期预测值", text)
        self.assertIn("未来4季度预测详情", text)
        self.assertIn('id="presetMainChart"', text)
        self.assertIn('id="presetDataTable"', text)
        self.assertIn('id="presetPredTable"', text)
        self.assertIn('id="triggerStatusBox"', text)
        self.assertIn('id="gapBarFill"', text)
        self.assertIn('id="predTriggerText"', text)
        self.assertIn('id="presetTimeline"', text)
        self.assertIn('id="presetTriggerHistory"', text)
        self.assertIn("下调触发", text)
        self.assertIn("上调触发", text)
        self.assertIn("紧急调整", text)
        self.assertIn("历史触发记录", text)
        self.assertIn("function loadPresetData(", text)
        self.assertIn("function renderPresetChart(", text)
        self.assertIn("function switchPresetTab(", text)
        self.assertIn("function updatePresetTimeline(", text)
        self.assertIn("function updatePresetTriggerStatus(", text)
        self.assertIn("data/actuals.json", text)
        self.assertIn("data/predictions.json", text)
        self.assertIn("function loadOfflineSnapshot(", text)
        self.assertIn("PRESET_TRIGGER_THRESHOLD", text)
        self.assertIn("prediction_views.html", text)
        self.assertIn("formula_report.html", text)
        self.assertIn("trigger_analysis_report.html", text)

    def test_preset_reports_are_local_and_linked(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('href="docs/formula_report.html"', text)
        self.assertIn('href="docs/trigger_analysis_report.html"', text)
        self.assertIn('href="docs/prediction_views.html"', text)
        for name in ("formula_report.html", "trigger_analysis_report.html", "prediction_views.html"):
            self.assertTrue((Path("docs") / name).exists(), f"missing report file: {name}")
        self.assertTrue(METHODOLOGY.exists())



    def test_base_section_is_driven_by_selected_rate_basis(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="baseRateBasisSelect"', text)
        self.assertIn('<option value="spot" selected>即期</option>', text)
        self.assertIn('<option value="ma750">750日平均</option>', text)
        self.assertIn('<option value="ma20">20日平均</option>', text)
        self.assertIn('<option value="ma30">30日平均</option>', text)
        self.assertIn('<option value="ma60">60日平均</option>', text)
        self.assertIn("let baseRateBasis = 'spot';", text)
        self.assertIn("function getRatesForBasis", text)
        self.assertIn("function basisLabel()", text)
        self.assertIn("上年度末", text)
        self.assertIn("上季度末", text)
        self.assertIn("上月末", text)
        self.assertIn("上日", text)
        self.assertNotIn("10年750MA", text)

    def test_base_key_terms_and_curve_use_current_basis_only(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="historyDiffFromSelect"', text)
        self.assertIn('id="historyDiffToSelect"', text)
        self.assertIn('id="historyDiffHeader"', text)
        self.assertIn('id="historyDiffBody"', text)
        self.assertIn("populateCurveDateSelector", text)
        self.assertIn("getCurveSelectableDates", text)
        self.assertIn("renderHistoryDiffTable", text)
        self.assertIn("关键期限利率", text)
        self.assertIn("所选口径", text)
        self.assertNotIn("<th>750MA (%)</th>", text)
        self.assertNotIn("<th>750-上月 (bp)</th>", text)
        self.assertNotIn("<th>日期A (%)</th>", text)
        self.assertNotIn("<th>日期B (%)</th>", text)
        history_index = text.index('id="historyDiffBody"')
        forecast_index = text.index('id="forecastChart"')
        self.assertLess(history_index, forecast_index)

    def test_base_key_terms_support_custom_average_split_year(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="baseAverageSplitInput"', text)
        self.assertIn("let baseAverageSplitYear = 3;", text)
        self.assertIn("function baseAverageKeys()", text)
        self.assertIn("baseAverageSplitYear + 1", text)
        self.assertIn("renderKeyTermsTable();", text)

    def test_premium_section_is_premium_only_and_renamed(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("基础曲线", text)
        self.assertIn("对比曲线", text)
        self.assertIn('id="lifeCompareChart"', text)
        self.assertNotIn('id="lifeDiffFromSelect"', text)
        self.assertNotIn('id="lifeDiffToSelect"', text)
        self.assertIn('id="lifeDiffHeader"', text)
        self.assertIn('id="lifeDiffBody"', text)
        self.assertIn("renderLifeCompareChart", text)
        self.assertIn("renderLifeDiffTable", text)
        self.assertNotIn('id="lifeCurveTypeSelect"', text)
        self.assertNotIn("lifeCurveType", text)
        self.assertIn('id="legacyDiscountMetricSelect"', text)
        self.assertIn('id="newDiscountMetricSelect"', text)
        self.assertIn("即期折现率", text)
        self.assertIn("远期折现率", text)
        self.assertNotIn('id="lifeDownloadBtn"', text)

    def test_premium_section_has_monitor_and_discount_generation_panels(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="premiumMonitorToggle"', text)
        self.assertIn('id="premiumMonitorContent"', text)
        self.assertIn('id="premiumDiscountToggle"', text)
        self.assertIn('id="premiumDiscountContent"', text)
        self.assertIn("function togglePremiumSection", text)
        self.assertIn("premium-section.collapsed .premium-section-body", text)

    def test_premium_monitor_cards_follow_excel_requirement(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="premiumLiquidityCard"', text)
        self.assertIn('id="premiumCounterCycleCard"', text)
        self.assertIn('id="premiumLongSpreadCard"', text)
        self.assertIn('id="premiumLiquidityBody"', text)
        self.assertIn('id="premiumCounterCycleBody"', text)
        self.assertIn('id="premiumLongSpreadBody"', text)
        self.assertIn("PREMIUM_COUNTER_DEFAULT_TERMS", text)
        self.assertNotIn("PREMIUM_EXCEL_DEFAULTS", text)
        self.assertIn("function renderPremiumMonitor", text)
        self.assertIn("function defaultPremiumDates", text)
        self.assertIn("function projectLatestPremiumRow", text)

    def test_premium_monitor_uses_live_values_without_excel_number_fallbacks(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertNotIn("function premiumLiquidityFallbackValue", text)
        self.assertNotIn("PREMIUM_EXCEL_DEFAULTS.counterCycle.fallback", text)
        self.assertNotIn("PREMIUM_EXCEL_DEFAULTS.longSpread.fallback", text)
        self.assertIn("fmtBpValue(computed)", text)

    def test_premium_monitor_prefers_raw_curve_data_over_precomputed_rows(self):
        text = INDEX.read_text(encoding="utf-8")
        start = text.index("function monitorRate(period, key, date, term)")
        end = text.index("function monitorSpreadBp", start)
        body = text[start:end]
        self.assertIn("premiumSourceDataCache[key]", body)
        self.assertIn("monitorRateFromSourceData(period, key, date, term)", body)
        self.assertLess(
            body.index("monitorRateFromSourceData(period, key, date, term)"),
            body.index("monitorRowsFor(period, key)"),
        )

    def test_long_spread_monitor_matches_excel_grouped_structure_and_formula(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("function premiumLongSpreadBp(period, date, baseTerm)", text)
        self.assertIn("monitorRate(period, 'gov_spot', date, '40Y')", text)
        self.assertIn("monitorRate(period, 'gov_spot', date, '50Y')", text)
        self.assertIn("monitorRate(period, 'gov_spot', date, baseTerm)", text)
        self.assertIn("2500日移动平均（旧准则）", text)
        self.assertIn("750日移动平均（新准则）", text)
        self.assertIn("平均利差（基于10年）", text)
        self.assertIn("平均利差（基于15年）", text)
        self.assertIn("平均利差（基于20年）", text)
        self.assertIn("premiumLongSpreadBp(group.period, baseDate, item.term)", text)
        self.assertNotIn("40-50Y平均口径", text)

    def test_premium_monitor_observation_dates_are_selectable_and_liquidity_shows_all_curves(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("其他观察时点1", text)
        self.assertIn("其他观察时点2", text)
        self.assertIn("其他观察时点3", text)
        self.assertIn("[evalYear - 3, evalYear - 2, evalYear - 1].map", text)
        self.assertIn("roleLabel: '其他观察时点'", text)
        self.assertIn("<th rowspan=\"2\">类型</th><th rowspan=\"2\">日期</th>", text)
        self.assertIn('id="premiumLiquidityObservationDate1"', text)
        self.assertIn('id="premiumCounterObservationDate1"', text)
        self.assertIn('id="premiumLongObservationDate1"', text)
        self.assertNotIn('id="premiumLiquidityCurve"', text)
        self.assertNotIn('id="premiumLiquidityPeriod"', text)
        self.assertIn('id="premiumLiquidityRailPeriod"', text)
        self.assertIn('id="premiumLiquidityCorpPeriod"', text)
        self.assertIn('id="premiumLiquidityCdbPeriod"', text)
        self.assertIn("PREMIUM_LIQUIDITY_PERIOD_CONTROL_IDS", text)
        self.assertIn("function premiumLiquidityPeriodForCurve", text)
        self.assertIn("premiumLiquidityPeriodForCurve(curve.key)", text)
        self.assertIn("lifeDiscountData.benchmarkRows?.[key]", text)
        self.assertIn("function ensurePremiumMonitorSourceData", text)
        self.assertIn("premiumSourceMA", text)
        self.assertIn("monitorRateFromSourceData", text)
        self.assertIn("ensurePremiumMonitorSourceData().then(renderPremiumMonitor)", text)
        self.assertIn("PREMIUM_LIQUIDITY_CURVES", text)
        self.assertIn("for (const curve of PREMIUM_LIQUIDITY_CURVES)", text)
        self.assertIn("铁道债-国债（旧准则）", text)
        self.assertIn("AAA企业债-国债（旧准则）", text)
        self.assertIn("国开债-国债（新准则）", text)

    def test_all_premium_evaluation_defaults_use_prior_month_end(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("function previousMonthEndOnOrBefore", text)
        self.assertIn("function defaultLifeEvaluationDate", text)
        self.assertIn("previousMonthEndOnOrBefore(currentIsoDate())", text)
        self.assertIn("lifeSelectedDate = defaultLifeEvaluationDate();", text)
        self.assertIn("const evalDate = defaultLifeEvaluationDate(evalDateOverride);", text)

    def test_discount_generation_default_compare_date_is_prior_year_end(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("function defaultDiscountCompareDate", text)
        self.assertIn("lastYearTrade || evalDate", text)

    def test_discount_generation_uses_separate_legacy_and_new_cards(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="legacyDiscountParamsCard"', text)
        self.assertIn('id="newDiscountParamsCard"', text)
        self.assertIn('id="legacyDiscountChartCard"', text)
        self.assertIn('id="newDiscountChartCard"', text)
        self.assertIn('id="legacyDiscountTableCard"', text)
        self.assertIn('id="newDiscountTableCard"', text)
        self.assertIn('id="legacyDiscountChart"', text)
        self.assertIn('id="newDiscountChart"', text)
        self.assertIn('id="legacyDiscountMetricSelect"', text)
        self.assertIn('id="newDiscountMetricSelect"', text)
        self.assertIn("function buildDiscountGenerationRows", text)
        self.assertIn("function buildRuleBaseCurve", text)
        self.assertIn("function downloadDiscountGenerationExcel", text)

    def test_premium_counter_cycle_terms_are_selectable(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="premiumCounterStartTerm"', text)
        self.assertIn('id="premiumCounterEndTerm"', text)
        self.assertIn("function premiumCounterTerms", text)
        self.assertIn("premiumCounterStartTerm", text)
        self.assertIn("premiumCounterEndTerm", text)
        self.assertIn("function counterCycleBp", text)

    def test_counter_cycle_uses_2500_and_750_day_moving_averages(self):
        text = INDEX.read_text(encoding="utf-8")
        start = text.index("function counterCycleBp")
        end = text.index("function premiumLongSpreadBp", start)
        body = text[start:end]
        self.assertIn("monitorRate(2500, 'gov_spot'", body)
        self.assertIn("monitorRate(750, 'gov_spot'", body)
        self.assertNotIn("monitorRate(250, 'gov_spot'", body)
        self.assertIn("国债2500日移动平均 - 国债750日移动平均", text)
        self.assertNotIn("国债2500日移动平均 - 国债250日移动平均", text)

    def test_discount_generation_eval_and_compare_premiums_are_separate(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("evalFrontPremiumBp", text)
        self.assertIn("evalLongPremiumBp", text)
        self.assertIn("compareFrontPremiumBp", text)
        self.assertIn("compareLongPremiumBp", text)
        self.assertIn("evalPremium = buildDiscountPremiumRow(state.evalFrontPremiumBp, state.evalLongPremiumBp)", text)
        self.assertIn("comparePremium = buildDiscountPremiumRow(state.compareFrontPremiumBp, state.compareLongPremiumBp)", text)
        self.assertIn("DiscountEvalFrontPremium", text)
        self.assertIn("DiscountCompareFrontPremium", text)
        self.assertIn("DiscountEvalLongPremium", text)
        self.assertIn("DiscountCompareLongPremium", text)

    def test_discount_generation_parameters_keep_each_date_group_on_one_row(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('class="discount-param-row" data-point="eval"', text)
        self.assertIn('class="discount-param-row" data-point="compare"', text)
        self.assertIn("评估时点前20年溢价（bp）", text)
        self.assertIn("评估时点40年后溢价（bp）", text)
        self.assertIn("对比时点前20年溢价（bp）", text)
        self.assertIn("对比时点40年后溢价（bp）", text)
        self.assertIn(".discount-param-row { display: grid;", text)

    def test_discount_generation_table_matches_excel_three_block_layout(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("function renderDiscountGenerationTable", text)
        self.assertIn("const DISCOUNT_GENERATION_COLUMNS", text)
        self.assertIn("row.header", text)
        self.assertIn("discount-block-label", text)
        self.assertIn("<th>关键期限</th>", text)
        self.assertIn("评估时点曲线", text)
        self.assertIn("对比时点曲线", text)
        self.assertIn("差异（评估-对比）单位bps", text)
        self.assertIn("基础曲线", text)
        self.assertIn("综合溢价", text)
        self.assertIn("即期折现率", text)
        self.assertIn("远期折现率", text)
        self.assertNotIn("<th>分块</th><th>曲线</th>", text)
        self.assertNotIn("<td></td><td><strong>", text)

    def test_ma_cards_are_available_under_base_with_shared_settings(self):
        text = INDEX.read_text(encoding="utf-8")
        base = text[text.index('id="viewDetail"'):text.index('id="viewPremium"')]
        premium = text[text.index('id="viewPremium"'):text.index('id="viewPreset"')]
        for element in ("maAnalysis", "maCurveSettings", "maTimeSeriesChart", "maCurveChart", "maTimeSeriesBody", "maCurveBody"):
            self.assertIn(f'id="{element}"', base)
            self.assertNotIn(f'id="{element}"', premium)
        self.assertEqual(text.count('id="maCurveSettings"'), 1)

    def test_comparison_spacing_and_diff_cells_are_consistent(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="historyComparisonCard"', text)
        self.assertIn('class="card section-card"', text)
        self.assertIn(".section-card { margin-bottom: 20px;", text)
        self.assertIn("function formatDiffCell", text)
        self.assertGreaterEqual(text.count("formatDiffCell("), 5)
        self.assertIn("diff-col positive", text)
        self.assertIn("diff-col negative", text)

    def test_ma_cards_keep_real_coverage_and_responsive_layout(self):
        text = INDEX.read_text(encoding="utf-8")
        css = Path("assets/ma-analysis.css").read_text(encoding="utf-8")
        self.assertIn('class="ma-analysis-grid"', text)
        self.assertEqual(text.count('class="card ma-analysis-card"'), 2)
        self.assertIn("repeat(2, minmax(0, 1fr))", css)
        self.assertIn("@media (max-width: 1024px)", css)
        self.assertIn("overflow: auto", css)
        self.assertNotIn("function lifeFullCompareValueAt", text)
        self.assertIn("期限缺失时留空", text)

    def test_ma_settings_use_raw_spot_sources_and_support_additional_curves(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="maAddCurve"', text)
        self.assertIn("YieldMA.createView", text)
        self.assertIn("fetch(bond.file, { cache: 'no-cache' })", text)
        for key in ("gov_spot", "cdb_spot", "rail_spot", "corp_aaa_spot", "corp_aa_spot", "corp_a_spot", "exim_spot", "adbc_spot", "local_gov_spot"):
            self.assertIn(key, text[text.index("function initMAAnalysis()"):text.index("let deferredDetailRenderId")])
        self.assertNotIn('id="maCurveGroupA"', text)
        self.assertNotIn('id="maCurveGroupB"', text)
        self.assertTrue(Path("assets/ma-analysis.js").is_file())

    def test_ma_notes_and_export_range_explain_the_actual_scope(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="maDateSelect"', text)
        self.assertNotIn('id="maTimeSeriesEndDateSelect"', text)
        self.assertIn("截至所选日期最近10个日期", text)
        self.assertIn("MA1 = 当日即期收益率", text)
        self.assertIn("最近 x 条原始即期收益率记录", text)
        self.assertIn('<label for="maCurveExportRange">导出范围</label>', text)
        self.assertIn('id="maCurveStatus"', text)
        self.assertIn('id="maExportStatus"', text)
        self.assertIn("导出全部已设置曲线", text)

    def test_frontend_makeup_weekends_match_the_backend_calendar(self):
        text = INDEX.read_text(encoding="utf-8")
        start = text.index("const TRADE_WEEKENDS = new Set")
        end = text.index("]);", start)
        block = text[start:end]
        for day in [
            "2013-01-05",
            "2016-02-06",
            "2017-01-22",
            "2025-10-11",
            "2026-01-04",
            "2026-10-10",
        ]:
            self.assertIn(day, block)
        for wrong_day in ["2016-01-30", "2017-01-21", "2020-02-01"]:
            self.assertNotIn(wrong_day, block)


if __name__ == "__main__":
    unittest.main()
