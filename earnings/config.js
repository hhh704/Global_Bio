// 읽기 전용 공개 설정입니다. anon(public) 키는 브라우저에 노출되어도 되는 키이며,
// 쓰기는 RLS(읽기 전용 정책)로 막혀 있습니다. service_role 키는 절대 여기에 넣지 마세요.
// 비워 두면 내장 데이터(data/data.json)로 표시되고, 화면 하단 '연결 설정'에서 브라우저에만 저장할 수도 있습니다.
window.EARN_CONFIG = {
  supabaseUrl: "",      // 예: "https://abcdxyz.supabase.co"
  supabaseAnonKey: ""   // Project Settings > API > anon public
};
