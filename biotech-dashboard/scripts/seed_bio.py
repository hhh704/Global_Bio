#!/usr/bin/env python3
"""
바이오텍 표준 데이터(JSON) -> Supabase(bio_* 테이블) 업로드.

사용법
  export SUPABASE_URL="https://xxxx.supabase.co"
  export SUPABASE_SERVICE_KEY="sb_secret_... (또는 legacy service_role eyJ...)"   # 절대 커밋/공유 금지
  python3 scripts/seed_bio.py --dry-run                   # 업로드 없이 건수만 확인
  python3 scripts/seed_bio.py                             # 전체 업로드
  python3 scripts/seed_bio.py --only VRTX,REGN            # 일부 기업만

동작
  - 기업 -> 매출 구성 -> 제품 -> 지역 -> 지표(순이익·현금) 순으로 upsert(있으면 갱신, 없으면 추가)
  - 올린 기업 안에서 JSON 에 더 이상 없는 행은 삭제(--no-prune 으로 끔)
  - 기업 표시 정보(버튼 이름·순서·색 순서·지역 부제·미국 티커)는 scripts/company_meta.json 에서 읽음
외부 패키지 없이 표준 라이브러리만 사용합니다.
"""
import argparse, json, os, sys, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHUNK = 200
T4 = ('a', 'q', 'ae', 'qe')


def auth(key):
    # 새 형식 키(sb_secret_...)는 apikey 헤더로만, 기존 service_role(JWT, eyJ...)는 Authorization 도 함께
    return {'apikey': key} if key.startswith('sb_') else {'apikey': key, 'Authorization': 'Bearer ' + key}


def api(base, key, method, path, body=None, prefer=None):
    url = base.rstrip('/') + '/rest/v1/' + path
    h = {**auth(key), 'Content-Type': 'application/json'}
    if prefer:
        h['Prefer'] = prefer
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = r.read().decode('utf-8')
            return json.loads(txt) if txt else None
    except urllib.error.HTTPError as e:
        msg = e.read().decode('utf-8', 'replace')
        hint = ''
        if e.code == 404 or 'does not exist' in msg:
            hint = '\n→ supabase/bio_schema.sql 을 SQL Editor 에서 먼저 실행했는지 확인하세요.'
        elif e.code in (401, 403):
            hint = '\n→ SUPABASE_SERVICE_KEY 가 secret 키(sb_secret_...) 또는 legacy service_role 키인지 확인하세요(publishable/anon 키로는 쓸 수 없습니다).'
        sys.exit(f'[오류] {method} {path.split("?")[0]} -> HTTP {e.code}\n{msg}{hint}')
    except urllib.error.URLError as e:
        sys.exit(f'[오류] 연결 실패: {e.reason}\n→ SUPABASE_URL 을 확인하세요.')


def ser(x):
    return {t: (x.get(t) or {}) for t in T4}


def rows_for(co_id, c, meta, order, now):
    m = meta.get(co_id, {})
    company = {
        'id': co_id, 'name': c['name'], 'label': m.get('label') or c.get('ko') or c['name'],
        'ticker': c.get('ticker'), 'us_ticker': m.get('us_ticker'), 'ko': c.get('ko'),
        'currency': c.get('currency') or 'USD', 'fy_end': c.get('fy_end') or '12',
        'last_actual': c.get('last_actual') or {},
        'sort_order': m.get('sort_order', 100 + order * 10),
        'bucket_order': m.get('bucket_order') or [], 'region_note': m.get('region_note') or '',
        'total': ser(c.get('total') or {}), 'notes': c.get('notes') or [], 'updated_at': now,
    }
    base = lambda i: {'company_id': co_id, 'sort_order': i, 'updated_at': now}
    buckets = [{**base(i), 'id': b['id'], 'en': b.get('en'), 'ko': b.get('ko'), 'kind': b.get('kind'),
                'scope': b.get('scope'), 'parent': b.get('parent'), **ser(b), 'der': b.get('der') or {},
                'derived_pts': b.get('derived_pts')} for i, b in enumerate(c['buckets'])]
    products = [{**base(i), 'id': p['id'], 'en': p.get('en'), 'ko': p.get('ko'), 'bucket': p.get('bucket'),
                 'kind': p.get('kind'), 'flags': p.get('flags') or [], 'other': bool(p.get('other')), **ser(p)}
                for i, p in enumerate(c['products'])]
    regions = [{**base(i), 'id': r['id'], 'en': r.get('en'), 'ko': r.get('ko'), **ser(r)} for i, r in enumerate(c['regions'])]
    metrics = [{**base(i), 'id': x['id'], 'en': x.get('en'), 'ko': x.get('ko'), 'unit': x.get('unit'),
                'note': x.get('note'), **ser(x)} for i, x in enumerate(c.get('metrics') or [])]
    return company, buckets, products, regions, metrics


def upsert(base, key, table, rows, conflict):
    for i in range(0, len(rows), CHUNK):
        api(base, key, 'POST', f'{table}?on_conflict={conflict}', rows[i:i + CHUNK],
            prefer='resolution=merge-duplicates,return=minimal')


def fetch_all(base, key, path, page=1000):
    out, start = [], 0
    while True:
        url = base.rstrip('/') + '/rest/v1/' + path
        req = urllib.request.Request(url, headers={**auth(key), 'Range-Unit': 'items', 'Range': f'{start}-{start + page - 1}'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                rows = json.loads(r.read().decode('utf-8') or '[]')
        except urllib.error.HTTPError as e:
            sys.exit(f'[오류] GET {path.split("?")[0]} -> HTTP {e.code}\n{e.read().decode("utf-8", "replace")}')
        out += rows
        if len(rows) < page:
            return out
        start += page


def prune(base, key, table, co_id, keep_ids):
    q = f'{table}?select=id&company_id=eq.{urllib.parse.quote(co_id, safe="")}'
    have = {r['id'] for r in (fetch_all(base, key, q) or [])}
    stale = sorted(have - set(keep_ids))
    for sid in stale:
        api(base, key, 'DELETE', f'{table}?company_id=eq.{urllib.parse.quote(co_id, safe="")}&id=eq.{urllib.parse.quote(sid, safe="")}')
    return len(stale)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', default=os.path.join(ROOT, 'biotech', 'data', 'data.json'))
    ap.add_argument('--meta', default=os.path.join(HERE, 'company_meta.json'))
    ap.add_argument('--only', help='쉼표로 구분한 기업 id (예: VRTX,REGN)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-prune', action='store_true', help='JSON 에 없는 기존 행을 지우지 않음')
    ap.add_argument('--note', default='seed_bio.py')
    a = ap.parse_args()

    data = json.load(open(a.data, encoding='utf-8'))
    meta = json.load(open(a.meta, encoding='utf-8')) if os.path.exists(a.meta) else {}
    ids = [x.strip() for x in a.only.split(',')] if a.only else list(data)
    miss = [i for i in ids if i not in data]
    if miss:
        sys.exit(f'[오류] 데이터에 없는 기업: {miss}')
    base = os.environ.get('SUPABASE_URL', '').strip()
    key = os.environ.get('SUPABASE_SERVICE_KEY', '').strip()
    if not a.dry_run and not (base and key):
        sys.exit('[오류] SUPABASE_URL 과 SUPABASE_SERVICE_KEY 환경변수를 먼저 설정하세요.')

    now = datetime.now(timezone.utc).isoformat()
    built = [rows_for(co, data[co], meta, n, now) for n, co in enumerate(data) if co in ids]
    tot = [0] * 5
    for c, b, p, r, m in built:
        print(f'{c["id"]:<5} {c["currency"]} 매출구성 {len(b):>2} · 제품 {len(p):>2} · 지역 {len(r):>2} · 지표 {len(m)} · 마지막 실적 {c["last_actual"]}')
        tot = [tot[0] + 1, tot[1] + len(b), tot[2] + len(p), tot[3] + len(r), tot[4] + len(m)]
    print(f'합계  기업 {tot[0]} · 매출구성 {tot[1]} · 제품 {tot[2]} · 지역 {tot[3]} · 지표 {tot[4]}')
    if a.dry_run:
        print('(dry-run: 업로드하지 않았습니다)')
        return

    upsert(base, key, 'bio_companies', [c for c, *_ in built], 'id')
    for c, b, p, r, m in built:
        for table, rows in (('bio_buckets', b), ('bio_products', p), ('bio_regions', r), ('bio_metrics', m)):
            upsert(base, key, table, rows, 'company_id,id')
        if not a.no_prune:
            gone = sum(prune(base, key, t, c['id'], [x['id'] for x in rows])
                       for t, rows in (('bio_buckets', b), ('bio_products', p), ('bio_regions', r), ('bio_metrics', m)))
            if gone:
                print(f'  {c["id"]}: 삭제된 옛 행 {gone}개')
    api(base, key, 'POST', 'bio_updates', [{'companies': [c['id'] for c, *_ in built], 'note': a.note}], prefer='return=minimal')
    print('완료.')


if __name__ == '__main__':
    main()
