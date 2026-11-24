export const sections = [
  {
    name: "연구",
    pages: [
      {
        route: "/research",
        label: "예측 연구",
        icon: "M3 17l5-6 4 3 8-10M15 4h5v5",
      },
      {
        route: "/reports",
        label: "분석 리포트",
        icon: "M5 3h10l4 4v14H5zM14 3v5h5M8 12h8M8 16h6",
      },
      {
        route: "/reflections",
        label: "매매 검증",
        icon: "M4 5h16v14H4zM8 12l3 3 5-6",
      },
      {
        route: "/retrospective",
        label: "회고 분석",
        icon: "M3 10a9 9 0 1 1 2 8M3 4v6h6M12 7v5l3 2",
      },
    ],
  },
  {
    name: "거래 콘솔",
    pages: [
      {
        route: "/",
        label: "대시보드",
        icon: "M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z",
      },
      {
        route: "/portfolio",
        label: "포트폴리오",
        icon: "M3 7h18v13H3zM8 7V4h8v3M3 11l9 3 9-3",
      },
      {
        route: "/positions",
        label: "보유 종목",
        icon: "M3 8l9-5 9 5-9 5zM3 12l9 5 9-5M3 16l9 5 9-5",
      },
    ],
  },
  {
    name: "운영",
    pages: [
      {
        route: "/schedules",
        label: "분석 예약",
        icon: "M4 6h16v15H4zM8 3v6M16 3v6M4 11h16M8 15h3",
      },
      {
        route: "/live",
        label: "실시간 모니터",
        icon: "M2 12h5l3-7 4 14 3-7h5",
      },
    ],
  },
  {
    name: "설정",
    pages: [
      {
        route: "/about",
        label: "서비스 소개",
        icon: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v6M12 7v.1",
      },
      {
        route: "/auth",
        label: "관리자 인증",
        icon: "M5 10h14v10H5zM8 10V7a4 4 0 0 1 8 0v3M12 14v2",
      },
    ],
  },
];

export function currentPage(location: string) {
  const [, base = "", detail] = location.split("?")[0].split("/");
  const path = base === "trade" ? "/positions" : "/" + base;
  for (const section of sections) {
    const page = section.pages.find((p) => p.route === path);
    if (page) return { section: section.name, page, detail };
  }
  return { section: "연구", page: sections[0].pages[0], detail: undefined };
}
