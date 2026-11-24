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
  ];
</script>

<section class="op-page">
  <header class="op-title">
    <div>
      <h1>연구실 안내</h1>
      <p>
        같은 시장 근거를 본 모델이 토론이나 과거 경험을 통해 더 정확한 확률을 내는지 관측합니다.
      </p>
    </div>
    <a class="op-primary" href="#/research">예측 사례 보기 →</a>
  </header>
  <section class="op-panel">
    <h2>한 사례의 관측 과정</h2>
    <ol class="op-journey">
      <li>
        <strong>근거 동결</strong>
        <p>한국·미국 주식과 ETF의 마감 시세를 확인하고 분석에 사용한 거래일과 가격을 저장합니다.</p>
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
  <div class="op-two">
    <section class="op-panel">
      <h2>비교하는 네 가지 방법</h2>
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
      <a href="#/" on:click={() => viewMode.set("analysis")}
        ><strong>종목별 분석 모드 →</strong><span>종목별 판단과 보유·청산 기록</span></a
      ><a href="#/portfolio"
        ><strong>포트폴리오 모드 →</strong><span>공유 자금과 포트폴리오 배분</span></a
      ><a href="#/schedules"
        ><strong>분석 예약 →</strong><span>종목과 주기를 지정한 실행 일정</span></a
      ><a href="#/live"><strong>실시간 실행 →</strong><span>대기열 및 진행 중인 분석 단계</span></a>
    </div>
  </section>
</section>
