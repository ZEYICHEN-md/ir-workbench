// Bilingual UI strings for travel dashboard
// Insights content: dashboard/travel/insights.js (from travel-insights.json)
const I18N = {
  zh: {
    pageTitle: '2026年旅游行业数据看板',
    title: '2026年旅游行业数据看板',
    irBrand: 'TRIP.COM GROUP•INVESTOR RELATIONS',
    irLogo: '携程',
    metaUpdate: '数据更新：{date}',
    metaDetail: '最新数据周：{week} · {compareBase}',
    metaSources: '来源：{sources}',
    downloadAll: '下载全部图表',
    downloadImg: '下载图片',
    tabWeekly: '周度趋势',
    tabMonthly: '月度趋势',
    tabQuarterly: '季度总览',
    weekYoY: '周同比',
    kpiOcc: '国内酒店入住率（最新周）',
    kpiAdr: '国内酒店 ADR（最新周）',
    kpiRevpar: '国内酒店 RevPAR（最新周）',
    kpiPax: '机票客运量（最新周）',
    kpiTicket: '机票票价（最新周）',
    kpiFlight: '客运航班量（最新周）',
    chartWeeklyHotel: '国内酒店周度指标（RevPAR / ADR / 入住率 同比）',
    chartWeeklyAviation: '航空周度指标（客运量 / 票价 / 航班量 同比）',
    chartMonthlyHotel: '国内酒店月度指标（RevPAR / ADR / 入住率 同比）',
    chartMonthlyDomAv: '国内航空客运量月度同比（民航局 vs 三大航）',
    chartMonthlyRailway: '铁路客运量月度同比',
    chartMonthlyIntl: '国际航空客运量 & 运力月度同比',
    chartQOverview: 'Q1 各板块同比表现总览',
    chartQTrend: 'Q1 → Q2 月度趋势变化（核心指标同比）',
    chartQCompare: 'Q1 vs Q2 对比（Q2 为 4–6 月各月同比平均）',
    sectorHotel: '国内酒店',
    sectorAviation: '航空',
    sectorDomestic: '国内航空',
    sectorIntl: '国际航空',
    strSource: 'STR',
    legendToggleHint: '显示 / 隐藏该指标',
    seriesOcc: '入住率',
    seriesAdr: 'ADR',
    seriesRevpar: 'RevPAR',
    seriesPax: '机票客运量',
    seriesTicket: '票价',
    seriesFlight: '客运航班量',
    markYtdAvgPax: '客运量 YTD Avg.',
    markYtdAvgRevpar: 'RevPAR YTD Avg.',
    seriesCaac: '民航局',
    seriesBig3: '三大航',
    seriesRailway: '铁路客运量',
    seriesIntlCaac: '国际客运量（民航局）',
    seriesIntlBig3: '国际客运量（三大航）',
    seriesCapacity: '国际航班运力(vs2019)',
    seriesHotelRev: '国内酒店 RevPAR',
    seriesDomAv: '国内航空客运量',
    yoyGrowth: '同比增速',
    insightsTitle: '数据洞察与结论',
    insightsScopeWeekly: '时间范围：周度同比（最新有数周 {latest}）',
    insightsScopeMonthly: '时间范围：月度同比（有数月份至 {latest}）',
    insightsScopeQuarterly: '时间范围：季度汇总（各月同比算术平均）',
    insightsStale: '本粒度洞察可能已过期（指标已更新，洞察尚未按新数据确认）',
    insightsEmpty: '本粒度暂无洞察',
    footer: '数据来源：STR、民航局、三大航、国铁、航班管家、飞常准',
    prevMonth: '前月',
    vs2019: '航班管家数据',
    crossBorder: '出入境同比',
    railSource: '国铁数据',
    tagHighlight: '亮点',
    tagRisk: '风险',
    tagOutlook: '展望',
    langBtn: 'EN',
    months: ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'],
  },
  en: {
    pageTitle: '2026 Travel Industry Dashboard',
    title: '2026 Travel Industry Dashboard',
    irBrand: 'TRIP.COM GROUP•INVESTOR RELATIONS',
    irLogo: 'Trip',
    metaUpdate: 'Data as of: {date}',
    metaDetail: 'Latest week: {week} · {compareBase}',
    metaSources: 'Sources: {sources}',
    downloadAll: 'Download all charts',
    downloadImg: 'Download',
    tabWeekly: 'Weekly',
    tabMonthly: 'Monthly',
    tabQuarterly: 'Quarterly',
    weekYoY: 'WoW YoY',
    kpiOcc: 'Domestic hotel occupancy (latest week)',
    kpiAdr: 'Domestic hotel ADR (latest week)',
    kpiRevpar: 'Domestic hotel RevPAR (latest week)',
    kpiPax: 'Air passengers (latest week)',
    kpiTicket: 'Airfares (latest week)',
    kpiFlight: 'Passenger flights (latest week)',
    chartWeeklyHotel: 'Weekly domestic hotel metrics (RevPAR / ADR / Occupancy YoY)',
    chartWeeklyAviation: 'Weekly aviation metrics (Pax / Fare / Flights YoY)',
    chartMonthlyHotel: 'Monthly domestic hotel metrics (RevPAR / ADR / Occupancy YoY)',
    chartMonthlyDomAv: 'Domestic air pax monthly YoY (CAAC vs Big3)',
    chartMonthlyRailway: 'Railway pax monthly YoY',
    chartMonthlyIntl: 'International air pax & capacity monthly YoY',
    chartQOverview: 'Q1 sector YoY overview',
    chartQTrend: 'Q1 → Q2 monthly trend (core metrics YoY)',
    chartQCompare: 'Q1 vs Q2 (Q2 = Apr–Jun monthly YoY average)',
    sectorHotel: 'Domestic hotel',
    sectorAviation: 'Aviation',
    sectorDomestic: 'Domestic aviation',
    sectorIntl: 'International aviation',
    strSource: 'STR',
    legendToggleHint: 'Show / hide this series',
    seriesOcc: 'Occupancy',
    seriesAdr: 'ADR',
    seriesRevpar: 'RevPAR',
    seriesPax: 'Air passengers',
    seriesTicket: 'Airfare',
    seriesFlight: 'Passenger flights',
    markYtdAvgPax: 'Pax YTD Avg.',
    markYtdAvgRevpar: 'RevPAR YTD Avg.',
    seriesCaac: 'CAAC',
    seriesBig3: 'Big3',
    seriesRailway: 'Railway pax',
    seriesIntlCaac: 'Intl pax (CAAC)',
    seriesIntlBig3: 'Intl pax (Big3)',
    seriesCapacity: 'Intl capacity (vs 2019)',
    seriesHotelRev: 'Domestic hotel RevPAR',
    seriesDomAv: 'Domestic air pax',
    yoyGrowth: 'YoY growth',
    insightsTitle: 'Insights',
    insightsScopeWeekly: 'Coverage: weekly YoY (latest week with data: {latest})',
    insightsScopeMonthly: 'Coverage: monthly YoY (through {latest})',
    insightsScopeQuarterly: 'Coverage: quarterly aggregates (arithmetic mean of monthly YoY)',
    insightsStale: 'Insights for this period may be stale (metrics updated; insights not re-confirmed)',
    insightsEmpty: 'No insights for this period yet',
    footer: 'Sources: STR, CAAC, Big3, China Railway, VariFlight, VeryZhun',
    prevMonth: 'Prev',
    vs2019: 'VariFlight',
    crossBorder: 'Cross-border YoY',
    railSource: 'China Railway',
    tagHighlight: 'Highlight',
    tagRisk: 'Risk',
    tagOutlook: 'Outlook',
    langBtn: '中文',
    months: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
  },
};

const LANG_KEY = 'travel_dashboard_lang';
let currentLang = localStorage.getItem(LANG_KEY) || 'zh';
let currentView = 'weekly';

function t(key) {
  const pack = I18N[currentLang] || I18N.zh;
  return pack[key] != null ? pack[key] : (I18N.zh[key] != null ? I18N.zh[key] : key);
}

function sectorOverviewTitle(scopeLabel) {
  return currentLang === 'zh'
    ? scopeLabel + ' 各板块同比表现总览'
    : scopeLabel + ' sector YoY overview';
}

function monthLabel(raw) {
  const m = String(raw).match(/^(\d{1,2})月$/);
  if (!m) return raw;
  const idx = parseInt(m[1], 10) - 1;
  const months = t('months');
  return months[idx] || raw;
}

function localizeMonths(arr) {
  return arr.map(monthLabel);
}

function fmtPct(v) {
  if (v == null || Number.isNaN(v)) return '—';
  const sign = v >= 0 ? '+' : '';
  return sign + (v * 100).toFixed(1) + '%';
}

function setLang(lang) {
  currentLang = lang === 'en' ? 'en' : 'zh';
  localStorage.setItem(LANG_KEY, currentLang);
  document.documentElement.lang = currentLang === 'zh' ? 'zh-CN' : 'en';
  applyStaticI18n();
  if (typeof initAll === 'function') initAll();
}

function toggleLang() {
  setLang(currentLang === 'zh' ? 'en' : 'zh');
}

function tagTone(tag) {
  if (tag === 'highlight') return 'positive';
  if (tag === 'risk') return 'negative';
  if (tag === 'outlook') return 'neutral';
  return 'default';
}

function tagText(tag) {
  const map = {
    highlight: 'tagHighlight',
    risk: 'tagRisk',
    outlook: 'tagOutlook',
  };
  return t(map[tag] || 'tagRisk');
}

function insightsForView(view) {
  const period = view || currentView || 'weekly';
  if (typeof INSIGHTS === 'undefined' || !INSIGHTS[period]) return [];
  const block = INSIGHTS[period];
  const items = block[currentLang] || block.zh || [];
  return Array.isArray(items) ? items : [];
}

function insightsStaleForView(view) {
  const period = view || currentView || 'weekly';
  if (typeof INSIGHTS === 'undefined' || !INSIGHTS.meta || !INSIGHTS.meta.stale) return false;
  return !!INSIGHTS.meta.stale[period];
}

function lastNonNullIndex(series) {
  if (!Array.isArray(series)) return -1;
  for (let i = series.length - 1; i >= 0; i--) {
    if (series[i] != null && !Number.isNaN(series[i])) return i;
  }
  return -1;
}

function latestWeeklyLabel() {
  if (typeof DATA === 'undefined' || !DATA.weekly) return '—';
  const idx = lastNonNullIndex(DATA.weekly.hotelRevPAR);
  if (idx < 0) return '—';
  return DATA.weekly.weeks[idx] || '—';
}

function latestMonthlyLabel() {
  if (typeof DATA === 'undefined' || !DATA.monthly) return '—';
  const candidates = [
    DATA.monthly.railway,
    DATA.monthly.hotelRevPAR,
    DATA.monthly.domAviationCAAC,
  ];
  let idx = -1;
  candidates.forEach(s => { idx = Math.max(idx, lastNonNullIndex(s)); });
  if (idx < 0) return '—';
  return monthLabel(DATA.monthly.months[idx] || '—');
}

function insightsScopeText(view) {
  const period = view || currentView || 'weekly';
  if (period === 'weekly') {
    return t('insightsScopeWeekly').replace('{latest}', latestWeeklyLabel());
  }
  if (period === 'monthly') {
    return t('insightsScopeMonthly').replace('{latest}', latestMonthlyLabel());
  }
  return t('insightsScopeQuarterly');
}

function renderInsights() {
  const root = document.getElementById('insights-body');
  const staleEl = document.getElementById('insights-stale');
  const scopeEl = document.getElementById('insights-scope');
  if (!root) return;

  if (scopeEl) scopeEl.textContent = insightsScopeText(currentView);

  if (staleEl) {
    const stale = insightsStaleForView(currentView);
    staleEl.hidden = !stale;
    staleEl.textContent = stale ? t('insightsStale') : '';
  }

  const items = insightsForView(currentView);
  const order = ['highlight', 'risk', 'outlook'];
  const groups = {};
  items.forEach(it => {
    if (!order.includes(it.tag)) return;
    if (!groups[it.tag]) groups[it.tag] = [];
    if (groups[it.tag].length < 2) groups[it.tag].push(it);
  });

  const sections = order.filter(tag => groups[tag] && groups[tag].length);
  if (!sections.length) {
    root.innerHTML = `<div class="insights-empty">${t('insightsEmpty')}</div>`;
    return;
  }

  root.innerHTML = sections.map(tag => {
    const tone = tagTone(tag);
    const points = groups[tag].map(it => `
      <div class="insight-point">
        <div class="insight-point-title">${it.title}</div>
        <div class="insight-point-body">${it.body}</div>
      </div>`).join('');
    return `<div class="insight-group insight-group--${tone}">
      <div class="insight-group-label">${tagText(tag)}</div>
      <div class="insight-points">${points}</div>
    </div>`;
  }).join('');
}

function formatMetaDate(iso) {
  if (!iso) return '—';
  const parts = String(iso).split('-');
  if (parts.length !== 3) return iso;
  return `${parts[0]}/${parts[1]}/${parts[2]}`;
}

function latestDataWeek() {
  if (typeof DATA === 'undefined' || !DATA.weekly || !DATA.weekly.weeks || !DATA.weekly.weeks.length) return '—';
  return DATA.weekly.weeks[DATA.weekly.weeks.length - 1];
}

function fillTemplate(str, vars) {
  return String(str).replace(/\{(\w+)\}/g, (_, k) => (vars[k] != null ? vars[k] : ''));
}

function applyHeroMeta() {
  const meta = (typeof DATA !== 'undefined' && DATA && DATA.meta) ? DATA.meta : {};
  const vars = {
    date: formatMetaDate(meta.dataUpdate),
    week: latestDataWeek(),
    compareBase: meta.compareBase || (currentLang === 'zh' ? '同比2025年' : 'YoY vs 2025'),
    sources: meta.dataSource || '',
  };
  const updateEl = document.getElementById('i18n-meta-update');
  const detailEl = document.getElementById('i18n-meta-detail');
  const sourcesEl = document.getElementById('i18n-meta-sources');
  if (updateEl) updateEl.textContent = fillTemplate(t('metaUpdate'), vars);
  if (detailEl) detailEl.textContent = fillTemplate(t('metaDetail'), vars);
  if (sourcesEl) sourcesEl.textContent = fillTemplate(t('metaSources'), vars);
}

function applyIrBrand() {
  const logoEl = document.getElementById('i18n-ir-logo');
  if (logoEl) logoEl.textContent = t('irLogo');
  const el = document.getElementById('i18n-ir-brand');
  if (!el) return;
  const raw = t('irBrand');
  const parts = raw.split('•');
  if (parts.length === 2) {
    el.innerHTML = `${parts[0].trim()}<span class="ir-dot">•</span>${parts[1].trim()}`;
  } else {
    el.textContent = raw;
  }
}

function applyStaticI18n() {
  document.title = t('pageTitle');
  const map = {
    'i18n-title': 'title',
    'i18n-download-all': 'downloadAll',
    'i18n-tab-weekly': 'tabWeekly',
    'i18n-tab-monthly': 'tabMonthly',
    'i18n-tab-quarterly': 'tabQuarterly',
    'i18n-kpi-occ': 'kpiOcc',
    'i18n-kpi-adr': 'kpiAdr',
    'i18n-kpi-revpar': 'kpiRevpar',
    'i18n-kpi-pax': 'kpiPax',
    'i18n-kpi-ticket': 'kpiTicket',
    'i18n-kpi-flight': 'kpiFlight',
    'i18n-chart-weekly-hotel': 'chartWeeklyHotel',
    'i18n-chart-weekly-aviation': 'chartWeeklyAviation',
    'i18n-chart-monthly-hotel': 'chartMonthlyHotel',
    'i18n-chart-monthly-dom-av': 'chartMonthlyDomAv',
    'i18n-chart-monthly-railway': 'chartMonthlyRailway',
    'i18n-chart-monthly-intl': 'chartMonthlyIntl',
    'i18n-chart-q-trend': 'chartQTrend',
    'i18n-chart-q-compare': 'chartQCompare',
    'i18n-sector-hotel': 'sectorHotel',
    'i18n-sector-hotel-w': 'sectorHotel',
    'i18n-sector-hotel-m': 'sectorHotel',
    'i18n-sector-aviation-w': 'sectorDomestic',
    'i18n-sector-domestic': 'sectorDomestic',
    'i18n-sector-domestic-m': 'sectorDomestic',
    'i18n-sector-intl': 'sectorIntl',
    'i18n-sector-intl-m': 'sectorIntl',
    'i18n-insights-title': 'insightsTitle',
  };
  Object.keys(map).forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = t(map[id]);
  });
  applyIrBrand();
  applyHeroMeta();
  document.querySelectorAll('.dl-text').forEach(el => { el.textContent = t('downloadImg'); });
  const langBtn = document.getElementById('lang-toggle');
  if (langBtn) langBtn.textContent = t('langBtn');
  const footer = document.getElementById('i18n-footer');
  if (footer && typeof DATA !== 'undefined' && DATA && DATA.meta) {
    footer.textContent = `${t('footer')}  |  ${DATA.meta.dataUpdate || ''}  |  ${DATA.meta.compareBase || ''}`;
  }
  renderInsights();
}
