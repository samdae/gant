<script lang="ts">
  import "./labOperations.css";
  import { viewMode } from "../stores/mode";
  const methods = [
    [
      "빈도 기준선",
      "이미 끝난 같은 종목의 5거래일 구간에서 상승 빈도를 계산하고 표본 수를 보정합니다.",
    ],
    ["단일 모델", "동결된 시장 근거만 보고 상승 확률을 추정합니다."],
    ["역할 토론", "강세·약세 분석가부터 위험 심판까지 여덟 역할이 같은 근거를 검토합니다."],
    [
      "기억을 본 단일 모델",
      "단일 모델과 같은 조건에 이미 채점한 과거 사례 하나를 더합니다. 사용 가능한 기억이 없으면 건너뜁니다.",
    ],
    [
      "새 사례의 기억 선택 비교",
      "기존 네 방법에 더해 종목 분류와 가격 흐름으로 과거 사례를 찾습니다. 기존 기억 방식에서 예측을 발행했고 새 방식이 다른 사례를 골랐을 때만, 같은 모델에 그 사례를 제공해 추가 예측을 발행합니다.",
    ],
  ];
</script>

<section class="op-page">
  <header class="op-title">
    <div>
      <h1>GANT 연구 안내</h1>
      <p>
        개장 전 발행한 상승 확률을 다섯 거래일 뒤의 시세와 대조합니다. 각 사례에서 당시 가격, 검증 조건과 최근 30일 이슈를 함께 읽을 수 있습니다.
      </p>
    </div>
    <a class="op-primary" href="#/research">예측 사례 보기 →</a>
  </header>
  <section class="op-panel">
    <h2>한 사례의 관측 과정</h2>
    <ol class="op-journey">
      <li>
        <strong>근거 동결</strong>
        <p>한국·미국 주식과 ETF의 마감 시세, 가격 가설과 재검토 조건을 저장합니다. 공개·최초 관측 시각이 모두 기준 시점보다 앞선 최근 30일 출처를 함께 보존합니다.</p>
      </li>
      <li>
        <strong>개장 전 발행</strong>
        <p>다음 거래일 개장 전에 방법별 상승 확률과 판단 근거를 기록합니다.</p>
      </li>
      <li>
        <strong>다섯 거래일 후 채점</strong>
        <p>첫날 시가보다 다섯째 날 종가가 높으면 상승입니다. 보합은 상승에 포함하지 않습니다.</p>
      </li>
    </ol>
  </section>
  <nav class="guide-index" aria-label="연구 자료"><a href="#/research">당시 가격과 이슈 →</a><a href="#/results">방법별 채점 성과 →</a><a href="#/observe">관찰 종목·수집 현황 →</a></nav>
  <div class="op-two">
    <section class="op-panel">
      <h2>예측 방법과 기억 선택 비교</h2>
      <dl class="op-guide">
        {#each methods as method}<div>
            <dt>{method[0]}</dt>
            <dd>{method[1]}</dd>
          </div>{/each}
      </dl>
    </section>
    <section class="op-panel">
      <h2>기억의 효과 읽기</h2>
      <p>
        같은 사례에 두 방법이 모두 확률을 발행하고 실제 가격이 확인된 뒤 비교합니다. Brier 점수는
        예측 확률과 실제 결과 차이의 제곱이며, 낮을수록 정확합니다.
      </p>
      <table class="op-example">
        <caption>계산 예시 · 실제 상승한 경우</caption><thead
          ><tr><th>방법</th><th>상승 확률</th><th>Brier</th></tr></thead
        ><tbody
          ><tr><td>기억 없이</td><td>50%</td><td>0.25</td></tr><tr
            ><td>기억 제공</td><td>70%</td><td>0.09</td></tr
          ></tbody
        >
      </table>
      <p>
        이 예시의 개선량은 +0.16입니다. 반대로 보합 또는 하락했다면 −0.24입니다. 같은 버전의 공통
        사례 수와 관측 기간을 함께 확인하세요.
      </p>
    </section>
  </div>
  <section class="op-panel">
    <h2>가상매매 기록 살펴보기</h2>
    <p>
      예측 연구는 거래 여부와 관계없이 채점합니다. 가상매매에서는 종목별 판단과 실제 모의 체결을
      따라갈 수 있습니다.
    </p>
    <div class="op-links">
      <a href="#/dashboard" on:click={() => viewMode.set("analysis")}
        ><strong>종목별 분석 모드 →</strong><span>종목별 판단과 보유·청산 기록</span></a
      ><a href="#/portfolio"
        ><strong>포트폴리오 모드 →</strong><span>공유 자금과 포트폴리오 배분</span></a
      ><a href="#/schedules"
        ><strong>분석 예약 →</strong><span>종목과 주기를 지정한 실행 일정</span></a
      ><a href="#/live"><strong>실시간 실행 →</strong><span>대기열 및 진행 중인 분석 단계</span></a>
    </div>
  </section>
</section>
