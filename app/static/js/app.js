const TIMEOUT_MS = 5000;
const $ = (id) => document.getElementById(id);

async function getJson(path) {
  const response = await fetch(new URL(path, document.baseURI), {
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(`HTTP ${response.status} ${body?.code ?? ""}`.trim());
  return body;
}

function time(iso) {
  return iso ? new Date(iso).toLocaleTimeString("ko-KR") : "-";
}

function cell(row, text) {
  row.insertCell().textContent = text;
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

function loadRooms() {
  return run("rooms-status", async () => {
    const data = await getJson("api/readingrooms");
    const body = $("rooms");
    body.replaceChildren();
    for (const room of data.rooms) {
      const row = body.insertRow();
      for (const value of [room.code, room.name, room.total, room.used, room.available, room.operation]) {
        cell(row, value);
      }
      row.addEventListener("click", () => loadDetail(room.code));
    }
    return `기준 ${time(data.updatedAt)}`;
  });
}

function loadDetail(code) {
  return run("detail-status", async () => {
    const [detail, seats] = await Promise.all([
      getJson(`api/readingrooms/${code}`),
      getJson(`api/readingrooms/${code}/seats`),
    ]);
    const { room, endingSoon } = detail;
    const policy = room.policy;
    const ending = endingSoon.seats.map((seat) => `${seat.number}번 ${seat.remainingMinutes}분`).join(", ") || "없음";
    const lines = [
      `${room.code} ${room.name}: ${room.used}/${room.total} 사용, ${room.operation}`,
      `오늘 운영 ${policy.start} - ${policy.end} (${policy.kind}), 노트북 ${policy.notebook ? "허용" : "불가"}, 배정 ${policy.hours}시간`,
      `${endingSoon.withinMinutes}분 안에 반납 예정: ${ending}`,
      `집계 기준 ${time(detail.updatedAt)}, 좌석 기준 ${time(seats.updatedAt)}`,
    ];
    $("detail").replaceChildren(...lines.map((line) => {
      const p = document.createElement("p");
      p.textContent = line;
      return p;
    }));
    $("seat-grid").replaceChildren(...seats.seats.map((seat) => {
      const box = document.createElement("span");
      box.className = `seat ${seat.status}`;
      box.textContent = seat.number;
      box.title = seat.remainingMinutes === null ? seat.name : `${seat.name} 남은 ${seat.remainingMinutes}분`;
      return box;
    }));
  });
}

$("rooms-refresh").addEventListener("click", loadRooms);

$("seat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = $("seat-result");
  try {
    const data = await getJson(`api/readingrooms/${$("seat-room").value}/seats/${encodeURIComponent($("seat-number").value.trim())}`);
    result.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    result.textContent = `실패: ${error.message}`;
  }
});

$("health").addEventListener("click", () => run("health-status", async () => {
  const data = await getJson("health");
  if (data?.status !== "ok") throw new Error("응답 형식이 다르다");
  return "정상";
}));

void loadRooms();
