// plugins/metadata/stock_ticker/dashboard.js
// 코어가 new Function('pluginId', 'shadowRoot', 'items', <이 파일 내용>) 형태로 실행합니다.
// 즉 이 파일은 함수 "본문"이며, pluginId/shadowRoot/items는 이미 인자로 바인딩되어 들어옵니다.

function stockTickerEscapeHtml(str) {
    return String(str == null ? '' : str).replace(/[&<>"']/g, function (ch) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
    });
}

// series(종가 배열)를 0~width/height 좌표계의 SVG path 문자열로 변환
function stockTickerBuildPaths(series, width, height, padding) {
    if (!series || series.length < 2) return null;

    var min = Math.min.apply(null, series);
    var max = Math.max.apply(null, series);
    var range = (max - min) || 1;
    var innerW = width - padding * 2;
    var innerH = height - padding * 2;
    var stepX = innerW / (series.length - 1);

    var points = series.map(function (v, i) {
        var x = padding + i * stepX;
        var y = padding + innerH * (1 - (v - min) / range);
        return [x, y];
    });

    var linePath = points
        .map(function (p, i) {
            return (i === 0 ? 'M' : 'L') + p[0].toFixed(2) + ',' + p[1].toFixed(2);
        })
        .join(' ');

    var lastX = points[points.length - 1][0].toFixed(2);
    var firstX = points[0][0].toFixed(2);
    var baseline = (height - padding).toFixed(2);
    var areaPath = linePath + ' L' + lastX + ',' + baseline + ' L' + firstX + ',' + baseline + ' Z';

    return { linePath: linePath, areaPath: areaPath };
}

// 종목 1개의 추이 그래프(스파크라인) SVG 마크업 생성
function stockTickerRenderChart(series) {
    var width = 120;
    var height = 34;
    var padding = 3;

    var paths = stockTickerBuildPaths(series, width, height, padding);
    if (!paths) {
        return '<span style="font-size:0.68rem;color:var(--app-text-muted,#94a3b8);">추이 데이터 없음</span>';
    }

    var first = series[0];
    var last = series[series.length - 1];
    var isUp = last >= first;
    var strokeColor = isUp ? '#22c55e' : '#ef4444';
    var fillColor = isUp ? 'rgba(34,197,94,0.16)' : 'rgba(239,68,68,0.16)';

    return (
        '<svg viewBox="0 0 ' + width + ' ' + height + '" preserveAspectRatio="none">' +
        '<path d="' + paths.areaPath + '" fill="' + fillColor + '" stroke="none"></path>' +
        '<path d="' + paths.linePath + '" fill="none" stroke="' + strokeColor + '" ' +
        'stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"></path>' +
        '</svg>'
    );
}

// 종목 카드 1개(심볼/이름 + 그래프 + 현재가/등락률) 마크업 생성
function stockTickerRenderItem(item) {
    var change = typeof item.change_pct === 'number' ? item.change_pct : 0;
    var changeClass = change > 0 ? 'up' : change < 0 ? 'down' : 'flat';
    var changeSign = change > 0 ? '+' : '';
    var priceText = (item.price != null ? item.price : '-') + (item.currency ? ' ' + item.currency : '');

    return (
        '<div class="stock-ticker-item" data-symbol="' + stockTickerEscapeHtml(item.symbol || '') + '">' +
        '<div class="stock-ticker-info">' +
        '<span class="stock-ticker-symbol">' + stockTickerEscapeHtml(item.symbol || '') + '</span>' +
        '<span class="stock-ticker-name">' + stockTickerEscapeHtml(item.name || '') + '</span>' +
        '</div>' +
        '<div class="stock-ticker-chart">' + stockTickerRenderChart(item.series || []) + '</div>' +
        '<div class="stock-ticker-price-block">' +
        '<span class="stock-ticker-price">' + stockTickerEscapeHtml(priceText) + '</span>' +
        '<span class="stock-ticker-change ' + changeClass + '">' + changeSign + change + '%</span>' +
        '</div>' +
        '</div>'
    );
}

// ---- 실제 실행부 ----
var stockTickerListEl = shadowRoot.querySelector('#stock-ticker-list');

if (stockTickerListEl) {
    if (!items || items.length === 0) {
        stockTickerListEl.innerHTML =
            '<div class="stock-ticker-empty">표시할 종목이 없습니다. 플러그인 설정에서 종목 코드를 확인하세요.</div>';
    } else {
        stockTickerListEl.innerHTML = items.map(stockTickerRenderItem).join('');
    }
}
