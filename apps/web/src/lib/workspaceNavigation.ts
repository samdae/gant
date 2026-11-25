export const homeRoute = "/reports";
export const sections = [
  {
    name: "예측 연구",
    pages: [
      { route: "/research", label: "연구 사례" },
      { route: "/results", label: "예측 성과" },
      { route: "/observe", label: "관측 현황" },
    ],
  },
  {
    name: "분석 기록",
    pages: [
      { route: "/reports", label: "분석 리포트" },
      { route: "/reflections", label: "매매 검증" },
      { route: "/retrospective", label: "회고 분석" },
    ],
  },
  {
    name: "모의 거래",
    pages: [
      { route: "/dashboard", label: "대시보드" },
      { route: "/portfolio", label: "포트폴리오" },
      { route: "/positions", label: "보유·종료 종목" },
    ],
  },
  {
    name: "운영",
    pages: [
      { route: "/schedules", label: "분석 예약" },
      { route: "/live", label: "실시간 실행" },
    ],
  },
  {
    name: "안내",
    pages: [
      { route: "/about", label: "서비스 소개" },
      { route: "/auth", label: "관리자 인증" },
    ],
  },
];

export function currentPage(location: string) {
  const [, base = "", detail] = location.split("?")[0].split("/");
  const aliases: Record<string, string> = {
    "": homeRoute,
    performance: "/results",
    trade: "/positions",
  };
  const path = aliases[base] || "/" + base;
  for (const section of sections) {
    const page = section.pages.find((item) => item.route === path);
    if (page) return { section, page, detail };
  }
  return {
    section: sections[0],
    page: sections[0].pages[0],
    detail: undefined,
  };
}
