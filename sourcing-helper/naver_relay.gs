/**
 * 소싱도우미 네이버 API 중계 (Google Apps Script 웹앱)
 *
 * [설정] 프로젝트 설정(톱니바퀴) → 스크립트 속성에 아래 키 추가
 *   NAVER_CLIENT_ID      : 개발자센터 Client ID
 *   NAVER_CLIENT_SECRET  : 개발자센터 Client Secret
 *   ACCESS_TOKEN         : 아무 긴 문자열 (웹앱 접근용 비밀번호)
 *   SEARCHAD_API_KEY     : (선택) 검색광고 API 키
 *   SEARCHAD_SECRET      : (선택) 검색광고 비밀키
 *   SEARCHAD_CUSTOMER_ID : (선택) 검색광고 CUSTOMER_ID
 *
 * [배포] 배포 → 새 배포 → 유형: 웹 앱
 *   실행 계정: 나 / 액세스 권한: 모든 사용자
 *
 * [호출] {웹앱URL}?token=ACCESS_TOKEN&q=키워드1,키워드2
 */

function doGet(e) {
  const props = PropertiesService.getScriptProperties().getProperties();
  const p = e.parameter || {};
  if (!props.ACCESS_TOKEN || p.token !== props.ACCESS_TOKEN) {
    return json_({ error: 'unauthorized' });
  }
  const keywords = String(p.q || '')
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)
    .slice(0, 5);
  if (!keywords.length) return json_({ error: 'q required (comma-separated, max 5)' });

  const out = { keywords: keywords, fetchedAt: new Date().toISOString() };

  // 1) 네이버 쇼핑 검색: 국내 판매 여부·가격대
  out.shopping = {};
  keywords.forEach(k => {
    try {
      out.shopping[k] = shopSearch_(k, props);
    } catch (err) {
      out.shopping[k] = { error: String(err) };
    }
  });

  // 2) 데이터랩 검색어 트렌드: 최근 12개월 상대지수 (앱에 데이터랩 API 추가 필요)
  try {
    out.trend = datalab_(keywords, props);
  } catch (err) {
    out.trend = { error: String(err) };
  }

  // 3) 검색광고 키워드도구: 월간 검색량 (키 있을 때만)
  if (props.SEARCHAD_API_KEY && props.SEARCHAD_SECRET && props.SEARCHAD_CUSTOMER_ID) {
    try {
      out.volume = keywordTool_(keywords, props);
    } catch (err) {
      out.volume = { error: String(err) };
    }
  } else {
    out.volume = { note: 'searchad keys not set' };
  }

  return json_(out);
}

function shopSearch_(query, props) {
  const url = 'https://openapi.naver.com/v1/search/shop.json?display=20&sort=sim&query=' +
    encodeURIComponent(query);
  const res = UrlFetchApp.fetch(url, {
    headers: {
      'X-Naver-Client-Id': props.NAVER_CLIENT_ID,
      'X-Naver-Client-Secret': props.NAVER_CLIENT_SECRET
    },
    muteHttpExceptions: true
  });
  if (res.getResponseCode() !== 200) {
    return { error: 'HTTP ' + res.getResponseCode(), body: res.getContentText().slice(0, 300) };
  }
  const data = JSON.parse(res.getContentText());
  const items = (data.items || []).map(it => ({
    title: String(it.title || '').replace(/<[^>]+>/g, ''),
    lprice: Number(it.lprice) || null,
    mall: it.mallName,
    brand: it.brand,
    maker: it.maker,
    productType: it.productType, // 1~3 일반, 4~6 중고, 7~9 단종, 10~12 판매예정
    category: [it.category1, it.category2, it.category3, it.category4].filter(Boolean).join(' > '),
    link: it.link
  }));
  const prices = items.map(i => i.lprice).filter(Boolean).sort((a, b) => a - b);
  return {
    total: data.total,
    minPrice: prices[0] || null,
    medianPrice: prices.length ? prices[Math.floor(prices.length / 2)] : null,
    maxPrice: prices[prices.length - 1] || null,
    mallCount: new Set(items.map(i => i.mall)).size,
    items: items
  };
}

function datalab_(keywords, props) {
  const end = new Date();
  const start = new Date(end.getFullYear() - 1, end.getMonth(), 1);
  const fmt = d => Utilities.formatDate(d, 'Asia/Seoul', 'yyyy-MM-dd');
  const body = {
    startDate: fmt(start),
    endDate: fmt(end),
    timeUnit: 'month',
    keywordGroups: keywords.map(k => ({ groupName: k, keywords: [k] }))
  };
  const res = UrlFetchApp.fetch('https://openapi.naver.com/v1/datalab/search', {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'X-Naver-Client-Id': props.NAVER_CLIENT_ID,
      'X-Naver-Client-Secret': props.NAVER_CLIENT_SECRET
    },
    payload: JSON.stringify(body),
    muteHttpExceptions: true
  });
  if (res.getResponseCode() !== 200) {
    return { error: 'HTTP ' + res.getResponseCode(), body: res.getContentText().slice(0, 300) };
  }
  const data = JSON.parse(res.getContentText());
  return (data.results || []).map(r => ({
    keyword: r.title,
    monthly: (r.data || []).map(d => ({ period: d.period.slice(0, 7), ratio: Math.round(d.ratio * 10) / 10 }))
  }));
}

function keywordTool_(keywords, props) {
  const path = '/keywordstool';
  const ts = String(Date.now());
  const sig = Utilities.base64Encode(
    Utilities.computeHmacSha256Signature(ts + '.GET.' + path, props.SEARCHAD_SECRET)
  );
  const hints = keywords.map(k => k.replace(/\s+/g, '')).join(',');
  const url = 'https://api.searchad.naver.com' + path +
    '?showDetail=1&hintKeywords=' + encodeURIComponent(hints);
  const res = UrlFetchApp.fetch(url, {
    headers: {
      'X-Timestamp': ts,
      'X-API-KEY': props.SEARCHAD_API_KEY,
      'X-Customer': String(props.SEARCHAD_CUSTOMER_ID),
      'X-Signature': sig
    },
    muteHttpExceptions: true
  });
  if (res.getResponseCode() !== 200) {
    return { error: 'HTTP ' + res.getResponseCode(), body: res.getContentText().slice(0, 300) };
  }
  const list = JSON.parse(res.getContentText()).keywordList || [];
  const num = v => (typeof v === 'number' ? v : 5); // "< 10" → 5로 근사
  const hintSet = new Set(keywords.map(k => k.replace(/\s+/g, '').toLowerCase()));
  const rows = list.map(r => ({
    keyword: r.relKeyword,
    pc: r.monthlyPcQcCnt,
    mobile: r.monthlyMobileQcCnt,
    total: num(r.monthlyPcQcCnt) + num(r.monthlyMobileQcCnt),
    competition: r.compIdx,
    isHint: hintSet.has(String(r.relKeyword).toLowerCase())
  }));
  const hintsOut = rows.filter(r => r.isHint);
  const related = rows.filter(r => !r.isHint).sort((a, b) => b.total - a.total).slice(0, 15);
  return { exact: hintsOut, related: related };
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/** 에디터에서 바로 테스트: 실행 → testRelay */
function testRelay() {
  const token = PropertiesService.getScriptProperties().getProperty('ACCESS_TOKEN');
  const res = doGet({ parameter: { token: token, q: '발사믹 식초,메종 브레몽' } });
  Logger.log(res.getContent().slice(0, 3000));
}
