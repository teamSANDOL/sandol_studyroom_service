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
    const data = await getJson("api/readingrooms");
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

void loadRooms();
