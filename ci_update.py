#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update ChinaBond yield curve JSON files for GitHub Pages.

The site uses one JSON file per curve/measure dataset:
9 bond curves x 2 measures = 18 datasets.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import sys
import time
import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

import requests


SEARCHYC_URL = "https://yield.chinabond.com.cn/cbweb-mn/yc/searchYc"
PRESET_MODEL_SOURCE_URL = "https://hh9616.github.io/preset-rate-reference-model/data/model-data.js"
SUMMARY_FILE = "data/summary.json"
LIFE_DISCOUNT_FILE = "data/life_discount.json"
PRESET_MODEL_FILE = "assets/preset_model_data.js"
MAKEUP_AUDIT_FILE = "data/data_makeup_weekend_audit.json"
DATA_SCHEMA_VERSION = 2
LIFE_DISCOUNT_SCHEMA_VERSION = 3
MAKEUP_AUDIT_SCHEMA_VERSION = 1
START_DATE = "2020-01-02"
PREMIUM_HISTORY_START_DATE = "2013-01-01"
SUMMARY_TERMS = ["1Y", "5Y", "10Y", "20Y", "30Y"]
LIFE_TERMS = [f"{i}Y" for i in range(1, 51)]
LIFE_SPREAD_TERMS = [f"{i}Y" for i in range(1, 21)]
LIFE_MA_PERIOD = 750
LIFE_MONITOR_MA_PERIODS = [250, 750, 2500]
LIFE_MONITOR_DATASET_KEYS = ["gov_spot", "cdb_spot", "rail_spot", "corp_aaa_spot"]
LIFE_ULTIMATE_RATE = 4.5
LIFE_BENCHMARK_KEYS = ["gov_spot", "cdb_spot"]
LIFE_SHORT_SPREAD_TERM = "20Y"
LIFE_LONG_SPREAD_TERM = "50Y"
LIFE_LONG_PREMIUM_DEFAULT = "50y"
LIFE_LONG_PREMIUM_OPTIONS = [
    {"key": "40y", "name": "40年标的溢价"},
    {"key": "50y", "name": "50年标的溢价"},
    {"key": "avg_40_50", "name": "40-50年平均溢价"},
]
BJ_TZ = timezone(timedelta(hours=8))
MAX_RETRIES = 3
RETRY_DELAY = 3
MAKEUP_EMPTY_GRACE_DAYS = 7

# Weekend workdays published in the annual State Council holiday schedules.
# Each curve still has to return valid ChinaBond data before the date is stored.
MAKEUP_WORKDAY_CANDIDATES = {
    "2013-01-05", "2013-01-06", "2013-02-16", "2013-02-17", "2013-04-07",
    "2013-04-27", "2013-04-28", "2013-06-08", "2013-06-09", "2013-09-22",
    "2013-09-29", "2013-10-12",
    "2014-01-26", "2014-02-08", "2014-05-04", "2014-09-28", "2014-10-11",
    "2015-01-04", "2015-02-15", "2015-02-28", "2015-09-06", "2015-10-10",
    "2016-02-06", "2016-02-14", "2016-06-12", "2016-09-18", "2016-10-08",
    "2016-10-09",
    "2017-01-22", "2017-02-04", "2017-04-01", "2017-05-27", "2017-09-30",
    "2018-02-11", "2018-02-24", "2018-04-08", "2018-04-28", "2018-09-29",
    "2018-09-30", "2018-12-29",
    "2019-02-02", "2019-02-03", "2019-04-28", "2019-05-05", "2019-09-29",
    "2019-10-12",
    "2020-01-19", "2020-04-26", "2020-05-09", "2020-06-28", "2020-09-27",
    "2020-10-10",
    "2021-02-07", "2021-02-20", "2021-04-25", "2021-05-08", "2021-09-18",
    "2021-09-26", "2021-10-09",
    "2022-01-29", "2022-01-30", "2022-04-02", "2022-04-24", "2022-05-07",
    "2022-10-08", "2022-10-09",
    "2023-01-28", "2023-01-29", "2023-04-23", "2023-05-06", "2023-06-25",
    "2023-10-07", "2023-10-08",
    "2024-02-04", "2024-02-18", "2024-04-07", "2024-04-28", "2024-05-11",
    "2024-09-14", "2024-09-29", "2024-10-12",
    "2025-01-26", "2025-02-08", "2025-04-27", "2025-09-28", "2025-10-11",
    "2026-01-04", "2026-02-14", "2026-02-28", "2026-05-09", "2026-09-20",
    "2026-10-10",
}

SEARCHYC_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://yield.chinabond.com.cn/cbweb-mn/yield_main?locale=zh_CN",
    "Content-Type": "application/x-www-form-urlencoded",
}


@dataclass(frozen=True)
class CurveConfig:
    key: str
    display_name: str
    short_name: str
    yc_def_id: str
    max_year: int
    has_official_spot: bool = True


@dataclass(frozen=True)
class DatasetConfig:
    key: str
    curve: CurveConfig
    rate_type: str
    filename: str
    display_name: str
    source_note: str

    @property
    def terms(self) -> List[str]:
        return [f"{i}Y" for i in range(1, self.curve.max_year + 1)]

    @property
    def qxll(self) -> str:
        return "1" if self.rate_type == "spot" else "0"

    @property
    def is_bootstrapped(self) -> bool:
        return self.rate_type == "spot" and not self.curve.has_official_spot

    @property
    def meta(self) -> dict:
        return {
            "schemaVersion": DATA_SCHEMA_VERSION,
            "dataset": self.key,
            "ycDefId": self.curve.yc_def_id,
            "rateType": self.rate_type,
            "maxYear": self.curve.max_year,
        }

    @property
    def is_legacy_file(self) -> bool:
        return self.key in LEGACY_FILENAMES

    @property
    def requires_isolated_fetch(self) -> bool:
        return self.curve.key == "local_gov"


CURVES = [
    CurveConfig("gov", "中债国债", "国债", "2c9081e50a2f9606010a3068cae70001", 50),
    CurveConfig("cdb", "中债国开债", "国开债", "8a8b2ca037a7ca910137bfaa94fa5057", 50),
    CurveConfig("rail", "中债铁道债", "铁道债", "2c9081e91b55cc84011c25e7977b4dac", 30),
    CurveConfig("corp_aaa", "中债企业债(AAA)", "AAA企业债", "2c9081e50a2f9606010a309f4af50111", 30),
    CurveConfig("exim", "中债进出口行债", "进出口行债", "8a8b2ca0567e033b01567ea9c1d96af8", 20),
    CurveConfig("adbc", "中债农发行债", "农发行债", "2c9081e50a2f9606010a306abdde0003", 30),
    CurveConfig("local_gov", "中国地方政府债", "地方政府债", "998183ff8c00f640018c32d4721a0d16", 30, False),
    CurveConfig("corp_aa", "中债企业债(AA)", "AA企业债", "2c90818812b319130112c279222836c3", 30),
    CurveConfig("corp_a", "中债企业债(A)", "A企业债", "2c9081e91e6a3313011e6d438a58000d", 30),
]

LEGACY_FILENAMES = {
    "gov_spot": "data/data.json",
    "gov_ytm": "data/data_gov_ytm.json",
    "cdb_spot": "data/data_cdb.json",
    "cdb_ytm": "data/data_cdb_ytm.json",
}


def build_datasets() -> List[DatasetConfig]:
    datasets: List[DatasetConfig] = []
    for curve in CURVES:
        for rate_type, zh in [("spot", "即期"), ("ytm", "到期")]:
            key = f"{curve.key}_{rate_type}"
            filename = LEGACY_FILENAMES.get(key, f"data/data_{key}.json")
            if rate_type == "spot" and not curve.has_official_spot:
                source = "中债登到期收益率(qxll=0)经年付息平价债 bootstrap 推导"
            else:
                qxll = "1" if rate_type == "spot" else "0"
                source = f"中债登 searchYc 接口，ycDefIds={curve.yc_def_id}，qxll={qxll}"
            datasets.append(
                DatasetConfig(
                    key=key,
                    curve=curve,
                    rate_type=rate_type,
                    filename=filename,
                    display_name=f"{curve.display_name}{zh}",
                    source_note=source,
                )
            )
    return datasets


ALL_DATASETS = build_datasets()
DATASET_BY_KEY = {dataset.key: dataset for dataset in ALL_DATASETS}
CURVE_BY_ID = {curve.yc_def_id: curve for curve in CURVES}
LIFE_BENCHMARKS = [
    DATASET_BY_KEY[key]
    for key in LIFE_BENCHMARK_KEYS
    if key in DATASET_BY_KEY
]
LIFE_SPREAD_BONDS = [
    dataset
    for dataset in ALL_DATASETS
    if dataset.rate_type == "spot" and dataset.key not in LIFE_BENCHMARK_KEYS and dataset.curve.max_year >= 20
]


def now_beijing() -> date:
    return datetime.now(BJ_TZ).date()


def iter_weekdays(start_str: str, end_str: str) -> Iterable[str]:
    current = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_str, "%Y-%m-%d").date()
    while current <= end:
        if current.weekday() < 5:
            yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def next_fetch_date(existing: dict) -> str:
    dates = existing.get("dates") or []
    if not dates:
        return START_DATE
    return (datetime.strptime(dates[-1], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def has_current_metadata(dataset: DatasetConfig, existing: dict) -> bool:
    return existing.get("meta") == dataset.meta


def dataset_history_start(dataset: DatasetConfig) -> str:
    if dataset.key in LIFE_MONITOR_DATASET_KEYS:
        return PREMIUM_HISTORY_START_DATE
    return START_DATE


def needs_extended_history_rebuild(dataset: DatasetConfig, existing: dict) -> bool:
    dates = existing.get("dates") or []
    return dataset.key in LIFE_MONITOR_DATASET_KEYS and bool(dates) and dates[0] > PREMIUM_HISTORY_START_DATE


def next_fetch_date_for_dataset(dataset: DatasetConfig, existing: dict) -> str:
    if needs_extended_history_rebuild(dataset, existing):
        return dataset_history_start(dataset)
    if not dataset.is_legacy_file and not has_current_metadata(dataset, existing):
        return dataset_history_start(dataset)
    return next_fetch_date(existing)


def empty_dataset(dataset: DatasetConfig) -> dict:
    return {"dates": [], "terms": dataset.terms, "rows": [], "meta": dataset.meta}


def load_existing(filepath: str, terms: Optional[List[str]] = None) -> dict:
    expected_terms = terms or [f"{i}Y" for i in range(1, 51)]
    if not os.path.exists(filepath):
        return {"dates": [], "terms": expected_terms, "rows": []}
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("dates", [])
    data.setdefault("rows", [])
    data["terms"] = data.get("terms") or expected_terms
    return data


def save_json(filepath: str, data: dict):
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, filepath)


def empty_makeup_audit() -> dict:
    return {"schemaVersion": MAKEUP_AUDIT_SCHEMA_VERSION, "datasets": {}}


def load_makeup_audit() -> dict:
    if not os.path.exists(MAKEUP_AUDIT_FILE):
        return empty_makeup_audit()
    try:
        with open(MAKEUP_AUDIT_FILE, "r", encoding="utf-8") as f:
            audit = json.load(f)
    except (OSError, ValueError):
        return empty_makeup_audit()
    if audit.get("schemaVersion") != MAKEUP_AUDIT_SCHEMA_VERSION:
        return empty_makeup_audit()
    audit.setdefault("datasets", {})
    return audit


def record_makeup_audit(audit: dict, dataset_key: str, day: str, status: str) -> None:
    audit.setdefault("schemaVersion", MAKEUP_AUDIT_SCHEMA_VERSION)
    audit.setdefault("datasets", {}).setdefault(dataset_key, {})[day] = status


def makeup_dataset_needs_check(
    dataset: DatasetConfig,
    state: dict,
    audit: dict,
    day: str,
    today_str: str,
) -> bool:
    if day not in MAKEUP_WORKDAY_CANDIDATES or day > today_str:
        return False
    if day < dataset_history_start(dataset) or day in set(state.get("dates") or []):
        return False
    status = audit.get("datasets", {}).get(dataset.key, {}).get(day)
    return status not in {"data", "empty"}


def makeup_empty_is_final(day: str, today_str: str) -> bool:
    candidate = datetime.strptime(day, "%Y-%m-%d").date()
    today = datetime.strptime(today_str, "%Y-%m-%d").date()
    return (today - candidate).days >= MAKEUP_EMPTY_GRACE_DAYS


def save_text(filepath: str, text: str):
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, filepath)


def normalize_rates(series_data, max_year: int) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for point in series_data or []:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        tenor, value = point[0], point[1]
        if tenor is None or value is None:
            continue
        tenor_float = float(tenor)
        if abs(tenor_float - round(tenor_float)) < 1e-6:
            year = int(round(tenor_float))
            if 1 <= year <= max_year:
                out[f"{year}Y"] = round(float(value), 8)
    return out


def bootstrap_spot_from_ytm(ytm_rates: Dict[str, float]) -> Dict[str, float]:
    spots_decimal: Dict[int, float] = {}
    years = sorted(
        int(term[:-1])
        for term, value in ytm_rates.items()
        if term.endswith("Y") and value is not None
    )

    for year in years:
        ytm_percent = ytm_rates.get(f"{year}Y")
        if ytm_percent is None:
            continue
        ytm = ytm_percent / 100.0
        coupon = 100.0 * ytm
        if year == 1:
            spots_decimal[year] = ytm
            continue

        known_coupon_pv = 0.0
        for shorter in range(1, year):
            if shorter in spots_decimal:
                known_coupon_pv += coupon / ((1.0 + spots_decimal[shorter]) ** shorter)

        final_cashflow = coupon + 100.0
        final_pv = 100.0 - known_coupon_pv
        if final_pv <= 0:
            spots_decimal[year] = ytm
        else:
            spots_decimal[year] = (final_cashflow / final_pv) ** (1.0 / year) - 1.0

    return {f"{year}Y": round(rate * 100.0, 8) for year, rate in spots_decimal.items()}


def searchyc_payload(curve_ids: List[str], qxll: str, query_date: str) -> dict:
    return {
        "xyzSelect": "txy",
        "workTimes": query_date,
        "dxbj": "0",
        "qxll": qxll,
        "yqqxN": "N",
        "yqqxK": "K",
        "ycDefIds": ",".join(curve_ids),
        "wrjxCBFlag": "0",
        "locale": "zh_CN",
    }


def fetch_searchyc_bundle_result(
    curves: List[CurveConfig], qxll: str, query_date: str
) -> tuple[Dict[str, Dict[str, float]], bool]:
    if not curves:
        return {}, True

    payload = searchyc_payload([curve.yc_def_id for curve in curves], qxll, query_date)
    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(SEARCHYC_URL, data=payload, headers=SEARCHYC_HEADERS, timeout=30)
            resp.raise_for_status()
            raw = resp.json()
            if not raw or not isinstance(raw, list):
                return {}, True

            results: Dict[str, Dict[str, float]] = {}
            requested_by_id = {curve.yc_def_id: curve for curve in curves}
            for index, item in enumerate(raw):
                returned_id = item.get("ycDefId")
                curve = requested_by_id.get(returned_id)
                if curve is None and index < len(curves):
                    curve = curves[index]
                if curve is None:
                    continue
                results[curve.key] = normalize_rates(item.get("seriesData", []), curve.max_year)
            return results, True
        except Exception as exc:  # pragma: no cover - exercised in GitHub Actions/network
            last_error = exc
            if attempt < MAX_RETRIES:
                print(f"  {query_date} qxll={qxll}: retry {attempt}/{MAX_RETRIES} after {exc}")
                time.sleep(RETRY_DELAY)

    print(f"  {query_date} qxll={qxll}: failed - {last_error}")
    return {}, False


def fetch_searchyc_bundle(curves: List[CurveConfig], qxll: str, query_date: str) -> Dict[str, Dict[str, float]]:
    return fetch_searchyc_bundle_result(curves, qxll, query_date)[0]


def fetch_dataset_rates(dataset: DatasetConfig, query_date: str) -> Dict[str, float]:
    if dataset.is_bootstrapped:
        ytm = fetch_searchyc_bundle([dataset.curve], "0", query_date).get(dataset.curve.key, {})
        return bootstrap_spot_from_ytm(ytm) if ytm else {}
    return fetch_searchyc_bundle([dataset.curve], dataset.qxll, query_date).get(dataset.curve.key, {})


def row_from_rates(terms: List[str], rates: Dict[str, float]) -> List[Optional[float]]:
    return [rates.get(term) for term in terms]


def merge_rates(existing: dict, terms: List[str], rates_by_date: Dict[str, Dict[str, float]]) -> dict:
    by_date = {
        day: list(existing.get("rows", [])[index])
        for index, day in enumerate(existing.get("dates", []))
    }
    for day, rates in rates_by_date.items():
        by_date[day] = row_from_rates(terms, rates)
    dates = sorted(by_date)
    return {"dates": dates, "terms": terms, "rows": [by_date[day] for day in dates]}


def update_dataset(dataset: DatasetConfig, today_str: str) -> bool:
    existing = load_existing(dataset.filename, dataset.terms)
    start = next_fetch_date_for_dataset(dataset, existing)
    if needs_extended_history_rebuild(dataset, existing):
        existing = empty_dataset(dataset)
    if start == dataset_history_start(dataset) and not dataset.is_legacy_file and not has_current_metadata(dataset, existing):
        existing = empty_dataset(dataset)
    if start > today_str:
        return False

    fetched: Dict[str, Dict[str, float]] = {}
    for day in iter_weekdays(start, today_str):
        rates = fetch_dataset_rates(dataset, day)
        if rates:
            fetched[day] = rates
            print(f"  {dataset.display_name} {day}: {len(rates)} terms")

    if not fetched:
        return False

    output = merge_rates(existing, dataset.terms, fetched)
    output["meta"] = dataset.meta
    save_json(dataset.filename, output)
    return True


def append_dataset_day(states: Dict[str, dict], dataset: DatasetConfig, day: str, rates: Dict[str, float]):
    if not rates:
        return
    state = states[dataset.key]
    if day in state["dates"]:
        return
    state["dates"].append(day)
    state["rows"].append(row_from_rates(dataset.terms, rates))


def dataset_needs_day(state: dict, day: str) -> bool:
    dates = state.get("dates") or []
    return day not in set(dates)


def sort_dataset_state(state: dict) -> None:
    rows_by_date = {
        day: state.get("rows", [])[index]
        for index, day in enumerate(state.get("dates", []))
    }
    dates = sorted(rows_by_date)
    state["dates"] = dates
    state["rows"] = [rows_by_date[day] for day in dates]


def update_all_datasets(today_str: str) -> Dict[str, bool]:
    states = {}
    starts = []
    starts_by_key = {}
    audit = load_makeup_audit()
    audit_before = json.dumps(audit, ensure_ascii=False, sort_keys=True)
    for dataset in ALL_DATASETS:
        state = load_existing(dataset.filename, dataset.terms)
        start = next_fetch_date_for_dataset(dataset, state)
        starts_by_key[dataset.key] = start
        if start == dataset_history_start(dataset) and not dataset.is_legacy_file and not has_current_metadata(dataset, state):
            state = empty_dataset(dataset)
        states[dataset.key] = state
        if start <= today_str:
            starts.append(start)

    makeup_days = sorted(
        day
        for day in MAKEUP_WORKDAY_CANDIDATES
        if any(
            makeup_dataset_needs_check(dataset, states[dataset.key], audit, day, today_str)
            for dataset in ALL_DATASETS
        )
    )
    if not starts and not makeup_days:
        return {dataset.key: False for dataset in ALL_DATASETS}

    changed = {dataset.key: False for dataset in ALL_DATASETS}
    normal_days = list(iter_weekdays(min(starts), today_str)) if starts else []
    candidate_days = sorted(set(normal_days) | set(makeup_days))
    if starts:
        print(f"Fetch range: {min(starts)} -> {today_str}")
    if makeup_days:
        print(f"Makeup weekend checks: {makeup_days[0]} -> {makeup_days[-1]} ({len(makeup_days)} dates)")

    for day in candidate_days:
        makeup_pending_keys = {
            dataset.key
            for dataset in ALL_DATASETS
            if makeup_dataset_needs_check(dataset, states[dataset.key], audit, day, today_str)
        }
        pending = [
            dataset
            for dataset in ALL_DATASETS
            if dataset_needs_day(states[dataset.key], day)
            and (day >= starts_by_key[dataset.key] or dataset.key in makeup_pending_keys)
        ]
        if not pending:
            continue

        spot_curves = []
        ytm_curves = []
        isolated = []
        for dataset in pending:
            if dataset.requires_isolated_fetch:
                isolated.append(dataset)
                continue
            if dataset.is_bootstrapped or dataset.rate_type == "ytm":
                if dataset.curve not in ytm_curves:
                    ytm_curves.append(dataset.curve)
            elif dataset.rate_type == "spot":
                if dataset.curve not in spot_curves:
                    spot_curves.append(dataset.curve)

        spot_results, spot_completed = (
            fetch_searchyc_bundle_result(spot_curves, "1", day) if spot_curves else ({}, True)
        )
        ytm_results, ytm_completed = (
            fetch_searchyc_bundle_result(ytm_curves, "0", day) if ytm_curves else ({}, True)
        )

        for dataset in [d for d in pending if not d.requires_isolated_fetch]:
            rates: Dict[str, float] = {}
            if dataset.is_bootstrapped:
                ytm = ytm_results.get(dataset.curve.key, {})
                rates = bootstrap_spot_from_ytm(ytm) if ytm else {}
                request_completed = ytm_completed
            elif dataset.rate_type == "spot":
                rates = spot_results.get(dataset.curve.key, {})
                request_completed = spot_completed
            else:
                rates = ytm_results.get(dataset.curve.key, {})
                request_completed = ytm_completed

            if rates:
                append_dataset_day(states, dataset, day, rates)
                changed[dataset.key] = True
                print(f"  {day} {dataset.display_name}: {len(rates)} terms")
                if dataset.key in makeup_pending_keys:
                    record_makeup_audit(audit, dataset.key, day, "data")
            elif (
                dataset.key in makeup_pending_keys
                and request_completed
                and makeup_empty_is_final(day, today_str)
            ):
                record_makeup_audit(audit, dataset.key, day, "empty")

        isolated_cache: Dict[tuple, tuple[Dict[str, float], bool]] = {}
        for dataset in isolated:
            cache_qxll = "0" if dataset.is_bootstrapped else dataset.qxll
            cache_key = (dataset.curve.key, cache_qxll)
            if cache_key not in isolated_cache:
                results, request_completed = fetch_searchyc_bundle_result([dataset.curve], cache_qxll, day)
                isolated_cache[cache_key] = (results.get(dataset.curve.key, {}), request_completed)
            raw_rates, request_completed = isolated_cache[cache_key]
            rates = bootstrap_spot_from_ytm(raw_rates) if dataset.is_bootstrapped and raw_rates else raw_rates
            if rates:
                append_dataset_day(states, dataset, day, rates)
                changed[dataset.key] = True
                print(f"  {day} {dataset.display_name}: {len(rates)} terms")
                if dataset.key in makeup_pending_keys:
                    record_makeup_audit(audit, dataset.key, day, "data")
            elif (
                dataset.key in makeup_pending_keys
                and request_completed
                and makeup_empty_is_final(day, today_str)
            ):
                record_makeup_audit(audit, dataset.key, day, "empty")

    for dataset in ALL_DATASETS:
        state = states[dataset.key]
        sort_dataset_state(state)
        state["terms"] = dataset.terms
        state["meta"] = dataset.meta
        save_json(dataset.filename, state)

    audit_after = json.dumps(audit, ensure_ascii=False, sort_keys=True)
    if audit_after != audit_before:
        save_json(MAKEUP_AUDIT_FILE, audit)

    return changed


# ================================================================
# Life insurance liability discount rate curves
# ================================================================

def build_life_base_curve(ma_rates: Dict[str, float]) -> Dict[str, float]:
    r20 = ma_rates.get("20Y")
    if r20 is None:
        return {}

    base: Dict[str, float] = {}
    for year in range(1, 51):
        term = f"{year}Y"
        if year <= 20:
            value = ma_rates.get(term)
        elif year <= 40:
            r_star = ma_rates.get(term)
            if r_star is None:
                value = None
            else:
                weight = (year - 20) / 20.0
                first_interp = r20 + (LIFE_ULTIMATE_RATE - r20) * weight
                value = first_interp * weight + r_star * (1.0 - weight)
        else:
            value = LIFE_ULTIMATE_RATE

        if value is not None:
            base[term] = round(value, 8)
    return base


def dataset_summary(dataset: DatasetConfig) -> dict:
    return {
        "key": dataset.key,
        "name": dataset.display_name,
        "shortName": dataset.curve.short_name,
        "sourceFile": dataset.filename,
        "sourceNote": dataset.source_note,
    }


def terminal_benchmark_spread(benchmark_rates: Dict[str, float], mode: str = LIFE_LONG_PREMIUM_DEFAULT) -> Optional[float]:
    short_rate = benchmark_rates.get(LIFE_SHORT_SPREAD_TERM)
    if short_rate is None:
        return None

    if mode == "40y":
        long_rate = benchmark_rates.get("40Y")
        return None if long_rate is None else float(long_rate) - float(short_rate)

    if mode == "avg_40_50":
        values = [
            benchmark_rates.get(f"{year}Y")
            for year in range(40, 51)
        ]
        if any(value is None for value in values):
            return None
        average_long_rate = sum(float(value) for value in values) / len(values)
        return average_long_rate - float(short_rate)

    long_rate = benchmark_rates.get(LIFE_LONG_SPREAD_TERM)
    return None if long_rate is None else float(long_rate) - float(short_rate)


def build_accounting_premium_curve(
    benchmark_rates: Dict[str, float],
    spread_bond_rates: Dict[str, float],
    long_premium_mode: str = LIFE_LONG_PREMIUM_DEFAULT,
) -> Dict[str, float]:
    front_spreads: Dict[int, float] = {}
    for year in range(1, 21):
        term = f"{year}Y"
        bond = spread_bond_rates.get(term)
        benchmark = benchmark_rates.get(term)
        if bond is not None and benchmark is not None:
            front_spreads[year] = float(bond) - float(benchmark)

    spread20 = front_spreads.get(20)
    spread40 = terminal_benchmark_spread(benchmark_rates, long_premium_mode)
    if spread20 is None or spread40 is None:
        return {}

    premium: Dict[str, float] = {}
    for year in range(1, 51):
        if year <= 20:
            value = front_spreads.get(year)
        elif year < 40:
            weight = (year - 20) / 20.0
            value = spread20 + (spread40 - spread20) * weight
        else:
            value = spread40
        if value is not None:
            premium[f"{year}Y"] = round(value, 8)
    return premium


def build_life_discount_spot_curve(base_curve: Dict[str, float], premium_curve: Dict[str, float]) -> Dict[str, float]:
    spot: Dict[str, float] = {}
    for year in range(1, 51):
        term = f"{year}Y"
        base = base_curve.get(term)
        premium = premium_curve.get(term)
        if base is None or premium is None:
            continue
        spot[term] = round(base + premium, 8)
    return spot


def build_forward_curve(spot_curve: Dict[str, float]) -> Dict[str, float]:
    forward: Dict[str, float] = {}
    previous_spot = None
    for year in range(1, 51):
        term = f"{year}Y"
        spot = spot_curve.get(term)
        if spot is None:
            previous_spot = None
            continue
        if year == 1 or previous_spot is None:
            value = spot
        else:
            current_discount = (1.0 + spot / 100.0) ** year
            previous_discount = (1.0 + previous_spot / 100.0) ** (year - 1)
            value = (current_discount / previous_discount - 1.0) * 100.0
        forward[term] = round(value, 8)
        previous_spot = spot
    return forward


def moving_average_rows(data: dict, period: int, terms: List[str]) -> List[tuple]:
    rows = data.get("rows", [])
    dates = data.get("dates", [])
    source_terms = data.get("terms", [])
    term_indexes = [source_terms.index(term) if term in source_terms else None for term in terms]
    sums = [0.0 for _ in terms]
    valid_counts = [0 for _ in terms]
    output = []

    for row_index, row in enumerate(rows):
        for term_index, source_index in enumerate(term_indexes):
            value = row[source_index] if source_index is not None and source_index < len(row) else None
            if value is not None:
                sums[term_index] += float(value)
                valid_counts[term_index] += 1

            old_row_index = row_index - period
            if old_row_index >= 0:
                old_row = rows[old_row_index]
                old_value = old_row[source_index] if source_index is not None and source_index < len(old_row) else None
                if old_value is not None:
                    sums[term_index] -= float(old_value)
                    valid_counts[term_index] -= 1

        if row_index >= period - 1:
            ma = {}
            for term_index, term in enumerate(terms):
                if valid_counts[term_index] == period:
                    ma[term] = round(sums[term_index] / period, 8)
            if len(ma) == len(terms):
                output.append((dates[row_index], ma))
    return output


def moving_average_map(data: dict, period: int, terms: List[str]) -> Dict[str, Dict[str, float]]:
    return {
        curve_date: ma_rates
        for curve_date, ma_rates in moving_average_rows(data, period, terms)
    }


def available_life_terms(data: dict) -> List[str]:
    source_terms = set(data.get("terms") or [])
    return [term for term in LIFE_TERMS if term in source_terms]


def build_life_discount_data(benchmark_data: Dict[str, dict], spread_bond_data: Dict[str, dict]) -> dict:
    monitor_data = {
        key: data
        for key, data in {**benchmark_data, **spread_bond_data}.items()
        if key in LIFE_MONITOR_DATASET_KEYS and data.get("dates") and data.get("rows")
    }
    benchmark_ma = {
        key: moving_average_map(data, LIFE_MA_PERIOD, LIFE_TERMS)
        for key, data in benchmark_data.items()
        if data.get("dates") and data.get("rows")
    }
    spread_bond_ma = {
        key: moving_average_map(data, LIFE_MA_PERIOD, LIFE_SPREAD_TERMS)
        for key, data in spread_bond_data.items()
        if data.get("dates") and data.get("rows")
    }
    monitor_ma = {
        str(period): {
            key: moving_average_map(data, period, available_life_terms(data))
            for key, data in monitor_data.items()
        }
        for period in LIFE_MONITOR_MA_PERIODS
    }

    if not benchmark_ma or not spread_bond_ma:
        dates: List[str] = []
    else:
        common_dates = set.intersection(
            *[set(rows) for rows in [*benchmark_ma.values(), *spread_bond_ma.values()]]
        )
        dates = sorted(common_dates)

    base_rows: Dict[str, List[List[Optional[float]]]] = {key: [] for key in benchmark_ma}
    benchmark_rows: Dict[str, List[List[Optional[float]]]] = {key: [] for key in benchmark_ma}
    spread_bond_rows: Dict[str, List[List[Optional[float]]]] = {key: [] for key in spread_bond_ma}
    monitor_rows: Dict[str, Dict[str, List[List[Optional[float]]]]] = {
        period: {key: [] for key in rows_by_key}
        for period, rows_by_key in monitor_ma.items()
    }
    usable_dates = []

    for curve_date in dates:
        bases_for_date: Dict[str, Dict[str, float]] = {}
        for key, rows_by_date in benchmark_ma.items():
            base_curve = build_life_base_curve(rows_by_date[curve_date])
            if len(base_curve) != len(LIFE_TERMS):
                break
            bases_for_date[key] = base_curve
        else:
            usable_dates.append(curve_date)
            for key, rows_by_date in benchmark_ma.items():
                benchmark_rows[key].append(row_from_rates(LIFE_TERMS, rows_by_date[curve_date]))
                base_rows[key].append(row_from_rates(LIFE_TERMS, bases_for_date[key]))
            for key, rows_by_date in spread_bond_ma.items():
                spread_bond_rows[key].append(row_from_rates(LIFE_SPREAD_TERMS, rows_by_date[curve_date]))
            for period, rows_by_key in monitor_ma.items():
                for key, rows_by_date in rows_by_key.items():
                    monitor_rows[period][key].append(row_from_rates(LIFE_TERMS, rows_by_date.get(curve_date, {})))

    benchmark_keys = [dataset.key for dataset in LIFE_BENCHMARKS if dataset.key in benchmark_ma]
    spread_bond_keys = [dataset.key for dataset in LIFE_SPREAD_BONDS if dataset.key in spread_bond_ma]

    return {
        "meta": {
            "schemaVersion": LIFE_DISCOUNT_SCHEMA_VERSION,
            "source": "derived-from-local-curve-json",
            "baseRule": "750日移动平均标的即期收益率曲线 + 20-40年二次插值至4.5%终极利率",
            "premiumRule": "前20年为选中债券即期曲线与标的即期曲线的利差；40年及以后可选标的40Y-20Y、标的50Y-20Y或标的40-50Y平均利率-20Y；20-40年线性插值",
            "forwardRule": "F_t=((1+S_t)^t/(1+S_{t-1})^(t-1))-1",
            "maPeriod": LIFE_MA_PERIOD,
            "ultimateRate": LIFE_ULTIMATE_RATE,
            "shortSpreadTerm": LIFE_SHORT_SPREAD_TERM,
            "longSpreadTerm": LIFE_LONG_SPREAD_TERM,
            "longPremiumDefault": LIFE_LONG_PREMIUM_DEFAULT,
            "longPremiumOptions": LIFE_LONG_PREMIUM_OPTIONS,
            "monitorPeriods": LIFE_MONITOR_MA_PERIODS,
            "monitorDatasetKeys": LIFE_MONITOR_DATASET_KEYS,
        },
        "dates": usable_dates,
        "terms": LIFE_TERMS,
        "spreadTerms": LIFE_SPREAD_TERMS,
        "benchmarks": [dataset_summary(DATASET_BY_KEY[key]) for key in benchmark_keys],
        "spreadBonds": [dataset_summary(DATASET_BY_KEY[key]) for key in spread_bond_keys],
        "baseRows": {key: base_rows[key] for key in benchmark_keys},
        "benchmarkRows": {key: benchmark_rows[key] for key in benchmark_keys},
        "spreadBondRows": {key: spread_bond_rows[key] for key in spread_bond_keys},
        "monitorRows": monitor_rows,
    }


def generate_life_discount_curves() -> bool:
    benchmark_data = {
        dataset.key: load_existing(dataset.filename, dataset.terms)
        for dataset in LIFE_BENCHMARKS
    }
    spread_bond_data = {
        dataset.key: load_existing(dataset.filename, dataset.terms)
        for dataset in LIFE_SPREAD_BONDS
    }
    if not any(data.get("dates") and data.get("rows") for data in spread_bond_data.values()):
        return False
    output = build_life_discount_data(benchmark_data, spread_bond_data)
    if not output["dates"]:
        return False
    save_json(LIFE_DISCOUNT_FILE, output)
    print(
        f"Life discount curves generated: {len(output['dates'])} dates, "
        f"{len(output['benchmarks'])} benchmarks, {len(output['spreadBonds'])} spread bonds"
    )
    return True


# ================================================================
# Preset rate reference model
# ================================================================

def fetch_preset_model_source() -> str:
    resp = requests.get(PRESET_MODEL_SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_preset_model_js(source: str) -> dict:
    match = re.search(r"window\.MODEL_DATA\s*=\s*(\{.*\})\s*;?\s*$", source.strip(), re.S)
    if not match:
        raise ValueError("preset model source does not contain window.MODEL_DATA")
    data = json.loads(match.group(1))
    validate_preset_model_data(data)
    return data


def validate_preset_model_data(data: dict):
    if not isinstance(data, dict):
        raise ValueError("preset model data must be an object")
    if not data.get("updatedAt"):
        raise ValueError("preset model data missing updatedAt")
    series = data.get("series")
    if not isinstance(series, list) or not series:
        raise ValueError("preset model data missing series")
    latest = series[-1]
    required_latest_fields = ["date", "liabilityAnchor", "assetBaseReturn_mean", "modelReferenceValue"]
    missing = [field for field in required_latest_fields if field not in latest]
    if missing:
        raise ValueError(f"preset model latest row missing fields: {', '.join(missing)}")
    actual_values = data.get("actualValues")
    if actual_values is not None and not isinstance(actual_values, list):
        raise ValueError("preset model actualValues must be a list")


def build_preset_model_script(data: dict) -> str:
    validate_preset_model_data(data)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return "window.PRESET_MODEL_DATA = " + payload + ";\n"


def generate_preset_model_data() -> bool:
    try:
        source = fetch_preset_model_source()
        data = parse_preset_model_js(source)
        save_text(PRESET_MODEL_FILE, build_preset_model_script(data))
        print(f"Preset rate model data updated: {len(data.get('series', []))} rows")
        return True
    except Exception as exc:
        print(f"Preset rate model data update failed: {exc}")
        return False


def generate_summary():
    summary = {
        "date": "",
        "curves": {},
        "sources": {
            dataset.key: {
                "name": dataset.display_name,
                "file": dataset.filename,
                "source": dataset.source_note,
                "ycDefId": dataset.curve.yc_def_id,
                "maxYear": dataset.curve.max_year,
            }
            for dataset in ALL_DATASETS
        },
    }
    latest_dates = []

    for dataset in ALL_DATASETS:
        data = load_existing(dataset.filename, dataset.terms)
        if not dataset.is_legacy_file and not has_current_metadata(dataset, data):
            continue
        if not data["dates"] or not data["rows"]:
            continue
        latest_date = data["dates"][-1]
        latest_row = data["rows"][-1]
        prev_row = data["rows"][-2] if len(data["rows"]) >= 2 else None
        terms_data = {}
        for term in SUMMARY_TERMS:
            if term not in data["terms"]:
                continue
            index = data["terms"].index(term)
            value = latest_row[index] if index < len(latest_row) else None
            prev_value = prev_row[index] if prev_row and index < len(prev_row) else None
            change = round(value - prev_value, 4) if value is not None and prev_value is not None else None
            terms_data[term] = {"value": value, "change": change}

        summary["curves"][dataset.key] = {
            "name": dataset.display_name,
            "date": latest_date,
            "terms": terms_data,
        }
        latest_dates.append(latest_date)

    summary["date"] = max(latest_dates) if latest_dates else ""
    save_json(SUMMARY_FILE, summary)



# ================================================================
# 预定利率研究值 — data/predictions.json 生成
# 逻辑与参考站 sig546/preset-rate-research（scripts/update_predictions.py）一致：
#   税收溢价 = max(国开-国债, 进出口-国债) 的移动平均
#   基础回报 = min(国债MA250+溢价250, 国债MA750+溢价750)
#   参考利率 = 6个月(5Y LPR + 5Y定存)/2 的均值
#   预测值   = 分段系数调节( min(参考利率, 基础回报) )
#   未来季度 = 平推法（用最新利率平推至季度末，MA窗口缓慢渐变）
# 数据源：复用已抓取的中债登到期收益率（不额外访问外部源）
# ================================================================
PRESET_PRED_FILE = "data/predictions.json"
PRESET_ACTUALS_FILE = "data/actuals.json"
PRESET_10Y_TERM = "10Y"
PRESET_SEGMENT_COEFF = [
    (0.00, 1.00, 1.00), (1.00, 2.00, 1.00), (2.00, 2.50, 0.95),
    (2.50, 3.00, 0.95), (3.00, 3.50, 0.50),
    (3.50, 4.00, 0.50), (4.00, 10.00, 0.30),
]
PRESET_MAX_RATE = 2.00          # 当前普通型预定利率最高值（2025-09-01 起）
PRESET_TRIGGER_THRESHOLD = 0.25  # 25BP 触发线
PRESET_VALIDATION_MAX_CHANGE_BP = 50
# 人工维护：5年期以上LPR 与 六大行5年定存均值 的调整记录（日期, 值）
PRESET_LPR_HISTORY = [("2025-05-20", 3.5)]
PRESET_DEPOSIT_HISTORY = [
    ("2023-12-22", 2.00), ("2024-07-25", 1.80),
    ("2024-10-18", 1.55), ("2025-05-20", 1.30),
]


def preset_rate_for_month(year: int, month: int, history: List[tuple]) -> float:
    """取指定月份适用的利率（最新一次 <= 月末 的调整，与参考站一致）"""
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    rate = history[0][1] if history else 3.50
    for d, r in history:
        if date.fromisoformat(d) <= month_end:
            rate = r
    return rate


def preset_load_bond_rows() -> List[dict]:
    """从已生成的中债登到期收益率文件提取 国债/国开/进出口 10Y 日频序列"""
    def extract(filepath: str) -> dict:
        data = load_existing(filepath)
        if not data.get("terms") or PRESET_10Y_TERM not in data["terms"]:
            return {}
        idx = data["terms"].index(PRESET_10Y_TERM)
        out = {}
        for i, d in enumerate(data.get("dates", [])):
            try:
                v = data["rows"][i][idx]
            except (IndexError, TypeError):
                v = None
            if v is not None:
                out[d] = v
        return out

    gov = extract("data/data_gov_ytm.json")
    cdb = extract("data/data_cdb_ytm.json")
    ieb = extract("data/data_exim_ytm.json")
    rows = []
    for d in sorted(set(gov) | set(cdb) | set(ieb)):
        rows.append({"date": d, "gov_10y": gov.get(d), "cdb_10y": cdb.get(d), "ieb_10y": ieb.get(d)})
    return rows


def preset_compute_ma(bond_rows: List[dict], comp_date: str, window: int, field: str) -> Optional[float]:
    cutoff = comp_date[:10]
    values = [r[field] for r in bond_rows if r["date"] <= cutoff and r.get(field) is not None]
    if not values:
        return None
    n = min(window, len(values))
    return sum(values[-n:]) / n


def preset_compute_spread_ma(bond_rows: List[dict], comp_date: str, window: int) -> float:
    """max(cdb-gov, ieb-gov) 的移动平均（与参考站一致）"""
    cutoff = comp_date[:10]
    eligible = [r for r in bond_rows if r["date"] <= cutoff]
    spreads = []
    for r in eligible[-window:]:
        s1 = r["cdb_10y"] - r["gov_10y"] if (r.get("cdb_10y") is not None and r.get("gov_10y") is not None) else None
        s2 = r["ieb_10y"] - r["gov_10y"] if (r.get("ieb_10y") is not None and r.get("gov_10y") is not None) else None
        if s1 is not None or s2 is not None:
            spreads.append(max(s1 if s1 is not None else -99, s2 if s2 is not None else -99))
    if not spreads:
        return 0.0912  # 默认利差（与参考站一致）
    return sum(spreads) / len(spreads)


def preset_extend_bond_to_date(bond_rows: List[dict], comp_date: str) -> List[dict]:
    """平推法：用最后已知值填充 (最后日期, comp_date] 的工作日（与参考站一致）"""
    if not bond_rows:
        return bond_rows
    cutoff = comp_date[:10]
    last_date = max(r["date"] for r in bond_rows)
    if last_date >= cutoff:
        return bond_rows
    base = None
    for r in reversed(bond_rows):
        if r.get("gov_10y") is not None:
            base = r
            break
    if base is None:
        return bond_rows
    lg, lc, li = base.get("gov_10y"), base.get("cdb_10y"), base.get("ieb_10y")
    ext = list(bond_rows)
    d = date.fromisoformat(last_date) + timedelta(days=1)
    end = date.fromisoformat(cutoff)
    while d <= end:
        if d.weekday() < 5:  # 仅工作日
            ext.append({"date": d.isoformat(), "gov_10y": lg, "cdb_10y": lc, "ieb_10y": li})
        d += timedelta(days=1)
    return ext


def preset_apply_segment(pre_val: float) -> float:
    """分段系数调节（与参考站一致）"""
    total = 0.0
    for low, high, coeff in PRESET_SEGMENT_COEFF:
        if pre_val > high:
            total += (high - low) * coeff
        elif pre_val > low:
            total += (pre_val - low) * coeff
        else:
            break
    return round(total, 4)


def preset_compute_prediction(comp_date: str, bond_rows: List[dict]) -> dict:
    bond_rows = preset_extend_bond_to_date(bond_rows, comp_date)
    comp_dt = date.fromisoformat(comp_date[:10])

    # 参考利率：6个月 (LPR + 定存)/2 的均值
    ref_rates = []
    for i in range(5, -1, -1):
        y, m = comp_dt.year, comp_dt.month - i
        while m <= 0:
            y -= 1
            m += 12
        ref_rates.append((preset_rate_for_month(y, m, PRESET_LPR_HISTORY) + preset_rate_for_month(y, m, PRESET_DEPOSIT_HISTORY)) / 2)
    ref_rate = sum(ref_rates) / len(ref_rates)

    ma250_gov = preset_compute_ma(bond_rows, comp_date, 250, "gov_10y")
    ma750_gov = preset_compute_ma(bond_rows, comp_date, 750, "gov_10y")
    spread_250 = preset_compute_spread_ma(bond_rows, comp_date, 250)
    spread_750 = preset_compute_spread_ma(bond_rows, comp_date, 750)

    base_250 = (ma250_gov if ma250_gov is not None else 0.0) + spread_250
    base_750 = (ma750_gov if ma750_gov is not None else 0.0) + spread_750
    base_return = min(base_250, base_750)
    pre_adj = min(ref_rate, base_return)
    predicted = preset_apply_segment(pre_adj)
    return {
        "ref_rate": round(ref_rate, 4),
        "base_return": round(base_return, 4),
        "ma250_gov": round(ma250_gov, 4) if ma250_gov is not None else None,
        "ma750_gov": round(ma750_gov, 4) if ma750_gov is not None else None,
        "spread_250": round(spread_250, 4),
        "spread_750": round(spread_750, 4),
        "predicted": round(predicted, 4),
    }


def preset_get_prediction_quarters() -> List[dict]:
    """基于 actuals.json 最新季度，生成未来4个预测季度（与参考站一致）"""
    try:
        with open(PRESET_ACTUALS_FILE, "r", encoding="utf-8") as f:
            actuals_data = json.load(f)
    except Exception:
        return []
    actuals = actuals_data.get("actuals", [])
    if not actuals:
        return []
    latest = actuals[-1]
    latest_q = latest["quarter"]
    year = int(latest_q[:4])
    q = int(latest_q[5:])
    quarters = []
    for _ in range(4):
        q += 1
        if q > 4:
            q = 1
            year += 1
        quarter = f"{year}Q{q}"
        announce_map = {1: f"{year}年4月", 2: f"{year}年7月", 3: f"{year}年10月", 4: f"{year+1}年1月"}
        comp_month_map = {1: 3, 2: 6, 3: 9, 4: 12}
        comp_date = f"{year}-{comp_month_map[q]:02d}-{calendar.monthrange(year, comp_month_map[q])[1]}"
        quarters.append({"quarter": quarter, "announced": announce_map[q], "comp_date": comp_date})
    return quarters


def generate_predictions() -> bool:
    """生成 data/predictions.json（参考站逻辑，复用已抓取中债登数据）"""
    print("[preset-predictions] 生成 data/predictions.json ...")
    bond_rows = preset_load_bond_rows()
    if len(bond_rows) < 100:
        print("[preset-predictions] WARN: 债券数据不足100条，预测可能不准确")
    quarters = preset_get_prediction_quarters()
    if not quarters:
        print("[preset-predictions] actuals.json 为空，无法确定预测季度")
        return False

    old_preds = []
    try:
        with open(PRESET_PRED_FILE, "r", encoding="utf-8") as f:
            old_preds = json.load(f).get("predictions", [])
    except Exception:
        pass

    new_predictions = []
    warnings = []
    for i, q in enumerate(quarters):
        result = preset_compute_prediction(q["comp_date"], bond_rows)
        gap_bp = round((PRESET_MAX_RATE - result["predicted"]) * 100, 1)
        entry = {
            "quarter": q["quarter"],
            "announced": q["announced"],
            "predicted_value": result["predicted"],
            "ref_rate": result["ref_rate"],
            "base_return": result["base_return"],
            "ma250_gov": result["ma250_gov"],
            "ma750_gov": result["ma750_gov"],
            "spread_250": result["spread_250"],
            "spread_750": result["spread_750"],
            "max_rate": PRESET_MAX_RATE,
            "gap_bp": gap_bp,
            "trigger": gap_bp >= PRESET_TRIGGER_THRESHOLD * 100,
        }
        new_predictions.append(entry)
        # 校验（与参考站一致：变动过大告警、单季度合理性）
        if i < len(old_preds) and old_preds[i].get("quarter") == entry["quarter"]:
            change_bp = abs(entry["predicted_value"] - old_preds[i]["predicted_value"]) * 100
            if change_bp > PRESET_VALIDATION_MAX_CHANGE_BP:
                warnings.append(f"⚠️ {entry['quarter']} 预测值变动 {change_bp:.1f}BP（上期 {old_preds[i]['predicted_value']}%），超过 {PRESET_VALIDATION_MAX_CHANGE_BP}BP")
        if entry["predicted_value"] < 0.5 or entry["predicted_value"] > 4.0:
            warnings.append(f"⚠️ {entry['quarter']} 预测值 {entry['predicted_value']}% 明显异常")
        print(f"  {q['quarter']} ({q['announced']}): {result['predicted']:.4f}% (差值 {gap_bp}BP)")

    latest_gov = None
    for r in reversed(bond_rows):
        if r.get("gov_10y") is not None:
            latest_gov = r["gov_10y"]
            break
    now = datetime.now(BJ_TZ)
    output = {
        "last_updated": now.strftime("%Y-%m-%d %H:%M"),
        "method": "平推法",
        "description": "预定利率研究值模型预测",
        "base_data": {
            "lpr_5y": preset_rate_for_month(now.year, now.month, PRESET_LPR_HISTORY),
            "deposit_5y": preset_rate_for_month(now.year, now.month, PRESET_DEPOSIT_HISTORY),
            "bond_yield_10y": latest_gov,
        },
        "predictions": new_predictions,
        "validation_warnings": warnings,
    }
    save_json(PRESET_PRED_FILE, output)
    print(f"[preset-predictions] data/predictions.json 已更新（{len(new_predictions)} 季度，{len(warnings)} 条告警）")
    return True


def generate_derived_files() -> None:
    generate_life_discount_curves()
    generate_summary()
    generate_predictions()


def main():
    if "--derived-only" in sys.argv:
        print("Generating derived files from existing local data only")
        generate_derived_files()
        sys.exit(0)

    today_str = now_beijing().strftime("%Y-%m-%d")
    print("=" * 68)
    print("ChinaBond yield curve update: 9 curves x 2 measures")
    print(f"Beijing time: {datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 68)

    changed = update_all_datasets(today_str)
    generate_life_discount_curves()
    generate_preset_model_data()
    generate_summary()
    generate_predictions()

    changed_count = sum(1 for ok in changed.values() if ok)
    print("=" * 68)
    print(f"Datasets updated: {changed_count}/{len(ALL_DATASETS)}")
    print("=" * 68)
    sys.exit(0)


if __name__ == "__main__":
    main()
