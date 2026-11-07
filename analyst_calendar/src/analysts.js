// 애널리스트 명단 — 🔥 불꽃 리서치 채널 커버리지(조선·방산·기계) 기준.
// name 은 실제 담당자 이름으로 바꿔 넣으면 된다. coverage 의 종목/산업 태그가
// 보고서 해시태그·제목과 맞으면 그 사람 자료로 분류된다.
export const ANALYSTS = [
  {
    id: "ship", name: "조선 담당", team: "조선", color: "#1f6feb",
    coverage: ["조선", "한화오션", "HD현대중공업", "삼성중공업", "HD한국조선해양",
      "HD현대미포", "HJ중공업", "HD현대마린솔루션", "HD현대마린엔진", "한화엔진",
      "STX엔진", "세진중공업", "동성화인텍", "태광", "성광벤드"],
  },
  {
    id: "defense", name: "방산 담당", team: "방산", color: "#d1242f",
    coverage: ["방산", "한화에어로스페이스", "LIG넥스원", "현대로템", "한국항공우주",
      "KAI", "풍산", "한화시스템", "SNT다이내믹스", "휴니드", "빅텍"],
  },
  {
    id: "machinery", name: "기계 담당", team: "기계", color: "#1a7f37",
    coverage: ["기계", "두산에너빌리티", "두산밥캣", "HD현대인프라코어",
      "HD현대건설기계", "HD현대일렉트릭", "효성중공업", "LS일렉트릭", "대동", "TYM",
      "씨에스윈드", "SK오션플랜트"],
  },
];

export function assignAnalyst(tags = [], title = "") {
  for (const a of ANALYSTS)
    if (a.coverage.some((c) => tags.includes(c))) return a.id;
  for (const a of ANALYSTS)
    if (a.coverage.some((c) => title.includes(c))) return a.id;
  return null;
}
