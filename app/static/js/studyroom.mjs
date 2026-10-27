import { currentStudyroom, demoDate, reservationsFor } from "./mock-data.mjs";
import { node } from "./readingroom.mjs";

export function mountStudyrooms() {
  const el = id => document.getElementById(id);
  el("demo-clock").textContent = `가상 현재 ${demoDate} 14:10`;
  for (let number = 1; number <= 6; number++) {
    const current = currentStudyroom(String(number));
    const card = node("article", "studyroom-card");
    card.append(
      node("h3", "", `스터디룸 ${number}`),
      node("span", `badge badge-${current.status}`, current.status === "occupied" ? "사용 중" : "현재 비어 있음"),
      node("p", "", current.note),
    );
    el("studyroom-list").append(card);
  }
  const dates = Array.from({ length: 10 }, (_, offset) => new Date(Date.parse(`${demoDate}T00:00:00Z`) + offset * 86400000).toISOString().slice(0, 10));
  for (const date of dates) {
    const option = node("option", "", `${date}${date === demoDate ? " (오늘)" : ""}`);
    option.value = date;
    el("study-date").append(option);
  }
  let selectedSlot = null;

  function renderSchedule() {
    const date = el("study-date").value;
    const records = reservationsFor(date);
    el("schedule-date").textContent = `${date} 예시 예약표 / 09:30 - 21:20`;
    el("schedule-caption").textContent = `${date} 스터디룸 예시 예약 시간표`;
    el("schedule-body").replaceChildren();
    selectedSlot = null;
    el("study-detail").textContent = "시간표의 칸을 선택하면 예약 범위를 확인한다.";
    for (let hour = 9; hour < 21; hour++) {
      const row = node("tr", date === demoDate && hour === 13 ? "current-slot" : "");
      const header = node("th", "", `${String(hour).padStart(2, "0")}:30 - ${String(hour + 1).padStart(2, "0")}:20`);
      header.scope = "row";
      if (date === demoDate && hour === 13) header.append(node("span", "now-label", "가상 현재"));
      row.append(header);
      for (let room = 1; room <= 6; room++) {
        const record = records.find(record => record.room === String(room) && record.start <= hour && record.end > hour);
        const cell = node("td");
        const button = node("button", `schedule-cell${record ? " booked" : ""}`, record ? "예약" : "기록 없음");
        button.type = "button";
        button.dataset.slot = `${room}-${hour}`;
        button.setAttribute("aria-pressed", "false");
        button.setAttribute("aria-label", `${date} ${room}번방 ${hour}:30, ${record ? "예약 기록" : "기록 없음"}, 상세 보기`);
        button.addEventListener("click", () => {
          selectedSlot = button.dataset.slot;
          el("schedule-body").querySelectorAll("button").forEach(item => item.setAttribute("aria-pressed", String(item.dataset.slot === selectedSlot)));
          el("study-detail").textContent = record
            ? `${date}, 스터디룸 ${room}: ${String(record.start).padStart(2, "0")}:30 - ${String(record.end).padStart(2, "0")}:20 예시 예약. 실제 예약 기록은 아니다.`
            : `${date}, 스터디룸 ${room}: ${hour}:30 - ${hour + 1}:20 예시 기록 없음. 실제 예약 가능 여부는 공식 사이트에서 확인한다.`;
        });
        cell.append(button);
        row.append(cell);
      }
      el("schedule-body").append(row);
    }
  }
  el("study-date").addEventListener("change", renderSchedule);
  renderSchedule();
}
