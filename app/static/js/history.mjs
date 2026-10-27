import { demoDate } from "./mock-data.mjs";
import { dailyHistory, firstDate, reasonLabels, shiftDate, weeklyHistory, weekStart } from "./mock-history.mjs";
import { node } from "./readingroom.mjs";

function svgNode(tag, attributes = {}, text) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (text !== undefined) element.textContent = text;
  return element;
}

function metric(label, value) {
  const item = node("div", "trend-metric");
  item.append(node("span", "", label), node("strong", "", value));
  return item;
}

function pointLabel(date, point, duration) {
  const range = `${String(point.hour).padStart(2, "0")}:00 - ${String(point.hour + duration).padStart(2, "0")}:00`;
  return `${date}, ${range}: ${point.percent === null ? reasonLabels[point.reason] : `평균 사용률 ${point.percent}%, 예시 표본 ${point.samples}개`}`;
}

export function mountHistory() {
  const el = id => document.getElementById(id);
  const input = el("history-date");
  input.min = firstDate;
  input.max = demoDate;
  input.value = demoDate;
  let selectedDate = demoDate;
  let room = null;

  function chooseDate(date) {
    const valid = /^\d{4}-\d{2}-\d{2}$/.test(date) && Number.isFinite(Date.parse(`${date}T00:00:00Z`))
      && date >= firstDate && date <= demoDate && shiftDate(date, 0) === date;
    if (!valid) {
      el("history-date-message").hidden = false;
      el("history-date-message").textContent = `${firstDate}부터 ${demoDate}까지의 날짜를 선택하라.`;
      input.value = selectedDate;
      return;
    }
    selectedDate = date;
    input.value = date;
    el("history-date-message").hidden = true;
    render();
  }

  function renderLine(data) {
    const svg = svgNode("svg", { viewBox: "0 0 720 280", role: "group", "aria-label": `${room.name} ${data.date} 가상 시간별 평균 사용률` });
    svg.append(svgNode("title", {}, "24시간 추이. 기록이 없는 구간은 연결하지 않는다."));
    const x = hour => 54 + hour / 23 * 632;
    const y = percent => 220 - percent * 1.8;
    for (const percent of [0, 25, 50, 75, 100]) {
      svg.append(svgNode("line", { x1: 54, x2: 686, y1: y(percent), y2: y(percent), class: "chart-grid" }));
      svg.append(svgNode("text", { x: 44, y: y(percent) + 4, "text-anchor": "end", class: "chart-axis" }, `${percent}%`));
    }
    for (const hour of [0, 6, 12, 18, 23]) svg.append(svgNode("text", { x: x(hour), y: 251, "text-anchor": "middle", class: "chart-axis" }, `${hour}시`));
    let segment = [];
    const flush = () => {
      if (segment.length > 1) svg.append(svgNode("polyline", { points: segment.join(" "), class: "chart-line", fill: "none" }));
      segment = [];
    };
    for (const point of data.hours) {
      if (point.percent === null) { flush(); continue; }
      segment.push(`${x(point.hour)},${y(point.percent)}`);
    }
    flush();
    for (const point of data.hours) {
      const label = pointLabel(data.date, point, 1);
      const group = svgNode("g", { class: `chart-point${point.percent === null ? " chart-no-data" : ""}`, role: "button", tabindex: "0", "aria-label": label, "aria-pressed": "false" });
      group.append(svgNode("title", {}, label));
      const cy = point.percent === null ? 220 : y(point.percent);
      group.append(svgNode("circle", { cx: x(point.hour), cy, r: 12, class: "chart-hit-target" }));
      group.append(svgNode("circle", { cx: x(point.hour), cy, r: point.percent === null ? 3 : 4, class: "chart-dot" }));
      const show = () => {
        svg.querySelectorAll("[role='button']").forEach(item => item.setAttribute("aria-pressed", String(item === group)));
        el("daily-readout").textContent = label;
      };
      group.addEventListener("click", show);
      group.addEventListener("focus", show);
      group.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); show(); }
      });
      svg.append(group);
    }
    el("daily-chart").replaceChildren(svg);
  }

  function renderDaily(data) {
    el("daily-date").textContent = `${data.date}, 24시간 기준`;
    const recorded = data.hours.filter(point => point.percent !== null);
    const highest = recorded.reduce((best, point) => !best || point.percent > best.percent ? point : best, null);
    const lowest = recorded.reduce((best, point) => !best || point.percent < best.percent ? point : best, null);
    el("daily-stats").replaceChildren(
      metric("하루 평균", data.summary.percent === null ? "기록 없음" : `${data.summary.percent}%`),
      metric("최고 사용률", highest ? `${highest.percent}% (${highest.hour}시)` : "기록 없음"),
      metric("최저 사용률", lowest ? `${lowest.percent}% (${lowest.hour}시)` : "기록 없음"),
    );
    el("daily-chart-wrap").hidden = !recorded.length;
    el("daily-empty").hidden = !!recorded.length;
    el("daily-empty").textContent = room.code === "D1" ? "멀티미디어실은 혼잡도 기록 대상이 아니다." : "운영 중 예시 관측이 없다. 휴실과 미수집은 0%로 해석하지 않는다.";
    el("daily-readout").textContent = room.code === "D1" ? "A1, A2, C1, E1의 추이를 제공한다." : `${recorded.length}개 시간 구간, 예시 표본 ${data.summary.samples}개. 점을 선택해 구간별 값을 확인하라.`;
    renderLine(data);
  }

  function renderWeekly(data) {
    el("weekly-range").textContent = `${data.start} - ${data.end}, 월요일부터 일요일`;
    const recorded = data.days.filter(day => day.summary.percent !== null);
    const busiest = recorded.reduce((best, day) => !best || day.summary.percent > best.summary.percent ? day : best, null);
    el("weekly-stats").replaceChildren(
      metric("주간 평균", data.summary.percent === null ? "기록 없음" : `${data.summary.percent}%`),
      metric("가장 혼잡한 날", busiest ? `${busiest.date.slice(5)} (${busiest.summary.percent}%)` : "기록 없음"),
      metric("예시 표본", `${data.summary.samples.toLocaleString("ko-KR")}개`),
    );
    const unsupported = room.code === "D1";
    el("weekly-grid-wrap").hidden = unsupported;
    el("weekly-empty").hidden = !unsupported;
    el("weekly-empty").textContent = "멀티미디어실은 혼잡도 기록 대상이 아니다.";
    el("heatmap-caption").textContent = `${room.name} 가상 주간 사용률, 2시간 구간`;
    const head = node("tr");
    const label = node("th", "", "날짜 / 시간");
    label.scope = "col";
    head.append(label);
    for (let hour = 0; hour < 24; hour += 2) {
      const cell = node("th", "", `${hour}시`);
      cell.scope = "col";
      head.append(cell);
    }
    el("heatmap-head").replaceChildren(head);
    el("heatmap-body").replaceChildren();
    for (const day of data.days) {
      const row = node("tr", day.date === input.value ? "selected-day" : "");
      const header = node("th");
      header.scope = "row";
      const weekday = new Intl.DateTimeFormat("ko-KR", { weekday: "short", timeZone: "UTC" }).format(new Date(`${day.date}T00:00:00Z`));
      const dateButton = node("button", "heatmap-date", `${day.date.slice(5)} (${weekday})`);
      dateButton.type = "button";
      dateButton.disabled = day.date > demoDate || day.date < firstDate || unsupported;
      dateButton.setAttribute("aria-label", `${day.date} 일간 추이 보기`);
      dateButton.setAttribute("aria-pressed", String(day.date === input.value));
      dateButton.addEventListener("click", () => { chooseDate(day.date); input.focus({ preventScroll: true }); });
      header.append(dateButton);
      row.append(header);
      for (const slot of day.slots) {
        const cell = node("td");
        const button = node("button", `heat-cell${slot.percent === null ? ` heat-${slot.reason}` : ""}`, slot.percent === null ? reasonLabels[slot.reason] : `${slot.percent}%`);
        button.type = "button";
        if (slot.percent !== null) button.dataset.level = String(Math.min(4, Math.floor(slot.percent / 20)));
        const text = pointLabel(day.date, slot, 2);
        button.title = text;
        button.setAttribute("aria-label", text);
        button.setAttribute("aria-pressed", "false");
        button.addEventListener("click", () => {
          el("heatmap-body").querySelectorAll(".heat-cell").forEach(item => item.setAttribute("aria-pressed", String(item === button)));
          el("weekly-readout").textContent = text;
        });
        cell.append(button);
        row.append(cell);
      }
      el("heatmap-body").append(row);
    }
    el("weekly-readout").textContent = unsupported ? "A1, A2, C1, E1의 추이를 제공한다." : "요일별 날짜를 누르면 일간 추이가 바뀐다. 칸을 선택하면 2시간 구간의 사용률을 확인한다.";
  }

  function render() {
    if (!room) return;
    const date = selectedDate;
    el("history-room").textContent = `${room.name}, 가상 분 단위 관측을 집계한 예시다.`;
    el("history-previous").disabled = date <= firstDate;
    el("history-next").disabled = date >= demoDate;
    el("week-previous").disabled = weekStart(date) <= weekStart(firstDate);
    el("week-next").disabled = weekStart(date) >= weekStart(demoDate);
    renderDaily(dailyHistory(room, date));
    renderWeekly(weeklyHistory(room, date));
  }

  input.addEventListener("change", () => chooseDate(input.value));
  el("history-previous").addEventListener("click", () => chooseDate(shiftDate(input.value, -1)));
  el("history-next").addEventListener("click", () => chooseDate(shiftDate(input.value, 1)));
  const changeWeek = direction => chooseDate([firstDate, shiftDate(input.value, direction * 7), demoDate].sort()[1]);
  el("week-previous").addEventListener("click", () => changeWeek(-1));
  el("week-next").addEventListener("click", () => changeWeek(1));
  return { chooseRoom(nextRoom) { room = nextRoom; render(); } };
}
