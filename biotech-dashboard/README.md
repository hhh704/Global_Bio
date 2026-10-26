# 바이오텍 실적 대시보드 · 배포 패키지 (Supabase + GitHub Pages + 주가·뉴스)

11개사(ALNY·ARGX·ARWR·BNTX·HALO·MDGL·MRNA·REGN·RVMD·SRPT·VRTX)의 매출 구성, 제품별 매출, 순이익·현금·런웨이, 컨센서스 추정치(연간 ~2030, 분기 ~2027Q4)에 주가·밸류에이션·뉴스 카드까지 붙은 화면입니다.
기존 제약 대시보드(`earnings/`, `earn_*` 테이블)와 Global_Bio는 건드리지 않습니다.

```
biotech/index.html             대시보드 화면 (Supabase → 실패하면 data/data.json 으로 표시)
biotech/config.js              Supabase URL + anon 키 (공개해도 되는 읽기 전용 키만)
biotech/data/data.json         표준 데이터 11개사 (대체 모드 + 업로드 원본)
biotech/data/company_meta.json 기업 표시 정보 (버튼 이름·순서·색 순서·지역 부제·미국 티커)
supabase/bio_schema.sql        bio_* 테이블 + 읽기 전용 보안 정책
scripts/seed_bio.py            data.json → Supabase 업로드 (표준 라이브러리만 사용)
scripts/company_meta.json      위 메타의 업로드용 사본 (두 파일은 같은 내용으로 유지)
```

## 설정 순서 (약 15분)

### 1. Supabase 테이블 만들기
제약 대시보드에 쓰던 Supabase 프로젝트를 엽니다 → **SQL Editor → New query** → `supabase/bio_schema.sql` 전체를 붙여넣고 **Run**.
- 왼쪽 **Table Editor**에 `bio_companies`, `bio_buckets`, `bio_products`, `bio_regions`, `bio_metrics`, `bio_updates` 6개가 보이면 성공입니다.
- 여러 번 실행해도 안전합니다. `earn_*`, `hc_*` 테이블에는 영향이 없습니다.

### 2. 키 확인 — Settings → API Keys
| 항목 | 새 형식 | 기존(Legacy API Keys 탭) | 어디에 쓰나 | 공개 |
|---|---|---|---|---|
| Project URL `https://xxxx.supabase.co` | (Settings → Data API 또는 상단 Connect) | | 3·4단계 | 공개돼도 됨 |
| 공개 키 | publishable `sb_publishable_...` | anon `eyJ...` | 4단계 `config.js` | 공개돼도 됨(읽기만) |
| 비밀 키 | secret `sb_secret_...` | service_role `eyJ...` | 3단계 터미널에서만 | **절대 비공개** |

새 형식과 기존 형식 어느 쪽이든 동작합니다. Supabase는 기존 anon·service_role 키를 2026년 말까지 단계적으로 없앨 예정이라 새 형식을 권장합니다.

### 3. 데이터 올리기 (내 컴퓨터 터미널)
```
cd biotech-dashboard            # 이 패키지를 푼 폴더
export SUPABASE_URL="https://xxxx.supabase.co"
export SUPABASE_SERVICE_KEY="sb_secret_... (secret 키)"
python3 scripts/seed_bio.py --dry-run    # 건수 확인: 기업 11 · 매출구성 33 · 제품 49 · 지역 13 · 지표 22
python3 scripts/seed_bio.py              # 실제 업로드 → 마지막에 "완료."
```
- Windows PowerShell이면 `export` 대신 `$env:SUPABASE_URL="..."`, `$env:SUPABASE_SERVICE_KEY="..."`.
- **비밀 키(secret/service_role)는 이 터미널에서만** 쓰세요. GitHub·`config.js`·채팅에 넣지 마세요. 터미널을 닫으면 사라집니다.
- 오류가 나면 메시지 아래 `→` 줄에 원인 안내가 나옵니다(테이블 없음 → 1단계, 401/403 → 비밀 키 확인).

### 4. 화면 연결
`biotech/config.js`를 열어 **Project URL과 공개 키(publishable 또는 anon)만** 넣습니다.
```js
window.EARN_CONFIG = {
  supabaseUrl: "https://xxxx.supabase.co",
  supabaseAnonKey: "sb_publishable_..."
};
```

### 5. GitHub에 올리기
`biotech/` 폴더 **하나만** 기존 `Global_Bio` 저장소 맨 위에 복사합니다(`earnings/`와 나란히).
```
cd Global_Bio
git add biotech
git commit -m "바이오텍 대시보드 추가"
git push
```
1~2분 뒤 **https://hhh704.github.io/Global_Bio/biotech/** 에서 열립니다.
(`supabase/`, `scripts/`, `README.md`는 저장소에 올리지 않아도 됩니다. 올려도 키가 없어 안전합니다.)

### 6. 확인
- 화면 맨 아래 `데이터: Supabase · 갱신 …` → 정상.
- `Supabase 미설정 → 내장 데이터 표시` 또는 `연결 실패` → 4단계 `config.js` 값을 확인하세요(화면은 data.json 으로 그대로 나옵니다).

### 7. 주가·뉴스 카드
- 기업을 고르면 KPI 아래에 **주가·밸류에이션·뉴스** 카드와 **기업 수익률 비교** 카드가 나옵니다.
- 카드 아래 **API 키 설정**에 Twelve Data(주가)·Finnhub(시총·PER·PSR·PBR·뉴스) 키를 넣고 저장 → **주가/시총·밸류/뉴스 새로고침**.
  - Global_Bio·제약 대시보드에서 이미 키를 넣었다면 같은 주소(hhh704.github.io)라 **자동으로 "있음"** 으로 표시됩니다.
  - 키는 이 브라우저(localStorage)에만 저장되고 GitHub·Supabase에는 올라가지 않습니다.
- 가져온 주가·시총·뉴스는 Global_Bio와 같은 `hc_prices` / `hc_market_data` / `hc_news` 테이블에 **티커 단위로 공유 저장**됩니다(ARGX처럼 양쪽에 있는 기업은 한 번만 가져오면 됨). 쓰기가 막혀 있으면 이 브라우저에만 임시 저장됩니다.
- 무료 한도: Twelve Data 분당 8회·일 800회(전체 주가는 7개사마다 1분 자동 대기), Finnhub 분당 60회.
- 참고: 바이오엔텍(BNTX)은 주가·시총이 USD(미국 ADR), 실적은 EUR입니다. 애로우헤드(ARWR)는 9월 결산이라 실적 기간 이름이 회계연도 기준입니다.

## 나중에 기업 추가·실적 갱신
1. Bloomberg PDF(`<TICKER>_A.pdf`, `<TICKER>_Q.pdf`)를 "바이오텍_실적분석" 프로젝트 대화에 올리면, 추출·검증 후 새 `data.json`과 `company_meta.json`을 받습니다.
2. `biotech/data/data.json`, `biotech/data/company_meta.json`, `scripts/company_meta.json`을 덮어씁니다.
3. `python3 scripts/seed_bio.py` (일부만: `--only VRTX,REGN`)
   - 있는 행은 갱신, 새 행은 추가, JSON에서 사라진 행은 삭제(`--no-prune`으로 끔).
4. `biotech/` 폴더를 다시 commit/push (data.json 대체 모드용).

## hc_ 테이블이 없을 때 (Global_Bio를 다른 Supabase 프로젝트에서 쓰는 경우)
주가·뉴스 카드는 `hc_prices`, `hc_market_data`, `hc_news`가 없어도 동작하지만 가져온 값이 이 브라우저에만 저장됩니다. 공유하려면 Global_Bio가 쓰는 테이블 정의를 같은 프로젝트에 만들어 주세요(필요하면 요청하세요).

## 보안 요약
- `config.js`에는 **공개 키(publishable/anon)만**. 비밀 키(secret/service_role)는 3단계 터미널에서만.
- `bio_*` 테이블은 읽기 전용(RLS): 화면(anon)은 읽기만, 쓰기는 service_role(시드 스크립트)만 가능.
- 주가·뉴스 API 키는 브라우저 localStorage에만.
