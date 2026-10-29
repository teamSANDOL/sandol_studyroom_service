const TIMEOUT_MS = 5000;
const ENDING_SOON = 30;
const OPERATION_LABEL = {
  open: "운영 중",
  outside_hours: "운영시간 외",
  closed: "휴실",
  disabled: "운영 중지",
};
const KIND_LABEL = { weekday: "평일", weekend: "주말", holiday: "휴일" };

const $ = (id) => document.getElementById(id);

async function getJson(path) {
  const response = await fetch(new URL(path, document.baseURI), {
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${body?.code ?? ""}`.trim());
  }
  return body;
}

function time(iso) {
  return iso ? new Date(iso).toLocaleTimeString("ko-KR") : "-";
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function usageLevel(ratio) {
  if (ratio >= 0.8) return "high";
  if (ratio >= 0.5) return "mid";
  return "low";
}

async function run(statusId, task) {
  const status = $(statusId);
  status.textContent = "조회 중";
  try {
    status.textContent = (await task()) ?? "";
  } catch (error) {
    status.textContent = `실패: ${error.message}`;
  }
}

function roomCard(room) {
  const ratio = room.total > 0 ? room.used / room.total : 0;
  const card = el("button", "room-card");
  card.type = "button";
  card.setAttribute("aria-pressed", "false");

  const head = el("div");
  head.append(el("span", "code", room.code), el("span", "name", ` ${room.name}`));

  const count = el("div", "count");
  count.append(el("span", null, String(room.used)));
  count.append(el("small", null, ` / ${room.total}명  여유 ${room.available}`));

  const bar = el("div", `bar ${usageLevel(ratio)}`);
  const fill = el("i");
  fill.style.width = `${Math.round(ratio * 100)}%`;
  bar.append(fill);

  const badge = el("span", `badge ${room.operation}`, OPERATION_LABEL[room.operation] ?? room.operation);

  card.append(head, count, bar, badge);
  card.addEventListener("click", () => selectRoom(room.code, card));
  return card;
}

function loadRooms() {
  return run("rooms-status", async () => {
    let data;
    try {
      data = await getJson("api/readingrooms");
    } catch (error) {
      $("rooms").replaceChildren(
        el("p", "empty-note", `열람실 정보를 불러오지 못했다. (${error.message})`),
      );
      return "불러오기 실패";
    }
    if (!data.rooms.length) {
      $("rooms").replaceChildren(el("p", "empty-note", "표시할 열람실이 없다."));
      return "비어 있음";
    }
    $("rooms").replaceChildren(...data.rooms.map(roomCard));
    return `기준 ${time(data.updatedAt)}`;
  });
}

function selectRoom(code, card) {
  for (const other of document.querySelectorAll(".room-card")) {
    other.setAttribute("aria-pressed", String(other === card));
  }
  $("detail-section").hidden = false;
  return loadDetail(code);
}

function seatBox(seat) {
  const ending =
    seat.status === "occupied" &&
    seat.remainingMinutes !== null &&
    seat.remainingMinutes <= ENDING_SOON;
  const box = el("span", `seat ${ending ? "ending" : seat.status}`, seat.number);
  box.title =
    seat.remainingMinutes === null
      ? seat.name
      : `${seat.name} · 남은 ${seat.remainingMinutes}분`;
  return box;
}

function metaItem(term, value) {
  const item = el("div");
  item.append(el("dt", null, term), el("dd", null, value));
  return item;
}

function loadDetail(code) {
  return run("detail-status", async () => {
    const [detail, seats] = await Promise.all([
      getJson(`api/readingrooms/${code}`),
      getJson(`api/readingrooms/${code}/seats`),
    ]);
    const { room, endingSoon } = detail;
    const policy = room.policy;

    $("detail-head").replaceChildren(
      el("span", null, `${room.code} ${room.name}`),
      el("span", `badge ${room.operation}`, OPERATION_LABEL[room.operation] ?? room.operation),
    );
    $("detail-meta").replaceChildren(
      metaItem("좌석", `${room.used} / ${room.total}명 사용, 여유 ${room.available}`),
      metaItem("오늘 운영", `${policy.start} - ${policy.end} (${KIND_LABEL[policy.kind] ?? policy.kind})`),
      metaItem("노트북", policy.notebook ? "허용" : "불가"),
      metaItem("배정 시간", `${policy.hours}시간`),
      metaItem("집계 기준", time(detail.updatedAt)),
      metaItem("좌석 기준", time(seats.updatedAt)),
    );
    $("ending").replaceChildren(
      ...endingSoon.seats.map((seat) =>
        el("span", "chip", `${seat.number}번 · ${seat.remainingMinutes}분`),
      ),
    );
    $("seat-grid").replaceChildren(...seats.seats.map(seatBox));

    $("raw-json").textContent = JSON.stringify({ detail, seats }, null, 2);
    $("raw-json").hidden = true;
    $("raw-toggle").textContent = "raw 응답 보기";
  });
}

$("raw-toggle").addEventListener("click", () => {
  const pre = $("raw-json");
  pre.hidden = !pre.hidden;
  $("raw-toggle").textContent = pre.hidden ? "raw 응답 보기" : "raw 응답 숨기기";
});

$("rooms-refresh").addEventListener("click", loadRooms);

$("seat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = $("seat-result");
  const room = $("seat-room").value;
  const number = encodeURIComponent($("seat-number").value.trim());
  try {
    result.textContent = JSON.stringify(
      await getJson(`api/readingrooms/${room}/seats/${number}`),
      null,
      2,
    );
  } catch (error) {
    result.textContent = `실패: ${error.message}`;
  }
});

$("health").addEventListener("click", () =>
  run("health-status", async () => {
    const data = await getJson("health");
    if (data?.status !== "ok") throw new Error("응답 형식이 다르다");
    return "정상";
  }),
);

/* ----- 혼잡도 통계 ----- */
const SVGNS = "http://www.w3.org/2000/svg";
const WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"];
const REASON_LABEL = {
  closed: "휴실",
  missing: "수집 없음",
  future: "아직 아님",
  outside_retention: "보관 범위 밖",
};
// 사용률 0, 50, 100%를 초록, 호박, 빨강으로 잇는 두 구간 보간이다.
const HEAT_STOPS = [
  [31, 157, 87],
  [199, 119, 0],
  [210, 68, 59],
];
let statsView = "daily";

function svg(tag, attrs) {
  const node = document.createElementNS(SVGNS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, String(value));
  }
  return node;
}

function svgText(attrs, text) {
  const node = svg("text", attrs);
  node.textContent = text;
  return node;
}

function withTitle(node, text) {
  const title = svg("title", {});
  title.textContent = text;
  node.appendChild(title);
  return node;
}

function heatColor(percent) {
  const [low, mid, high] = HEAT_STOPS;
  const [from, to, t] =
    percent <= 50 ? [low, mid, percent / 50] : [mid, high, (percent - 50) / 50];
  const channel = (index) => Math.round(from[index] + (to[index] - from[index]) * t);
  return `rgb(${channel(0)}, ${channel(1)}, ${channel(2)})`;
}

function cellTitle(label, bucket) {
  if (bucket.reason) return `${label} · ${REASON_LABEL[bucket.reason] ?? bucket.reason}`;
  return `${label} · ${bucket.percent}% (표본 ${bucket.samples})`;
}

function statsMeta(data) {
  const parts = [`보관 ${data.retentionDays}일`];
  parts.push(data.firstDate ? `수집 시작 ${data.firstDate}` : "수집 기록 없음");
  parts.push(data.collectionDelayed ? "수집 지연" : "수집 정상");
  if (data.collectionError) parts.push(`오류 ${data.collectionError}`);
  parts.push(`기준 ${time(data.updatedAt)}`);
  $("stats-meta").textContent = parts.join(" · ");
}

function axis(parent, x1, y1, x2, y2) {
  parent.append(svg("line", { x1, y1, x2, y2, class: "axis" }));
}

function barChart(buckets, { labelEvery, labelOf }) {
  const width = 960;
  const height = 240;
  const padX = 34;
  const padY = 16;
  const base = height - 28;
  const span = width - padX - 12;
  const step = span / buckets.length;
  const barW = Math.max(2, step - 3);
  const root = svg("svg", {
    viewBox: `0 0 ${width} ${height}`,
    class: "chart",
    role: "img",
  });

  for (const ratio of [0, 0.5, 1]) {
    const y = base - (base - padY) * ratio;
    axis(root, padX, y, width - 12, y);
    root.append(svgText({ x: 4, y: y + 4, class: "tick" }, `${ratio * 100}`));
  }

  buckets.forEach((bucket, index) => {
    const x = padX + index * step + (step - barW) / 2;
    const label = cellTitle(labelOf(bucket, index), bucket);
    if (bucket.reason) {
      root.append(
        withTitle(
          svg("rect", {
            x,
            y: base - 3,
            width: barW,
            height: 3,
            class: `bar-empty ${bucket.reason}`,
          }),
          label,
        ),
      );
      return;
    }
    const barH = Math.max(1, ((base - padY) * bucket.percent) / 100);
    root.append(
      withTitle(
        svg("rect", {
          x,
          y: base - barH,
          width: barW,
          height: barH,
          rx: 2,
          fill: heatColor(bucket.percent),
        }),
        label,
      ),
    );
  });

  buckets.forEach((bucket, index) => {
    if (index % labelEvery !== 0) return;
    root.append(
      svgText(
        { x: padX + index * step + step / 2, y: height - 6, class: "tick mid" },
        labelOf(bucket, index, true),
      ),
    );
  });
  return root;
}

function renderDaily(data) {
  const chart = barChart(data.hours, {
    labelEvery: 3,
    labelOf: (bucket, index, axisLabel) =>
      axisLabel ? `${index}` : `${bucket.hour}시`,
  });
  $("stats-chart").replaceChildren(chart);
}

function renderMonthly(data) {
  const days = barChart(data.days, {
    labelEvery: 5,
    labelOf: (bucket, index, axisLabel) =>
      axisLabel ? `${index + 1}` : `${bucket.date.slice(5)}`,
  });
  const hours = barChart(data.hours, {
    labelEvery: 3,
    labelOf: (bucket, index, axisLabel) =>
      axisLabel ? `${index}` : `${bucket.hour}시`,
  });
  $("stats-chart").replaceChildren(
    el("h3", "chart-title", "날짜별 일평균"),
    days,
    el("h3", "chart-title", "시간대별 월평균"),
    hours,
  );
}

function renderWeekly(data) {
  const width = 960;
  const cols = 12;
  const rows = 7;
  const padL = 30;
  const padB = 20;
  const cellW = (width - padL) / cols;
  const cellH = 30;
  const height = rows * cellH + padB;
  const root = svg("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart heat" });

  data.days.forEach((day, row) => {
    root.append(
      svgText(
        { x: 0, y: row * cellH + cellH / 2 + 4, class: "tick" },
        WEEKDAY[row],
      ),
    );
    day.slots.forEach((slot, col) => {
      const x = padL + col * cellW;
      const y = row * cellH;
      root.append(
        withTitle(
          svg("rect", {
            x: x + 1,
            y: y + 1,
            width: cellW - 2,
            height: cellH - 2,
            rx: 2,
            fill: slot.reason ? "var(--unknown-bg)" : heatColor(slot.percent),
            class: slot.reason ? `cell-empty ${slot.reason}` : "cell",
          }),
          cellTitle(`${WEEKDAY[row]} ${slot.hour}시`, slot),
        ),
      );
    });
  });

  for (let col = 0; col <= cols; col += 2) {
    root.append(
      svgText(
        { x: padL + col * cellW, y: height - 6, class: "tick mid" },
        `${col * 2}`,
      ),
    );
  }
  $("stats-chart").replaceChildren(root);
}

function renderLegend() {
  const legend = $("stats-legend");
  const scale = el("span", "heat-scale");
  scale.append(el("i", "heat-gradient"), el("small", null, "0% - 100%"));
  legend.replaceChildren(
    scale,
    ...Object.entries(REASON_LABEL).map(([key, label]) => {
      const item = el("span");
      item.append(el("i", `dot empty ${key}`), document.createTextNode(label));
      return item;
    }),
  );
}

const RENDERERS = {
  daily: renderDaily,
  weekly: renderWeekly,
  monthly: renderMonthly,
};

function loadStats() {
  const code = $("stats-room").value;
  const date = $("stats-date").value;
  const query = date ? `?date=${date}` : "";
  return run("stats-status", async () => {
    let data;
    try {
      data = await getJson(`api/readingrooms/${code}/history/${statsView}${query}`);
    } catch (error) {
      $("stats-meta").textContent = "";
      $("stats-legend").replaceChildren();
      $("stats-raw-toggle").hidden = true;
      $("stats-raw-json").hidden = true;
      $("stats-chart").replaceChildren(
        el(
          "p",
          "empty-note",
          error.message.includes("503")
            ? "수집 또는 DB 연결이 꺼져 있어 통계를 제공할 수 없다."
            : `통계를 불러오지 못했다. (${error.message})`,
        ),
      );
      return "제공 불가";
    }
    $("stats-raw-toggle").hidden = false;
    statsMeta(data);
    RENDERERS[statsView](data);
    renderLegend();
    if (data.summary.samples === 0) {
      $("stats-chart").prepend(el("p", "empty-note", "이 기간에 쌓인 데이터가 없다."));
    }
    $("stats-raw-json").textContent = JSON.stringify(data, null, 2);
    $("stats-raw-json").hidden = true;
    $("stats-raw-toggle").textContent = "raw 응답 보기";
    const summary = data.summary;
    return summary.reason
      ? REASON_LABEL[summary.reason] ?? summary.reason
      : `평균 ${summary.percent}%`;
  });
}

$("stats-raw-toggle").addEventListener("click", () => {
  const pre = $("stats-raw-json");
  pre.hidden = !pre.hidden;
  $("stats-raw-toggle").textContent = pre.hidden ? "raw 응답 보기" : "raw 응답 숨기기";
});

for (const tab of document.querySelectorAll("#stats-view .tab")) {
  tab.addEventListener("click", () => {
    statsView = tab.dataset.view;
    for (const other of document.querySelectorAll("#stats-view .tab")) {
      other.setAttribute("aria-pressed", String(other === tab));
    }
    void loadStats();
  });
}

$("stats-form").addEventListener("submit", (event) => {
  event.preventDefault();
  void loadStats();
});

void loadRooms();
void loadStats();
