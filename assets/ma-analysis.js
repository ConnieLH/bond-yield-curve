(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.YieldMA = api;
})(typeof window === 'undefined' ? this : window, function () {
    'use strict';

    const PRESETS = ['1', '60', '120', '250', '500', '750', '1000', '2500'];
    const COLORS = ['#1f4a7a', '#e67e22', '#16865d', '#8a58bd', '#cf4565', '#198eac'];
    const KEY_TERMS = ['1Y', '3Y', '5Y', '7Y', '10Y', '15Y', '20Y', '30Y', '40Y', '50Y'];

    // Keep the period as a decimal string: even a window larger than Number.MAX_SAFE_INTEGER
    // can be accepted and reported as insufficient without rounding or allocating a huge array.
    function normalizePeriod(value) {
        const text = String(value).trim();
        if (!/^\d+$/.test(text)) throw new Error('请输入大于等于 1 的整数');
        const period = text.replace(/^0+/, '');
        if (!period) throw new Error('请输入大于等于 1 的整数');
        return period;
    }

    function numericRate(value) {
        if (value === null || value === undefined || typeof value === 'boolean' || value === '') return null;
        if (typeof value !== 'number' && typeof value !== 'string') return null;
        if (typeof value === 'string' && !value.trim()) return null;
        const number = Number(value);
        return Number.isFinite(number) ? number : null;
    }

    function buildDataset(raw) {
        const dates = raw.dates;
        const terms = raw.terms;
        const rows = raw.rows;
        if (!Array.isArray(dates) || !dates.length || !Array.isArray(terms) || !terms.length ||
            !Array.isArray(rows) || dates.length !== rows.length) throw new Error('原始收益率数据格式不完整');
        if (new Set(terms).size !== terms.length || dates.some((d, i) =>
            !/^\d{4}-\d{2}-\d{2}$/.test(d) || (i > 0 && d <= dates[i - 1]))) {
            throw new Error('原始收益率的日期或期限格式错误');
        }
        const values = {}, sums = {}, counts = {};
        terms.forEach((term, column) => {
            values[term] = rows.map(row => numericRate(Array.isArray(row) ? row[column] : row?.[term]));
            sums[term] = [0];
            counts[term] = [0];
            values[term].forEach(value => {
                sums[term].push(sums[term][sums[term].length - 1] + (value ?? 0));
                counts[term].push(counts[term][counts[term].length - 1] + (value === null ? 0 : 1));
            });
        });
        return { dates: dates.slice(), terms: terms.slice(), dateIndex: new Map(dates.map((d, i) => [d, i])), values, sums, counts };
    }

    function exceedsCount(period, count) {
        const limit = String(count);
        return period.length > limit.length || (period.length === limit.length && period > limit);
    }

    function valueAt(dataset, date, term, period) {
        period = normalizePeriod(period);
        const empty = (status, message) => ({ value: null, status, message });
        if (!dataset) return empty('unavailable', '原始数据加载失败');
        if (!Object.prototype.hasOwnProperty.call(dataset.values, term)) return empty('term', term + ' 无数据');
        const index = dataset.dateIndex.get(date);
        if (index === undefined) return empty('date', '该日期无数据');
        if (exceedsCount(period, index + 1)) return empty('insufficient', '数据不足 ' + period + ' 条（仅有 ' + (index + 1) + ' 条）');
        const window = Number(period); // bounded by the real dataset size
        const start = index + 1 - window;
        const count = dataset.counts[term][index + 1] - dataset.counts[term][start];
        if (count !== window) return empty('missing', '窗口内数据缺失（有效 ' + count + '/' + period + ' 条）');
        const value = window === 1 ? dataset.values[term][index] :
            Number(((dataset.sums[term][index + 1] - dataset.sums[term][start]) / window).toFixed(8));
        return { value, status: 'ok', message: '可用' };
    }

    function dimensions(curves, datasets) {
        const selected = curves.map(curve => datasets[curve.bond]).filter(Boolean);
        const dates = [...new Set(selected.flatMap(data => data.dates))].sort();
        const terms = [...new Set(selected.flatMap(data => data.terms))]
            .filter(term => /^\d+(?:\.\d+)?Y$/.test(term)).sort((a, b) => parseFloat(a) - parseFloat(b));
        return { dates, terms };
    }

    function curveName(curve, index, bonds, kind) {
        return '曲线' + (index + 1) + ' · ' + bonds.find(b => b.key === curve.bond).label + '即期 · MA' + curve.period +
            (kind === 'time' ? ' · ' + curve.term : kind === 'curve' ? ' · ' + (curve.date || '日期无数据') : '');
    }

    function difference(a, b) {
        return a === null || b === null ? null : Number(((b - a) * 100).toFixed(6));
    }

    function exportRows(curves, datasets, bonds, dates, terms) {
        const header = ['日期', '期限'];
        curves.forEach((curve, index) => header.push(curveName(curve, index, bonds) + '(%)', '曲线' + (index + 1) + '状态'));
        curves.slice(1).forEach((curve, index) => header.push('曲线' + (index + 2) + '−曲线1(bp)'));
        const rows = [header];
        for (const date of dates) for (const term of terms) {
            const results = curves.map(curve => valueAt(datasets[curve.bond], date, term, curve.period));
            const row = [date, term];
            results.forEach(result => row.push(result.value, result.message));
            results.slice(1).forEach(result => row.push(difference(results[0].value, result.value)));
            rows.push(row);
        }
        return rows;
    }

    function resultsFor(kind, curves, datasets, coordinate) {
        return curves.map(curve => valueAt(datasets[curve.bond],
            kind === 'time' ? coordinate : curve.date,
            kind === 'time' ? curve.term : coordinate, curve.period));
    }

    function exportSelectedRows(curves, datasets, bonds, terms) {
        const header = ['期限'];
        curves.forEach((curve, index) => header.push(curveName(curve, index, bonds, 'curve') + '(%)', '曲线' + (index + 1) + '状态'));
        curves.slice(1).forEach((curve, index) => header.push('曲线' + (index + 2) + '−曲线1(bp)'));
        return [header, ...terms.map(term => {
            const results = resultsFor('curve', curves, datasets, term);
            const row = [term];
            results.forEach(result => row.push(result.value, result.message));
            results.slice(1).forEach(result => row.push(difference(results[0].value, result.value)));
            return row;
        })];
    }

    function createView(options) {
        const root = options.root, bonds = options.bonds, kind = options.kind;
        const prefix = kind === 'time' ? 'maTime' : 'maCurve';
        const panelLabel = kind === 'time' ? '时间序列' : '期限曲线';
        const datasets = {}, loads = {}, errors = {};
        let chart = null, nextId = 3, tableEndDate = null, revision = 0;
        let curves = [
            { id: 1, bond: 'gov_spot', period: '60', custom: false, term: '10Y', date: null },
            { id: 2, bond: 'rail_spot', period: '60', custom: false, term: '10Y', date: null }
        ];
        let available = { dates: [], terms: [] };
        const $ = id => root.querySelector('#' + id);
        const escape = value => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
        const colorAt = index => COLORS[index % COLORS.length];
        const chartId = kind === 'time' ? 'maTimeSeriesChart' : 'maCurveChart';
        const headerId = kind === 'time' ? 'maTimeSeriesHeader' : 'maCurveHeader';
        const bodyId = kind === 'time' ? 'maTimeSeriesBody' : 'maCurveBody';

        function populateSelectors() {
            available = dimensions(curves, datasets);
            curves.forEach(curve => {
                const data = datasets[curve.bond];
                if (!data) return;
                if (!data.terms.includes(curve.term)) curve.term = data.terms.includes('10Y') ? '10Y' : data.terms[0];
                if (!data.dates.includes(curve.date)) curve.date = data.dates[data.dates.length - 1];
            });
            if (kind === 'time') {
                if (!available.dates.includes(tableEndDate)) tableEndDate = available.dates[available.dates.length - 1];
                $('maTimeTableDateSelect').innerHTML = available.dates.slice().reverse().map(date =>
                    '<option' + (date === tableEndDate ? ' selected' : '') + '>' + date + '</option>').join('');
            } else {
                for (const id of ['maCurveFrom', 'maCurveTo']) {
                    $(id).min = available.dates[0] || '';
                    $(id).max = available.dates[available.dates.length - 1] || '';
                }
                if (!$('maCurveFrom').value) $('maCurveFrom').value = available.dates[0] || '';
                if (!$('maCurveTo').value) $('maCurveTo').value = available.dates[available.dates.length - 1] || '';
            }
        }

        function renderSettings() {
            $(prefix + 'Settings').innerHTML = curves.map((curve, index) => {
                const name = '曲线' + (index + 1), aria = panelLabel + ' ' + name + ' ';
                const id = prefix + '-' + curve.id;
                const data = datasets[curve.bond];
                const field = kind === 'time' ? 'term' : 'date';
                const coordinateLabel = kind === 'time' ? '期限' : '日期';
                const coordinates = data ? (kind === 'time' ? data.terms : data.dates.slice().reverse()) : [];
                return '<div class="ma-setting-row" data-curve-id="' + curve.id + '">' +
                    '<span class="ma-setting-name"><i style="background:' + colorAt(index) + '"></i>' + name + '</span>' +
                    '<span class="ma-setting-field"><label for="' + id + '-bond">债券</label><select id="' + id + '-bond" data-field="bond" aria-label="' + aria + '债券">' +
                    bonds.map(bond => '<option value="' + bond.key + '"' + (bond.key === curve.bond ? ' selected' : '') + '>' + bond.label + '</option>').join('') + '</select></span>' +
                    '<span class="ma-setting-field"><label for="' + id + '-period">移动平均</label><select id="' + id + '-period" data-field="period" aria-label="' + aria + '移动平均">' +
                    PRESETS.map(period => '<option value="' + period + '"' + (!curve.custom && period === curve.period ? ' selected' : '') + '>MA' + period + '</option>').join('') +
                    '<option value="custom"' + (curve.custom ? ' selected' : '') + '>自定义</option></select></span>' +
                    '<span class="ma-custom-window"' + (curve.custom ? '' : ' hidden') + '><input id="' + id + '-custom" data-field="custom" type="text" inputmode="numeric" aria-label="' + aria + '自定义天数" value="' + curve.period + '"><button type="button" data-action="apply">应用</button></span>' +
                    '<span class="ma-setting-field"><label for="' + id + '-coordinate">' + coordinateLabel + '</label><select id="' + id + '-coordinate" data-field="' + field + '" aria-label="' + aria + coordinateLabel + '"' + (data ? '' : ' disabled') + '>' +
                    (coordinates.length ? coordinates.map(value => '<option' + (value === curve[field] ? ' selected' : '') + '>' + value + '</option>').join('') : '<option>正在加载…</option>') + '</select></span>' +
                    '<button type="button" class="ma-remove" data-action="remove" aria-label="' + panelLabel + ' 删除' + name + '"' + (curves.length === 1 ? ' disabled' : '') + '>删除</button>' +
                    '<span class="ma-source-summary"></span><span class="ma-input-error" role="alert"></span></div>';
            }).join('');
        }

        function renderStatus() {
            curves.forEach(curve => {
                const row = root.querySelector('[data-curve-id="' + curve.id + '"]'), data = datasets[curve.bond];
                row.querySelector('.ma-source-summary').textContent = data ?
                    data.dates[0] + '～' + data.dates[data.dates.length - 1] + ' · ' + data.dates.length + '条 · ' + data.terms[0] + '～' + data.terms[data.terms.length - 1] +
                    (curve.bond === 'local_gov_spot' ? ' · 来源脚本由到期收益率推导即期' : '') : errors[curve.bond] || '正在加载原始数据…';
            });
            $(prefix + 'Status').textContent = curves.map((curve, index) => {
                const data = datasets[curve.bond];
                const result = valueAt(data, kind === 'time' ? tableEndDate : curve.date,
                    kind === 'time' ? curve.term : data?.terms[0], curve.period);
                return result.status === 'ok' ? '' : '曲线' + (index + 1) + '：' + (errors[curve.bond] || result.message);
            }).filter(Boolean).join('；');
        }

        function renderTable() {
            const labels = kind === 'time' ? available.dates.filter(date => date <= tableEndDate).slice(-10) : KEY_TERMS.filter(term => available.terms.includes(term));
            const headings = [kind === 'time' ? '日期' : '期限', ...curves.map((curve, index) => curveName(curve, index, bonds, kind) + '(%)'),
                ...curves.slice(1).map((curve, index) => '曲线' + (index + 2) + '−曲线1(bp)')];
            $(headerId).innerHTML = '<tr>' + headings.map(text => '<th>' + escape(text) + '</th>').join('') + '</tr>';
            $(bodyId).innerHTML = labels.map(label => {
                const results = resultsFor(kind, curves, datasets, label);
                const cells = results.map(result => '<td title="' + escape(result.message) + '">' + (result.value === null ? '<span class="ma-missing">' + escape(result.message) + '</span>' : result.value.toFixed(4)) + '</td>');
                const diffs = results.slice(1).map(result => {
                    const delta = difference(results[0].value, result.value);
                    return '<td class="' + (delta === null ? '' : delta > 0 ? 'ma-diff-positive' : 'ma-diff-negative') + '">' + (delta === null ? '—' : (delta > 0 ? '+' : '') + delta.toFixed(1)) + '</td>';
                });
                return '<tr><td><strong>' + escape(label) + '</strong></td>' + cells.join('') + diffs.join('') + '</tr>';
            }).join('');
        }

        function renderChart() {
            const container = $(chartId);
            if (!container.getBoundingClientRect().width) return;
            if (!chart) chart = options.echarts.init(container);
            const timeDates = available.dates.filter(date => date <= tableEndDate);
            const series = curves.map((curve, index) => {
                const data = datasets[curve.bond];
                const values = kind === 'time' ? timeDates.map(date => valueAt(data, date, curve.term, curve.period).value) :
                    available.terms.map(term => [parseFloat(term), valueAt(data, curve.date, term, curve.period).value]);
                return { name: curveName(curve, index, bonds, kind), type: 'line', data: values, connectNulls: false, smooth: false,
                    showSymbol: kind === 'curve', symbolSize: 4, lineStyle: { width: 2.2, color: colorAt(index) }, itemStyle: { color: colorAt(index) } };
            });
            chart.setOption(options.chartOption({
                tooltip: options.tooltip({ trigger: 'axis', formatter: params => {
                    const heading = params[0]?.axisValueLabel || '';
                    return escape(heading) + (kind === 'curve' ? ' 年' : '') + '<br>' + params.map(item => {
                        const value = Array.isArray(item.value) ? item.value[1] : item.value;
                        return item.marker + ' ' + escape(item.seriesName) + '：' +
                            (value === null || value === undefined ? '无数据' : Number(value).toFixed(4) + '%');
                    }).join('<br>');
                } }),
                legend: { type: 'scroll', top: 4, textStyle: { fontSize: 11 } },
                grid: { left: 60, right: 20, top: 60, bottom: kind === 'time' ? 62 : 48 },
                xAxis: kind === 'time' ? { type: 'category', data: timeDates, name: '日期', nameLocation: 'center', nameGap: 46,
                    axisLabel: { rotate: 30, fontSize: 10, interval: Math.max(1, Math.floor(timeDates.length / 8)) } } :
                    { type: 'value', name: '期限（年）', nameLocation: 'center', nameGap: 28, min: 1, max: parseFloat(available.terms[available.terms.length - 1]) || 50 },
                yAxis: { type: 'value', scale: true, name: '利率（%）', axisLabel: { formatter: value => value.toFixed(2) + '%' } }, series
            }), true);
        }

        function render() {
            populateSelectors(); renderSettings(); renderStatus(); renderTable(); renderChart();
        }

        async function refresh() {
            const current = ++revision;
            if (kind === 'curve') $('maCurveDownloadBtn').disabled = true;
            populateSelectors(); renderSettings(); renderStatus();
            await Promise.all([...new Set(curves.map(curve => curve.bond))].map(key => {
                if (!loads[key]) loads[key] = options.load(bonds.find(bond => bond.key === key)).then(raw => {
                    datasets[key] = buildDataset(raw);
                }).catch(() => { errors[key] = '原始数据加载失败，请检查本地数据文件'; });
                return loads[key];
            }));
            if (current === revision) {
                render();
                if (kind === 'curve') $('maCurveDownloadBtn').disabled = false;
            }
        }

        function applyCustom(row, curve) {
            try {
                curve.period = normalizePeriod(row.querySelector('[data-field="custom"]').value);
                curve.custom = true; render();
            } catch (failure) { row.querySelector('.ma-input-error').textContent = failure.message; }
        }

        function download() {
            $('maExportStatus').textContent = '';
            if (!available.dates.length) { $('maExportStatus').textContent = '暂无数据可导出'; return; }
            const mode = $('maCurveExportRange').value;
            let dates = mode === 'single' ? [...new Set(curves.map(curve => curve.date).filter(Boolean))].sort() : available.dates;
            if (mode === 'custom') {
                const from = $('maCurveFrom').value, to = $('maCurveTo').value;
                if (!from || !to || from > to) { $('maExportStatus').textContent = '请填写有效的起止日期，起始日期不能晚于结束日期'; return; }
                dates = dates.filter(date => date >= from && date <= to);
            }
            if (!dates.length) { $('maExportStatus').textContent = '所选区间内没有可用数据'; return; }
            const rows = mode === 'single' ? exportSelectedRows(curves, datasets, bonds, available.terms) : exportRows(curves, datasets, bonds, dates, available.terms);
            const XLSX = options.xlsx, book = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet(rows), 'MA期限曲线');
            const details = [['口径', '各债券原始即期收益率；MAx 为截至该日最近 x 条记录的算术平均；必须具备完整窗口'],
                ['导出范围', mode === 'single' ? '各曲线分别使用所选日期，日期见列名' : dates[0] + '～' + dates[dates.length - 1] + '；各曲线均按导出日期逐日计算'],
                ['缺失处理', '数据不足、该日无数据或期限缺失时留空，原因见状态列；不填充、不外推'],
                ['差值', '曲线N−曲线1；按列名所示债券、MA及日期比较，单位 bp'],
                ...curves.map((curve, index) => [curveName(curve, index, bonds, mode === 'single' ? 'curve' : undefined), bonds.find(bond => bond.key === curve.bond).file + (curve.bond === 'local_gov_spot' ? '；来源脚本由到期收益率推导即期' : '')])];
            XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet(details), '说明');
            XLSX.writeFile(book, '即期收益率_MA期限曲线_' + (mode === 'single' ? '所选日期_' : '') + dates[0] + (dates.length > 1 ? '_' + dates[dates.length - 1] : '') + '.xlsx');
            $('maExportStatus').textContent = '已导出 ' + (mode === 'single' ? '各曲线所选日期' : dates.length + ' 个日期') + '、' + curves.length + ' 条曲线';
        }

        root.addEventListener('change', event => {
            const target = event.target, row = target.closest('[data-curve-id]');
            if (row) {
                const curve = curves.find(item => item.id === Number(row.dataset.curveId));
                if (target.dataset.field === 'bond') { curve.bond = target.value; refresh(); }
                if (target.dataset.field === 'period') {
                    curve.custom = target.value === 'custom';
                    if (!curve.custom) curve.period = target.value;
                    render();
                }
                if (target.dataset.field === 'term' || target.dataset.field === 'date') {
                    curve[target.dataset.field] = target.value; render();
                }
            } else if (target.id === 'maCurveExportRange') {
                $('maCurveRangePickers').hidden = target.value !== 'custom';
                $('maExportStatus').textContent = '';
            } else if (target.id === 'maTimeTableDateSelect') { tableEndDate = target.value; render(); }
        });
        root.addEventListener('click', event => {
            const button = event.target.closest('button');
            if (!button) return;
            if (button.id === prefix + 'AddCurve') {
                curves.push({ id: nextId++, bond: 'gov_spot', period: '60', custom: false, term: '10Y', date: null }); refresh();
            } else if (button.id === 'maCurveDownloadBtn') download();
            else {
                const row = button.closest('[data-curve-id]');
                if (!row) return;
                const curve = curves.find(item => item.id === Number(row.dataset.curveId));
                if (button.dataset.action === 'apply') applyCustom(row, curve);
                if (button.dataset.action === 'remove' && curves.length > 1) {
                    curves = curves.filter(item => item !== curve); refresh();
                }
            }
        });
        root.addEventListener('keydown', event => {
            if (event.key === 'Enter' && event.target.dataset.field === 'custom') {
                event.preventDefault();
                const row = event.target.closest('[data-curve-id]');
                applyCustom(row, curves.find(item => item.id === Number(row.dataset.curveId)));
            }
        });
        refresh();
        return { resize() {
            if (!root.getBoundingClientRect().width) return;
            if (chart) chart.resize(); else renderChart();
        } };
    }

    return { normalizePeriod, buildDataset, valueAt, dimensions, curveName, difference, exportRows, resultsFor, exportSelectedRows, createView };
});
