const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const MA = require('../assets/ma-analysis.js');

function fixture(rows = [[2, 3], [4, 5], [8, 9]]) {
    return MA.buildDataset({ dates: ['2026-09-28', '2026-09-29', '2026-09-30'], terms: ['1Y', '10Y'], rows });
}

test('MA1 uses the actual spot rate and larger windows average raw rates directly', () => {
    const data = fixture();
    assert.equal(MA.valueAt(data, '2026-09-30', '1Y', 1).value, 8);
    assert.equal(MA.valueAt(data, '2026-09-30', '1Y', 2).value, 6);
    assert.equal(MA.valueAt(data, '2026-09-30', '10Y', 3).value, 5.66666667);
});

test('full windows are mandatory and unavailable dates are never projected or filled', () => {
    const data = fixture();
    const result = MA.valueAt(data, '2026-09-29', '1Y', 3);
    assert.equal(result.value, null);
    assert.equal(result.status, 'insufficient');
    assert.match(result.message, /数据不足 3 条/);
    assert.equal(MA.valueAt(data, '2026-10-01', '1Y', 1).status, 'date');
    assert.equal(MA.valueAt(data, '2026-09-30', '50Y', 1).status, 'term');
});

test('missing observations and blank values do not silently shrink the averaging window', () => {
    const data = fixture([[2, 3], [null, ''], [8, 9]]);
    assert.equal(MA.valueAt(data, '2026-09-30', '1Y', 2).status, 'missing');
    assert.equal(MA.valueAt(data, '2026-09-30', '10Y', 3).status, 'missing');
    assert.equal(MA.valueAt(data, '2026-09-29', '10Y', 1).value, null);
    assert.equal(MA.valueAt(data, '2026-09-30', '1Y', 1).value, 8);
});

test('custom windows accept MA1 and arbitrary positive integers without a 5000 cap or rounding', () => {
    assert.equal(MA.normalizePeriod('0001'), '1');
    assert.equal(MA.normalizePeriod('6000'), '6000');
    const huge = '999999999999999999999999999999999999999999';
    assert.equal(MA.normalizePeriod(huge), huge);
    const result = MA.valueAt(fixture(), '2026-09-30', '1Y', huge);
    assert.equal(result.status, 'insufficient');
    assert.ok(result.message.includes(huge));
    for (const value of ['0', '-1', '1.5', '1e3', '', 'NaN']) assert.throws(() => MA.normalizePeriod(value));
});

test('independent curves can select the same bond with different windows', () => {
    const data = fixture();
    const curves = [{ bond: 'gov_spot', period: '1' }, { bond: 'gov_spot', period: '2' }, { bond: 'rail_spot', period: '3' }];
    const datasets = { gov_spot: data, rail_spot: fixture([[3, 4], [5, 6], [9, 10]]) };
    const bonds = [{ key: 'gov_spot', label: '国债' }, { key: 'rail_spot', label: '铁道债' }];
    const rows = MA.exportRows(curves, datasets, bonds, ['2026-09-30'], ['1Y']);
    assert.match(rows[0][2], /曲线1 · 国债即期 · MA1/);
    assert.match(rows[0][4], /曲线2 · 国债即期 · MA2/);
    assert.match(rows[0][6], /曲线3 · 铁道债即期 · MA3/);
    assert.equal(rows[1][2], 8);
    assert.equal(rows[1][4], 6);
    assert.equal(rows[1][6], 5.66666667);
    assert.equal(rows[1][8], -200);
    assert.equal(rows[1][9], -233.333333);
});

test('date-filtered export still uses earlier history and records missing values truthfully', () => {
    const datasets = { gov_spot: fixture(), exim_spot: MA.buildDataset({ dates: ['2026-09-30'], terms: ['1Y'], rows: [[3]] }) };
    const curves = [{ bond: 'gov_spot', period: '2' }, { bond: 'exim_spot', period: '2500' }];
    const bonds = [{ key: 'gov_spot', label: '国债' }, { key: 'exim_spot', label: '进出口行债' }];
    const rows = MA.exportRows(curves, datasets, bonds, ['2026-09-30'], ['1Y', '10Y']);
    assert.equal(rows.length, 3);
    assert.equal(rows[1][2], 6); // includes 2026-09-29 even though it is outside the export interval
    assert.equal(rows[1][4], null);
    assert.match(rows[1][5], /数据不足 2500 条/);
    assert.equal(rows[1][6], null);
    assert.equal(rows[2][4], null);
    assert.equal(rows[2][5], '10Y 无数据');
});

test('dates and terms use real coverage of the selected bonds rather than fabricated 50Y data', () => {
    const a = MA.buildDataset({ dates: ['2026-09-29', '2026-09-30'], terms: ['1Y', '50Y'], rows: [[1, 2], [3, 4]] });
    const b = MA.buildDataset({ dates: ['2026-09-30'], terms: ['1Y', '20Y'], rows: [[5, 6]] });
    const datasets = { gov_spot: a, exim_spot: b };
    assert.deepEqual(MA.dimensions([{ bond: 'exim_spot' }], datasets), { dates: ['2026-09-30'], terms: ['1Y', '20Y'] });
    assert.deepEqual(MA.dimensions([{ bond: 'gov_spot' }, { bond: 'exim_spot' }], datasets).terms, ['1Y', '20Y', '50Y']);
    assert.equal(MA.valueAt(b, '2026-09-30', '50Y', 1).value, null);
});

test('all nine local datasets load and real MA values match a direct arithmetic reference', () => {
    const files = ['data.json', 'data_cdb.json', 'data_rail_spot.json', 'data_corp_aaa_spot.json', 'data_corp_aa_spot.json',
        'data_corp_a_spot.json', 'data_exim_spot.json', 'data_adbc_spot.json', 'data_local_gov_spot.json'];
    for (const file of files) {
        const raw = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', file), 'utf8'));
        const data = MA.buildDataset(raw), date = raw.dates[raw.dates.length - 1], index = raw.terms.indexOf('10Y');
        for (const period of [1, 60, 120, 250, 500, 750, 1000, 2500]) {
            const actual = MA.valueAt(data, date, '10Y', period);
            if (raw.rows.length < period) assert.equal(actual.status, 'insufficient');
            else {
                const expected = raw.rows.slice(-period).reduce((sum, row) => sum + row[index], 0) / period;
                assert.ok(Math.abs(actual.value - expected) < 1e-8, file + ' MA' + period);
            }
        }
    }
});

test('time series uses each curve own maturity and window on the same observation date', () => {
    const curves = [{ bond: 'gov', period: '1', term: '1Y' }, { bond: 'gov', period: '2', term: '10Y' }];
    const results = MA.resultsFor('time', curves, { gov: fixture() }, '2026-09-30');
    assert.deepEqual(results.map(result => result.value), [8, 7]);
    assert.equal(MA.resultsFor('time', [{ bond: 'gov', period: '1', term: '50Y' }], { gov: fixture() }, '2026-09-30')[0].status, 'term');
});

test('term curve and selected export use each curve own date, including missing dates', () => {
    const curves = [{ bond: 'gov', period: '1', date: '2026-09-29' }, { bond: 'gov', period: '2', date: '2026-09-30' }, { bond: 'gov', period: '1', date: '2026-10-01' }];
    const datasets = { gov: fixture() }, bonds = [{ key: 'gov', label: '国债' }];
    assert.deepEqual(MA.resultsFor('curve', curves, datasets, '1Y').map(result => result.value), [4, 6, null]);
    const rows = MA.exportSelectedRows(curves, datasets, bonds, ['1Y', '10Y']);
    assert.match(rows[0][1], /2026-09-29/);
    assert.match(rows[0][3], /2026-09-30/);
    assert.deepEqual(rows[1], ['1Y', 4, '可用', 6, '可用', null, '该日期无数据', 200, null]);
    assert.deepEqual(rows[2], ['10Y', 5, '可用', 7, '可用', null, '该日期无数据', 200, null]);
});
