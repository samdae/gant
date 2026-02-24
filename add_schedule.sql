INSERT INTO schedule_configs (ticker, interval_days, currency, initial_capital, market, display_name, created_at)
VALUES
  -- 기존
  ('NVDA',        1, 'USD', 5000,    'us', '엔비디아(AI반도체)',      NOW()),
  ('TSLA',        1, 'USD', 5000,    'us', '테슬라(전기차)',         NOW()),
  ('GOOGL',       1, 'USD', 5000,    'us', '구글(빅테크)',           NOW()),
  ('SPY',         1, 'USD', 5000,    'us', 'S&P500 ETF',           NOW()),
  ('GLD',         1, 'USD', 5000,    'us', '금 ETF',               NOW()),
  ('SLV',         1, 'USD', 5000,    'us', '은 ETF',               NOW()),
  ('BTC-USD',     1, 'USD', 5000,    'us', '비트코인',              NOW()),
  ('000660.KS',   1, 'KRW', 5000000, 'kr', 'SK하이닉스(반도체)',     NOW()),
  ('005930.KS',   1, 'KRW', 5000000, 'kr', '삼성전자',              NOW()),
  -- 신규
  ('FSLR',        1, 'USD', 5000,    'us', '퍼스트솔라(태양광)',      NOW()),
  ('VST',         1, 'USD', 5000,    'us', '비스트라(전력)',         NOW()),
  ('OXY',         1, 'USD', 5000,    'us', '옥시덴탈(석유)',         NOW()),
  ('DLR',         1, 'USD', 5000,    'us', '디지털리얼티(데이터센터)', NOW()),
  ('SCHP',        1, 'USD', 5000,    'us', '물가연동채 ETF',        NOW()),
  ('005380.KS',   1, 'KRW', 5000000, 'kr', '현대차',               NOW()),
  ('012450.KS',   1, 'KRW', 5000000, 'kr', '한화에어로(방산)',       NOW()),
  ('034020.KS',   1, 'KRW', 5000000, 'kr', '두산에너빌리티(원전)',    NOW()),
  ('096770.KS',   1, 'KRW', 5000000, 'kr', 'SK이노베이션(정유)',     NOW()),
  ('036460.KS',   1, 'KRW', 5000000, 'kr', '한국가스공사',          NOW()),
  ('009830.KS',   1, 'KRW', 5000000, 'kr', '한화솔루션(태양광)',     NOW()),
  ('267260.KS',   1, 'KRW', 5000000, 'kr', 'HD현대일렉(전력기기)',   NOW())
ON CONFLICT (ticker) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  interval_days = EXCLUDED.interval_days;