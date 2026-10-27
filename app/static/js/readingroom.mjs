import { demoDate, endingSoon, endTime } from "./mock-data.mjs";

export function node(tag, className = "", text) {
  const element = document.createElement(tag);
  element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
const labels = { available: "빈 좌석", occupied: "사용 중", unknown: "미확인" };

export function mountReadingrooms(rooms, layouts, onRoomChange = () => {}) {
  const el = id => document.getElementById(id);
  let active = rooms[0].code;
  let selected = null;
  let filter = "all";
  const currentRoom = () => rooms.find(room => room.code === active);
  const roomButtons = new Map();
  const openRooms = rooms.filter(room => room.operation === "open");
  el("reading-summary").textContent = `운영 중 공간의 빈 좌석 ${openRooms.reduce((sum, room) => sum + room.available, 0)}석`;

  for (const room of rooms) {
    const button = node("button", `room-card${room.operation === "open" ? "" : " room-card-disabled"}`);
    button.type = "button";
    button.dataset.room = room.code;
    button.setAttribute("aria-controls", "seat-map");
    const name = node("span", "room-name", room.name);
    const status = node("span", `badge badge-${room.operation}`, room.operation === "open" ? "운영 중" : "운영 중지");
    const header = node("span", "room-card-header");
    header.append(name, status);
    button.append(header);
    if (room.operation === "open") {
      const metric = node("span", "room-metric");
      metric.append(node("strong", "", `${Math.round(room.used / room.total * 100)}%`), node("span", "", "사용률"));
      const track = node("span", "occupancy-track");
      track.setAttribute("aria-hidden", "true");
      const fill = node("span", "occupancy-fill");
      fill.style.width = `${room.used / room.total * 100}%`;
      track.append(fill);
      button.append(metric, track, node("span", "room-foot", `빈 좌석 ${room.available} / ${room.total}석`));
    } else {
      button.append(node("span", "closed-label", "이용 불가"), node("span", "room-foot", "배치도만 확인한다"));
    }
    button.setAttribute("aria-label", `${room.name}, ${room.operation === "open" ? `사용률 ${Math.round(room.used / room.total * 100)}%, 빈 좌석 ${room.available}석` : "운영 중지"}, 배치도 보기`);
    button.addEventListener("click", () => {
      active = room.code;
      selected = null;
      el("seat-search").value = "";
      renderMap();
      el("map-scroll").scrollTo(0, 0);
      onRoomChange(room);
    });
    roomButtons.set(room.code, button);
    el("readingroom-list").append(button);
  }

  function seatButton(seat) {
    const button = node("button", `seat seat-${seat.status}`, seat.number);
    button.type = "button";
    button.dataset.seat = seat.number;
    button.setAttribute("aria-pressed", String(selected === seat.number));
    const soon = Number.isFinite(seat.remaining) && seat.remaining <= 30;
    if (seat.status === "occupied" && soon) button.classList.add("seat-ending");
    const remaining = seat.status === "occupied" ? `, 잔여 ${seat.remaining === null ? "미확인" : `${seat.remaining}분`}` : "";
    button.setAttribute("aria-label", `${seat.number}번 좌석, ${labels[seat.status]}${remaining}`);
    button.title = button.getAttribute("aria-label");
    button.addEventListener("click", () => selectSeat(seat.number));
    return button;
  }

  function renderMap() {
    const room = currentRoom();
    const layout = layouts[active];
    roomButtons.forEach((button, code) => button.setAttribute("aria-pressed", String(code === active)));
    el("map-title").textContent = `${room.name} 배치도`;
    el("room-meta").textContent = room.operation === "open"
      ? `전체 ${room.total}석, 사용 중 ${room.used}석, 빈 좌석 ${room.available}석 / 노트북 ${room.notebook ? "허용" : "불가"}`
      : "운영 중지 공간이다. 좌석 상태는 미확인으로 표시한다.";
    const map = el("seat-map");
    map.replaceChildren();
    map.classList.toggle("free-only", filter === "available");
    map.style.gridTemplateColumns = `repeat(${layout.columns}, 28px)`;
    map.style.gridTemplateRows = `repeat(${layout.rows}, 28px)`;
    const seats = new Map(room.seats.map(seat => [seat.number, seat]));
    const placed = new Set();
    for (const cell of layout.cells) {
      const item = cell.seat !== null ? seatButton(seats.get(cell.seat)) : node("span", "map-label", cell.label);
      if (cell.seat !== null) placed.add(cell.seat);
      item.style.gridColumn = `${cell.x + 1} / span ${cell.w}`;
      item.style.gridRow = `${cell.y + 1} / span ${cell.h}`;
      map.append(item);
    }
    const missing = room.seats.filter(seat => !placed.has(seat.number));
    const unmapped = el("unmapped-seats");
    unmapped.replaceChildren();
    unmapped.hidden = !missing.length;
    if (missing.length) {
      unmapped.append(node("p", "panel-note", `위치 미확인 ${missing.length}석: PoC 배치도에 위치가 없는 좌석이다.`));
      const group = node("div", `unmapped-list${filter === "available" ? " free-only" : ""}`);
      group.append(...missing.map(seatButton));
      unmapped.append(group);
    }
    const ending = el("ending-seats");
    ending.replaceChildren();
    const endingSeats = endingSoon(room);
    for (const seat of endingSeats) {
      const item = node("li");
      const button = node("button", "ending-seat");
      button.type = "button";
      button.dataset.endingSeat = seat.number;
      button.setAttribute("aria-pressed", String(selected === seat.number));
      const text = node("span", "ending-label");
      text.append(node("strong", "", `${seat.number}번 좌석`), node("span", "", `${endTime(seat.remaining)} 배정 종료 예정`));
      button.append(text, node("span", "expiry", seat.remaining === 0 ? "만료 시점" : `${seat.remaining}분 남음`));
      button.addEventListener("click", () => selectSeat(seat.number, true));
      item.append(button);
      ending.append(item);
    }
    if (!endingSeats.length) ending.append(node("li", "empty-note", room.operation === "open" ? "30분 이내 만료 예정 좌석이 없다." : "운영 중지 공간이다."));
    renderDetail();
  }

  function renderDetail() {
    const room = currentRoom();
    const seat = room.seats.find(seat => seat.number === selected);
    const detail = el("seat-detail");
    detail.replaceChildren();
    if (!seat) {
      detail.append(node("p", "empty-note", "배치도나 만료 목록에서 좌석을 선택하라."));
      return;
    }
    const heading = node("div", "selection-heading");
    heading.append(node("strong", "", `${seat.number}번 좌석`), node("span", `badge badge-${seat.status}`, labels[seat.status]));
    const facts = node("dl", "seat-facts");
    const fact = (label, value) => { facts.append(node("dt", "", label), node("dd", "", value)); };
    fact("좌석 이름", seat.name);
    fact("예시 기준", `${demoDate} 14:10`);
    if (seat.status === "occupied") {
      fact("잔여 시간", seat.remaining === null ? "미확인" : seat.remaining === 0 ? "배정 시간 만료" : `${seat.remaining}분`);
      fact("종료 예정", endTime(seat.remaining));
    }
    detail.append(heading, facts);
    detail.append(node("p", "panel-note", room.operation !== "open" ? "운영 중지 공간의 좌석은 이용 가능으로 해석하지 않는다." : seat.status === "occupied" ? "잔여 시간이 0분이어도 빈 좌석으로 확정하지 않는다. 실제 배정 상태는 달라질 수 있다." : "예시 상태다. 실제 좌석 배정은 공식 사이트에서 확인한다."));
  }

  function selectSeat(number, focus = false) {
    const seat = currentRoom().seats.find(seat => seat.number === number);
    if (!seat) {
      el("seat-detail").replaceChildren(node("p", "error-note", `${number || "입력한 번호"}번 좌석이 없다. 좌석 번호를 다시 확인하라.`));
      return;
    }
    selected = number;
    document.querySelectorAll("[data-seat], [data-ending-seat]").forEach(button => {
      const match = (button.dataset.seat || button.dataset.endingSeat) === number;
      button.setAttribute("aria-pressed", String(match));
      if (match && focus && button.dataset.seat) {
        button.scrollIntoView({ block: "nearest", inline: "center" });
        button.focus({ preventScroll: true });
      }
    });
    renderDetail();
  }

  el("seat-search-form").addEventListener("submit", event => {
    event.preventDefault();
    selectSeat(el("seat-search").value.trim().replace(/^0+(?=\d)/, ""), true);
  });
  document.querySelectorAll("[data-filter]").forEach(button => button.addEventListener("click", () => {
    filter = button.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach(item => item.setAttribute("aria-pressed", String(item === button)));
    renderMap();
  }));
  renderMap();
  onRoomChange(currentRoom());
}
