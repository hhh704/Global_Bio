-- ============================================================
-- 바이오텍 실적 대시보드 · Supabase 스키마 (매출 + 컨센서스 추정치 + 순이익·현금)
-- Supabase 대시보드 > SQL Editor 에 통째로 붙여넣고 Run 하세요.
-- 여러 번 실행해도 안전합니다 (IF NOT EXISTS / DROP POLICY IF EXISTS).
-- 모든 테이블이 bio_ 로 시작합니다 → 제약 대시보드(earn_*)·Global_Bio(hc_*) 테이블과 겹치지 않습니다.
-- 시계열 칸: a(연간 실적) q(분기 실적) ae(연간 추정) qe(분기 추정)  예: {"2025": 4248.05}
-- ============================================================

-- 1) 기업 ---------------------------------------------------
create table if not exists public.bio_companies (
  id           text primary key,            -- 'ARGX'
  name         text not null,               -- 'argenx'
  label        text not null,               -- 화면 버튼 이름 '아르젠엑스'
  ticker       text,                        -- Bloomberg 표기 'ARGX US'
  us_ticker    text,                        -- 미국 상장 티커(주가·뉴스 조회용)
  ko           text,
  currency     text not null default 'USD', -- 원본 통화(BNTX = EUR, 환산하지 않음)
  fy_end       text not null default '12',  -- 결산월(ARWR = '09')
  last_actual  jsonb not null default '{}', -- {"a":"2025","q":"2026Q2"} 이후 기간은 추정치
  sort_order   int  not null default 100,
  bucket_order jsonb not null default '[]',
  region_note  text,
  total        jsonb not null default '{"a":{},"q":{},"ae":{},"qe":{}}',
  notes        jsonb not null default '[]',
  updated_at   timestamptz not null default now()
);

-- 2) 매출 구성(제품·협업·로열티·기타·미분류) ----------------
create table if not exists public.bio_buckets (
  company_id   text not null references public.bio_companies(id) on delete cascade,
  id           text not null,
  en text, ko text, kind text, scope text, parent text,
  a  jsonb not null default '{}', q  jsonb not null default '{}',
  ae jsonb not null default '{}', qe jsonb not null default '{}',
  der          jsonb not null default '{}',
  derived_pts  int,
  sort_order   int not null default 0,
  updated_at   timestamptz not null default now(),
  primary key (company_id, id)
);

-- 3) 제품 ---------------------------------------------------
create table if not exists public.bio_products (
  company_id   text not null references public.bio_companies(id) on delete cascade,
  id           text not null,
  en text, ko text, bucket text, kind text,
  flags        jsonb not null default '[]',
  other        boolean not null default false,
  a  jsonb not null default '{}', q  jsonb not null default '{}',
  ae jsonb not null default '{}', qe jsonb not null default '{}',
  sort_order   int not null default 0,
  updated_at   timestamptz not null default now(),
  primary key (company_id, id)
);

-- 4) 지역 ---------------------------------------------------
create table if not exists public.bio_regions (
  company_id   text not null references public.bio_companies(id) on delete cascade,
  id           text not null,
  en text, ko text,
  a  jsonb not null default '{}', q  jsonb not null default '{}',
  ae jsonb not null default '{}', qe jsonb not null default '{}',
  sort_order   int not null default 0,
  updated_at   timestamptz not null default now(),
  primary key (company_id, id)
);

-- 5) 매출 외 지표(순이익·현금) -------------------------------
create table if not exists public.bio_metrics (
  company_id   text not null references public.bio_companies(id) on delete cascade,
  id           text not null,               -- 'net_income' | 'cash'
  en text, ko text,
  unit         text,                        -- 'musd'(기간값) | 'musd_bal'(기말잔액)
  note         text,
  a  jsonb not null default '{}', q  jsonb not null default '{}',
  ae jsonb not null default '{}', qe jsonb not null default '{}',
  sort_order   int not null default 0,
  updated_at   timestamptz not null default now(),
  primary key (company_id, id)
);

-- 6) 갱신 이력 ------------------------------------------------
create table if not exists public.bio_updates (
  id          bigserial primary key,
  at          timestamptz not null default now(),
  companies   text[],
  note        text
);

create index if not exists bio_buckets_company_idx  on public.bio_buckets  (company_id);
create index if not exists bio_products_company_idx on public.bio_products (company_id);
create index if not exists bio_regions_company_idx  on public.bio_regions  (company_id);
create index if not exists bio_metrics_company_idx  on public.bio_metrics  (company_id);

-- ------------------------------------------------------------
-- 보안: 읽기는 누구나(anon), 쓰기는 service_role 키만.
--   service_role 키는 RLS 를 우회하므로 로컬 시드 스크립트에서만 쓰고
--   절대 GitHub·config.js·채팅에 넣지 마세요.
-- ------------------------------------------------------------
do $$
declare t text;
begin
  foreach t in array array['bio_companies','bio_buckets','bio_products','bio_regions','bio_metrics','bio_updates']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists "public read" on public.%I', t);
    execute format('create policy "public read" on public.%I for select to anon, authenticated using (true)', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
    execute format('grant select on public.%I to anon, authenticated', t);
    execute format('grant all on public.%I to service_role', t);
  end loop;
end $$;
grant usage, select on sequence public.bio_updates_id_seq to service_role;

-- 주가·뉴스(2단계)는 Global_Bio 와 같은 hc_prices / hc_market_data / hc_news 테이블을 씁니다(티커 단위 공유).
-- 이미 Global_Bio 에서 쓰고 있다면 따로 만들 것이 없습니다. 없으면 README 의 "hc_ 테이블이 없을 때"를 보세요.
