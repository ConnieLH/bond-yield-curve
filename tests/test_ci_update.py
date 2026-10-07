import unittest
from unittest.mock import patch

import ci_update


class CurveConfigTests(unittest.TestCase):
    def test_builds_all_nine_curves_and_eighteen_datasets(self):
        curve_keys = [curve.key for curve in ci_update.CURVES]
        self.assertEqual(
            curve_keys,
            [
                "gov",
                "cdb",
                "rail",
                "corp_aaa",
                "exim",
                "adbc",
                "local_gov",
                "corp_aa",
                "corp_a",
            ],
        )

        dataset_keys = [dataset.key for dataset in ci_update.ALL_DATASETS]
        self.assertEqual(len(dataset_keys), 18)
        self.assertEqual(len(set(dataset_keys)), 18)
        self.assertIn("gov_spot", dataset_keys)
        self.assertIn("local_gov_spot", dataset_keys)
        self.assertIn("corp_a_ytm", dataset_keys)

    def test_legacy_files_are_preserved_for_existing_four_datasets(self):
        files = {dataset.key: dataset.filename for dataset in ci_update.ALL_DATASETS}
        self.assertEqual(files["gov_spot"], "data/data.json")
        self.assertEqual(files["cdb_spot"], "data/data_cdb.json")
        self.assertEqual(files["gov_ytm"], "data/data_gov_ytm.json")
        self.assertEqual(files["cdb_ytm"], "data/data_cdb_ytm.json")
        self.assertEqual(files["rail_spot"], "data/data_rail_spot.json")


class BootstrapTests(unittest.TestCase):
    def test_bootstraps_local_government_spot_from_ytm_curve(self):
        ytm = {"1Y": 2.0, "2Y": 3.0, "3Y": 4.0}

        spot = ci_update.bootstrap_spot_from_ytm(ytm)

        self.assertAlmostEqual(spot["1Y"], 2.0, places=8)
        self.assertGreater(spot["2Y"], ytm["2Y"])
        self.assertGreater(spot["3Y"], ytm["3Y"])
        self.assertEqual(sorted(spot.keys()), ["1Y", "2Y", "3Y"])


class LifeDiscountTests(unittest.TestCase):
    def test_life_base_curve_uses_ultimate_rate_transition(self):
        ma_rates = {f"{year}Y": 2.0 for year in range(1, 51)}

        base = ci_update.build_life_base_curve(ma_rates)

        self.assertAlmostEqual(base["20Y"], 2.0, places=8)
        self.assertAlmostEqual(base["30Y"], 2.625, places=8)
        self.assertAlmostEqual(base["40Y"], 4.5, places=8)
        self.assertAlmostEqual(base["50Y"], 4.5, places=8)

    def test_accounting_premium_curve_uses_front_spread_long_spread_and_interpolation(self):
        benchmark = {f"{year}Y": 2.0 for year in range(1, 51)}
        benchmark["50Y"] = 3.2
        spread_bond = {f"{year}Y": 2.4 for year in range(1, 21)}
        spread_bond["20Y"] = 2.8

        premium = ci_update.build_accounting_premium_curve(benchmark, spread_bond)

        self.assertAlmostEqual(premium["10Y"], 0.4, places=8)
        self.assertAlmostEqual(premium["20Y"], 0.8, places=8)
        self.assertAlmostEqual(premium["30Y"], 1.0, places=8)
        self.assertAlmostEqual(premium["40Y"], 1.2, places=8)
        self.assertAlmostEqual(premium["50Y"], 1.2, places=8)

    def test_accounting_premium_curve_supports_selectable_terminal_spread_modes(self):
        benchmark = {f"{year}Y": 2.0 for year in range(1, 51)}
        benchmark["40Y"] = 2.6
        benchmark["50Y"] = 3.2
        for year in range(41, 50):
            benchmark[f"{year}Y"] = 2.6 + (3.2 - 2.6) * (year - 40) / 10
        spread_bond = {f"{year}Y": 2.4 for year in range(1, 21)}
        spread_bond["20Y"] = 2.8

        premium40 = ci_update.build_accounting_premium_curve(benchmark, spread_bond, "40y")
        premium50 = ci_update.build_accounting_premium_curve(benchmark, spread_bond, "50y")
        premium_avg = ci_update.build_accounting_premium_curve(benchmark, spread_bond, "avg_40_50")

        self.assertAlmostEqual(premium40["40Y"], 0.6, places=8)
        self.assertAlmostEqual(premium40["30Y"], 0.7, places=8)
        self.assertAlmostEqual(premium50["40Y"], 1.2, places=8)
        self.assertAlmostEqual(premium50["30Y"], 1.0, places=8)
        self.assertAlmostEqual(premium_avg["40Y"], 0.9, places=8)
        self.assertAlmostEqual(premium_avg["30Y"], 0.85, places=8)

    def test_life_discount_spot_adds_accounting_premium_curve(self):
        base = {f"{year}Y": 2.0 for year in range(1, 51)}
        premium = {f"{year}Y": 0.25 for year in range(1, 51)}

        spot = ci_update.build_life_discount_spot_curve(base, premium)

        self.assertAlmostEqual(spot["10Y"], 2.25, places=8)
        self.assertAlmostEqual(spot["30Y"], 2.25, places=8)
        self.assertAlmostEqual(spot["40Y"], 2.25, places=8)

    def test_forward_rates_are_derived_from_spot_discount_rates(self):
        spot = {"1Y": 2.0, "2Y": 3.0, "3Y": 4.0}

        forward = ci_update.build_forward_curve(spot)

        expected_2y = (((1.03 ** 2) / 1.02) - 1.0) * 100.0
        self.assertAlmostEqual(forward["1Y"], 2.0, places=8)
        self.assertAlmostEqual(forward["2Y"], expected_2y, places=8)

    def test_life_discount_data_keeps_benchmark_and_spread_rows_for_accounting_rule(self):
        terms = [f"{year}Y" for year in range(1, 51)]
        spread_terms = [f"{year}Y" for year in range(1, 21)]
        gov_rows = [[2.0 for _ in terms] for _ in range(750)]
        cdb_rows = [[2.2 for _ in terms] for _ in range(750)]
        rail_rows = [[2.5 for _ in spread_terms] for _ in range(750)]
        dates = [f"2024-01-{(i % 28) + 1:02d}" for i in range(750)]
        dates[-1] = "2026-07-15"
        benchmark_data = {
            "gov_spot": {"dates": dates, "terms": terms, "rows": gov_rows},
            "cdb_spot": {"dates": dates, "terms": terms, "rows": cdb_rows},
        }
        spread_bond_data = {
            "rail_spot": {"dates": dates, "terms": spread_terms, "rows": rail_rows},
        }

        output = ci_update.build_life_discount_data(benchmark_data, spread_bond_data)

        self.assertEqual(output["dates"], ["2026-07-15"])
        self.assertEqual(output["terms"], terms)
        self.assertEqual(output["spreadTerms"], spread_terms)
        self.assertEqual([item["key"] for item in output["benchmarks"]], ["gov_spot", "cdb_spot"])
        self.assertEqual([item["key"] for item in output["spreadBonds"]], ["rail_spot"])
        self.assertNotIn("curves", output)
        self.assertAlmostEqual(output["baseRows"]["gov_spot"][0][19], 2.0, places=8)
        self.assertAlmostEqual(output["baseRows"]["gov_spot"][0][39], 4.5, places=8)
        self.assertAlmostEqual(output["benchmarkRows"]["cdb_spot"][0][0], 2.2, places=8)
        self.assertAlmostEqual(output["spreadBondRows"]["rail_spot"][0][0], 2.5, places=8)

    def test_life_discount_data_schema_is_compact(self):
        terms = [f"{year}Y" for year in range(1, 51)]
        spread_terms = [f"{year}Y" for year in range(1, 21)]
        rows = [[2.0 for _ in terms] for _ in range(750)]
        spread_rows = [[2.4 for _ in spread_terms] for _ in range(750)]
        dates = [f"2024-01-{(i % 28) + 1:02d}" for i in range(750)]

        output = ci_update.build_life_discount_data(
            {
                "gov_spot": {"dates": dates, "terms": terms, "rows": rows},
                "cdb_spot": {"dates": dates, "terms": terms, "rows": rows},
            },
            {"rail_spot": {"dates": dates, "terms": spread_terms, "rows": spread_rows}},
        )

        self.assertEqual(output["meta"]["schemaVersion"], 3)
        self.assertEqual(
            set(output.keys()),
            {"meta", "dates", "terms", "spreadTerms", "benchmarks", "spreadBonds", "baseRows", "benchmarkRows", "spreadBondRows", "monitorRows"},
        )

    def test_premium_monitor_datasets_use_extended_history_start(self):
        starts = {dataset.key: ci_update.dataset_history_start(dataset) for dataset in ci_update.ALL_DATASETS}

        self.assertEqual(starts["gov_spot"], ci_update.PREMIUM_HISTORY_START_DATE)
        self.assertEqual(starts["cdb_spot"], ci_update.PREMIUM_HISTORY_START_DATE)
        self.assertEqual(starts["rail_spot"], ci_update.PREMIUM_HISTORY_START_DATE)
        self.assertEqual(starts["corp_aaa_spot"], ci_update.PREMIUM_HISTORY_START_DATE)
        self.assertEqual(starts["gov_ytm"], ci_update.START_DATE)
        self.assertEqual(starts["corp_aa_spot"], ci_update.START_DATE)

    def test_premium_monitor_history_start_covers_2023_year_end_2500ma(self):
        self.assertLessEqual(ci_update.PREMIUM_HISTORY_START_DATE, "2013-01-01")

    def test_existing_monitor_dataset_backfills_when_history_is_short(self):
        dataset = ci_update.DATASET_BY_KEY["gov_spot"]
        existing = {
            "dates": ["2020-01-02", "2026-07-15"],
            "terms": dataset.terms,
            "rows": [[2.0 for _ in dataset.terms], [2.1 for _ in dataset.terms]],
            "meta": dataset.meta,
        }

        fetch_start = ci_update.next_fetch_date_for_dataset(dataset, existing)

        self.assertEqual(fetch_start, ci_update.PREMIUM_HISTORY_START_DATE)

    def test_existing_monitor_dataset_keeps_incremental_update_after_history_backfill(self):
        dataset = ci_update.DATASET_BY_KEY["gov_spot"]
        existing = {
            "dates": [ci_update.PREMIUM_HISTORY_START_DATE, "2026-07-15"],
            "terms": dataset.terms,
            "rows": [[2.0 for _ in dataset.terms], [2.1 for _ in dataset.terms]],
            "meta": dataset.meta,
        }

        fetch_start = ci_update.next_fetch_date_for_dataset(dataset, existing)

        self.assertEqual(fetch_start, "2026-07-16")

    def test_strict_moving_average_requires_full_period_for_every_term(self):
        terms = ["1Y", "2Y"]
        short_data = {
            "dates": [f"2026-01-{day:02d}" for day in range(1, 6)],
            "terms": terms,
            "rows": [[1.0, 2.0] for _ in range(5)],
        }
        full_data = {
            "dates": [f"2026-01-{day:02d}" for day in range(1, 6)],
            "terms": terms,
            "rows": [[float(day), float(day + 10)] for day in range(1, 6)],
        }

        self.assertEqual(ci_update.moving_average_rows(short_data, 6, terms), [])
        rows = ci_update.moving_average_rows(full_data, 5, terms)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "2026-01-05")
        self.assertAlmostEqual(rows[0][1]["1Y"], 3.0, places=8)
        self.assertAlmostEqual(rows[0][1]["2Y"], 13.0, places=8)

    def test_append_dataset_day_merges_backfilled_dates_in_order(self):
        dataset = ci_update.DATASET_BY_KEY["gov_spot"]
        states = {
            dataset.key: {
                "dates": ["2020-01-02"],
                "terms": dataset.terms,
                "rows": [[2.0 for _ in dataset.terms]],
            }
        }

        ci_update.append_dataset_day(states, dataset, "2014-01-02", {"1Y": 1.0})
        ci_update.sort_dataset_state(states[dataset.key])

        self.assertEqual(states[dataset.key]["dates"], ["2014-01-02", "2020-01-02"])
        self.assertEqual(states[dataset.key]["rows"][0][0], 1.0)

    def test_life_discount_data_includes_monitor_ma_rows_for_required_periods(self):
        terms = [f"{year}Y" for year in range(1, 51)]
        dates = [f"2020-01-{(i % 28) + 1:02d}" for i in range(2500)]
        dates[-1] = "2026-07-15"
        rows = [[2.0 for _ in terms] for _ in dates]
        cdb_rows = [[2.2 for _ in terms] for _ in dates]
        rail_rows = [[2.5 for _ in terms] for _ in dates]
        aaa_rows = [[2.8 for _ in terms] for _ in dates]

        output = ci_update.build_life_discount_data(
            {
                "gov_spot": {"dates": dates, "terms": terms, "rows": rows},
                "cdb_spot": {"dates": dates, "terms": terms, "rows": cdb_rows},
            },
            {
                "rail_spot": {"dates": dates, "terms": terms, "rows": rail_rows},
                "corp_aaa_spot": {"dates": dates, "terms": terms, "rows": aaa_rows},
            },
        )

        self.assertIn("monitorRows", output)
        self.assertEqual(set(output["monitorRows"]), {"250", "750", "2500"})
        self.assertEqual(
            set(output["monitorRows"]["2500"]),
            {"gov_spot", "cdb_spot", "rail_spot", "corp_aaa_spot"},
        )
        self.assertEqual(output["monitorRows"]["2500"]["rail_spot"][-1][9], 2.5)


class PresetModelTests(unittest.TestCase):
    def test_parses_external_model_data_and_rewrites_global_name(self):
        source = (
            'window.MODEL_DATA = {"updatedAt":"2026-07-17T13:50:24+08:00",'
            '"series":[{"date":"2026-07-16","liabilityAnchor":2.4,'
            '"assetBaseReturn_mean":1.914127,"modelReferenceValue":1.914127}],'
            '"actualValues":[{"quarter":"2026Q2","asOfDate":"2026-03-31","value":1.93}],'
            '"warnings":[]};'
        )

        data = ci_update.parse_preset_model_js(source)
        script = ci_update.build_preset_model_script(data)

        self.assertEqual(data["updatedAt"], "2026-07-17T13:50:24+08:00")
        self.assertEqual(data["series"][0]["date"], "2026-07-16")
        self.assertTrue(script.startswith("window.PRESET_MODEL_DATA = "))
        self.assertIn('"modelReferenceValue":1.914127', script)
        self.assertNotIn("window.MODEL_DATA", script)

    def test_generate_preset_model_data_saves_valid_local_script(self):
        source = (
            'window.MODEL_DATA = {"updatedAt":"2026-07-17T13:50:24+08:00",'
            '"series":[{"date":"2026-07-16","liabilityAnchor":2.4,'
            '"assetBaseReturn_mean":1.914127,"modelReferenceValue":1.914127}],'
            '"actualValues":[],"warnings":[]};'
        )
        saved = {}

        with patch.object(ci_update, "fetch_preset_model_source", return_value=source), \
             patch.object(ci_update, "save_text", side_effect=lambda path, text: saved.update({path: text})):
            updated = ci_update.generate_preset_model_data()

        self.assertTrue(updated)
        self.assertIn(ci_update.PRESET_MODEL_FILE, saved)
        self.assertIn("window.PRESET_MODEL_DATA", saved[ci_update.PRESET_MODEL_FILE])


class MakeupTradingDayTests(unittest.TestCase):
    def setUp(self):
        self.dataset = next(d for d in ci_update.ALL_DATASETS if d.key == "gov_spot")

    def test_candidates_cover_historical_and_current_makeup_weekends(self):
        self.assertIn("2013-01-05", ci_update.MAKEUP_WORKDAY_CANDIDATES)
        self.assertIn("2025-10-11", ci_update.MAKEUP_WORKDAY_CANDIDATES)
        self.assertIn("2026-01-04", ci_update.MAKEUP_WORKDAY_CANDIDATES)
        self.assertIn("2026-10-10", ci_update.MAKEUP_WORKDAY_CANDIDATES)

    def test_existing_dataset_date_does_not_need_makeup_check(self):
        state = {"dates": ["2025-10-11"], "terms": self.dataset.terms, "rows": [[]]}

        needs_check = ci_update.makeup_dataset_needs_check(
            self.dataset, state, {}, "2025-10-11", "2026-07-31"
        )

        self.assertFalse(needs_check)

    def test_finalized_empty_audit_does_not_need_makeup_check(self):
        state = {"dates": [], "terms": self.dataset.terms, "rows": []}
        audit = {
            "schemaVersion": ci_update.MAKEUP_AUDIT_SCHEMA_VERSION,
            "datasets": {self.dataset.key: {"2025-10-11": "empty"}},
        }

        needs_check = ci_update.makeup_dataset_needs_check(
            self.dataset, state, audit, "2025-10-11", "2026-07-31"
        )

        self.assertFalse(needs_check)

    def test_missing_unverified_makeup_date_needs_check(self):
        state = {"dates": [], "terms": self.dataset.terms, "rows": []}

        needs_check = ci_update.makeup_dataset_needs_check(
            self.dataset, state, {}, "2025-10-11", "2026-07-31"
        )

        self.assertTrue(needs_check)


class UpdateTests(unittest.TestCase):
    def test_new_dataset_without_metadata_rebuilds_from_start_date(self):
        dataset = next(d for d in ci_update.ALL_DATASETS if d.key == "rail_ytm")
        old_wrong_data = {
            "dates": ["2026-07-15"],
            "terms": dataset.terms,
            "rows": [[1.224232] + [None] * (len(dataset.terms) - 1)],
        }

        fetch_start = ci_update.next_fetch_date_for_dataset(dataset, old_wrong_data)

        self.assertEqual(fetch_start, ci_update.START_DATE)

    def test_premium_monitor_legacy_dataset_without_metadata_backfills_history(self):
        dataset = next(d for d in ci_update.ALL_DATASETS if d.key == "gov_spot")
        legacy_data = {
            "dates": ["2026-07-15"],
            "terms": dataset.terms,
            "rows": [[1.0] + [None] * (len(dataset.terms) - 1)],
        }

        fetch_start = ci_update.next_fetch_date_for_dataset(dataset, legacy_data)

        self.assertEqual(fetch_start, ci_update.PREMIUM_HISTORY_START_DATE)

    def test_update_all_fetches_local_government_separately_from_bundles(self):
        datasets = [
            next(d for d in ci_update.ALL_DATASETS if d.key == "rail_ytm"),
            next(d for d in ci_update.ALL_DATASETS if d.key == "local_gov_ytm"),
        ]
        states = {
            dataset.filename: {"dates": [], "terms": dataset.terms, "rows": [], "meta": dataset.meta}
            for dataset in datasets
        }
        calls = []
        saved = {}

        def fake_load_existing(filepath, terms=None):
            return states[filepath]

        def fake_fetch_searchyc_bundle(curves, qxll, day):
            calls.append([curve.key for curve in curves])
            return {curve.key: {"1Y": 1.0} for curve in curves}

        with patch.object(ci_update, "ALL_DATASETS", datasets), \
             patch.object(ci_update, "load_existing", side_effect=fake_load_existing), \
             patch.object(ci_update, "save_json", side_effect=lambda path, data: saved.update({path: data})), \
             patch.object(ci_update, "iter_weekdays", return_value=["2026-07-15"]), \
             patch.object(ci_update, "MAKEUP_WORKDAY_CANDIDATES", set()), \
             patch.object(
                 ci_update,
                 "fetch_searchyc_bundle_result",
                 side_effect=lambda curves, qxll, day: (fake_fetch_searchyc_bundle(curves, qxll, day), True),
             ):
            changed = ci_update.update_all_datasets("2026-07-15")

        self.assertIn(["rail"], calls)
        self.assertIn(["local_gov"], calls)
        self.assertNotIn(["rail", "local_gov"], calls)
        self.assertTrue(changed["rail_ytm"])
        self.assertTrue(changed["local_gov_ytm"])

    def test_update_all_bootstraps_local_government_spot_from_isolated_ytm_request(self):
        dataset = next(d for d in ci_update.ALL_DATASETS if d.key == "local_gov_spot")
        states = {
            dataset.filename: {"dates": [], "terms": dataset.terms, "rows": [], "meta": dataset.meta}
        }
        calls = []
        saved = {}

        def fake_load_existing(filepath, terms=None):
            return states[filepath]

        def fake_fetch_searchyc_bundle(curves, qxll, day):
            calls.append(([curve.key for curve in curves], qxll))
            return {"local_gov": {"1Y": 2.0, "2Y": 3.0}}

        with patch.object(ci_update, "ALL_DATASETS", [dataset]), \
             patch.object(ci_update, "load_existing", side_effect=fake_load_existing), \
             patch.object(ci_update, "save_json", side_effect=lambda path, data: saved.update({path: data})), \
             patch.object(ci_update, "iter_weekdays", return_value=["2026-07-15"]), \
             patch.object(ci_update, "MAKEUP_WORKDAY_CANDIDATES", set()), \
             patch.object(
                 ci_update,
                 "fetch_searchyc_bundle_result",
                 side_effect=lambda curves, qxll, day: (fake_fetch_searchyc_bundle(curves, qxll, day), True),
             ):
            changed = ci_update.update_all_datasets("2026-07-15")

        self.assertEqual(calls, [(["local_gov"], "0")])
        self.assertTrue(changed["local_gov_spot"])
        self.assertGreater(saved[dataset.filename]["rows"][0][1], 3.0)

    def test_update_all_reuses_local_government_ytm_for_spot_and_ytm(self):
        spot = next(d for d in ci_update.ALL_DATASETS if d.key == "local_gov_spot")
        ytm = next(d for d in ci_update.ALL_DATASETS if d.key == "local_gov_ytm")
        states = {
            dataset.filename: {"dates": [], "terms": dataset.terms, "rows": [], "meta": dataset.meta}
            for dataset in [spot, ytm]
        }
        calls = []

        def fake_load_existing(filepath, terms=None):
            return states[filepath]

        def fake_fetch_searchyc_bundle(curves, qxll, day):
            calls.append(([curve.key for curve in curves], qxll))
            return {"local_gov": {"1Y": 2.0, "2Y": 3.0}}

        with patch.object(ci_update, "ALL_DATASETS", [spot, ytm]), \
             patch.object(ci_update, "load_existing", side_effect=fake_load_existing), \
             patch.object(ci_update, "save_json"), \
             patch.object(ci_update, "iter_weekdays", return_value=["2026-07-15"]), \
             patch.object(ci_update, "MAKEUP_WORKDAY_CANDIDATES", set()), \
             patch.object(
                 ci_update,
                 "fetch_searchyc_bundle_result",
                 side_effect=lambda curves, qxll, day: (fake_fetch_searchyc_bundle(curves, qxll, day), True),
             ):
            changed = ci_update.update_all_datasets("2026-07-15")

        self.assertEqual(calls, [(["local_gov"], "0")])
        self.assertTrue(changed["local_gov_spot"])
        self.assertTrue(changed["local_gov_ytm"])

    def test_update_dataset_writes_bootstrapped_local_government_spot(self):
        dataset = next(d for d in ci_update.ALL_DATASETS if d.key == "local_gov_spot")
        existing = {"dates": [], "terms": dataset.terms, "rows": [], "meta": dataset.meta}
        fetched_ytm = {"1Y": 2.0, "2Y": 3.0, "3Y": 4.0}
        saved = {}

        with patch.object(ci_update, "load_existing", return_value=existing), \
             patch.object(ci_update, "save_json", side_effect=lambda path, data: saved.update({path: data})), \
             patch.object(ci_update, "iter_weekdays", return_value=["2026-07-15"]), \
             patch.object(ci_update, "fetch_searchyc_bundle", return_value={"local_gov": fetched_ytm}):
            updated = ci_update.update_dataset(dataset, "2026-07-15")

        self.assertTrue(updated)
        self.assertIn(dataset.filename, saved)
        output = saved[dataset.filename]
        self.assertEqual(output["dates"], ["2026-07-15"])
        self.assertEqual(output["terms"][:3], ["1Y", "2Y", "3Y"])
        self.assertEqual(output["rows"][0][0], 2.0)
        self.assertGreater(output["rows"][0][1], 3.0)

    def test_makeup_date_backfills_all_eighteen_datasets_independently(self):
        datasets = list(ci_update.ALL_DATASETS)
        states = {
            dataset.filename: {
                "dates": [ci_update.dataset_history_start(dataset), "2025-10-10", "2026-07-31"],
                "terms": dataset.terms,
                "rows": [
                    [0.9] + [None] * (len(dataset.terms) - 1),
                    [1.0] + [None] * (len(dataset.terms) - 1),
                    [1.1] + [None] * (len(dataset.terms) - 1),
                ],
                "meta": dataset.meta,
            }
            for dataset in datasets
        }
        saved = {}
        audit = ci_update.empty_makeup_audit()

        def fake_fetch_result(curves, qxll, day):
            self.assertEqual(day, "2025-10-11")
            return ({curve.key: {"1Y": 2.0} for curve in curves}, True)

        with patch.object(ci_update, "load_existing", side_effect=lambda path, terms=None: states[path]), \
             patch.object(ci_update, "load_makeup_audit", return_value=audit), \
             patch.object(ci_update, "save_json", side_effect=lambda path, data: saved.update({path: data})), \
             patch.object(ci_update, "iter_weekdays", return_value=[]), \
             patch.object(ci_update, "MAKEUP_WORKDAY_CANDIDATES", {"2025-10-11"}), \
             patch.object(ci_update, "fetch_searchyc_bundle_result", side_effect=fake_fetch_result, create=True):
            changed = ci_update.update_all_datasets("2026-07-31")

        self.assertEqual(set(changed), {dataset.key for dataset in datasets})
        self.assertTrue(all(changed.values()))
        for dataset in datasets:
            self.assertEqual(
                saved[dataset.filename]["dates"],
                [
                    ci_update.dataset_history_start(dataset),
                    "2025-10-10",
                    "2025-10-11",
                    "2026-07-31",
                ],
            )
            self.assertEqual(audit["datasets"][dataset.key]["2025-10-11"], "data")

    def test_successful_empty_makeup_result_is_finalized_and_not_retried(self):
        dataset = next(d for d in ci_update.ALL_DATASETS if d.key == "gov_spot")
        state = {
            "dates": [ci_update.PREMIUM_HISTORY_START_DATE, "2025-10-10", "2026-07-31"],
            "terms": dataset.terms,
            "rows": [
                [0.9] * len(dataset.terms),
                [1.0] * len(dataset.terms),
                [1.1] * len(dataset.terms),
            ],
            "meta": dataset.meta,
        }
        audit = ci_update.empty_makeup_audit()
        calls = []

        def fake_fetch_result(curves, qxll, day):
            calls.append(day)
            return ({}, True)

        def run_once():
            with patch.object(ci_update, "ALL_DATASETS", [dataset]), \
                 patch.object(ci_update, "load_existing", return_value=state), \
                 patch.object(ci_update, "load_makeup_audit", return_value=audit), \
                 patch.object(ci_update, "save_json"), \
                 patch.object(ci_update, "iter_weekdays", return_value=[]), \
                 patch.object(ci_update, "MAKEUP_WORKDAY_CANDIDATES", {"2025-10-11"}), \
                 patch.object(ci_update, "fetch_searchyc_bundle_result", side_effect=fake_fetch_result, create=True):
                ci_update.update_all_datasets("2026-07-31")

        run_once()
        run_once()

        self.assertEqual(calls, ["2025-10-11"])
        self.assertEqual(audit["datasets"][dataset.key]["2025-10-11"], "empty")

    def test_failed_makeup_request_remains_retryable(self):
        dataset = next(d for d in ci_update.ALL_DATASETS if d.key == "gov_spot")
        state = {
            "dates": [ci_update.PREMIUM_HISTORY_START_DATE, "2025-10-10", "2026-07-31"],
            "terms": dataset.terms,
            "rows": [
                [0.9] * len(dataset.terms),
                [1.0] * len(dataset.terms),
                [1.1] * len(dataset.terms),
            ],
            "meta": dataset.meta,
        }
        audit = ci_update.empty_makeup_audit()

        with patch.object(ci_update, "ALL_DATASETS", [dataset]), \
             patch.object(ci_update, "load_existing", return_value=state), \
             patch.object(ci_update, "load_makeup_audit", return_value=audit), \
             patch.object(ci_update, "save_json"), \
             patch.object(ci_update, "iter_weekdays", return_value=[]), \
             patch.object(ci_update, "MAKEUP_WORKDAY_CANDIDATES", {"2025-10-11"}), \
             patch.object(ci_update, "fetch_searchyc_bundle_result", return_value=({}, False), create=True):
            ci_update.update_all_datasets("2026-07-31")

        self.assertNotIn("2025-10-11", audit.get("datasets", {}).get(dataset.key, {}))


class StrictFetchTests(unittest.TestCase):
    def test_ci_network_failure_stops_before_saving_any_dataset(self):
        dataset = ci_update.ALL_DATASETS[0]
        state = ci_update.empty_dataset(dataset)
        state['dates'] = ['2026-09-30']
        state['rows'] = [[2.0] * len(dataset.terms)]
        with patch.dict(ci_update.os.environ, {'CI_STRICT_FETCH': '1'}), \
             patch.object(ci_update, 'ALL_DATASETS', [dataset]), \
             patch.object(ci_update, 'load_existing', return_value=state), \
             patch.object(ci_update, 'MAKEUP_WORKDAY_CANDIDATES', set()), \
             patch.object(ci_update, 'MAX_RETRIES', 1), \
             patch.object(ci_update.requests, 'post', side_effect=ci_update.requests.ConnectionError('unavailable')), \
             patch.object(ci_update, 'save_json') as save:
            with self.assertRaisesRegex(RuntimeError, 'ChinaBond request failed'):
                ci_update.update_all_datasets('2026-10-01')
        save.assert_not_called()
        self.assertEqual(state['dates'], ['2026-09-30'])

    def test_empty_successful_response_is_not_a_network_failure(self):
        with patch.dict(ci_update.os.environ, {'CI_STRICT_FETCH': '1'}), \
             patch.object(ci_update.requests, 'post') as post:
            post.return_value.json.return_value = []
            result, completed = ci_update.fetch_searchyc_bundle_result([ci_update.CURVES[0]], '1', '2026-10-01')
        self.assertEqual(result, {})
        self.assertTrue(completed)


if __name__ == "__main__":
    unittest.main()
