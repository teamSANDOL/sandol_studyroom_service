const koreaDate = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit",
}).format(new Date());

export const demoDate = koreaDate;
export const demoAt = new Date(`${demoDate}T14:10:00+09:00`);
const roomDefinitions = [
  { code: "A1", name: "제1일반열람실", ratio: 0.27, notebook: false },
  { code: "A2", name: "제2일반열람실", ratio: 0.59, notebook: false },
  { code: "C1", name: "자료열람실", ratio: 0.41, notebook: false },
  { code: "E1", name: "노트북열람실", ratio: 0.66, notebook: true },
  { code: "D1", name: "멀티미디어실", ratio: 0, notebook: true, disabled: true },
];

export function makeRooms(layouts) {
  return roomDefinitions.map((definition) => {
    const numbers = layouts[definition.code].cells.filter(cell => cell.seat !== null).map(cell => cell.seat);
    // PoC의 C1 배치도에는 41번부터 44번의 위치가 없다.
    if (definition.code === "C1") numbers.push("41", "42", "43", "44");
    numbers.sort((a, b) => Number(a) - Number(b));
    const total = numbers.length;
    const used = Math.round(total * definition.ratio);
    const shuffled = [...numbers].sort((a, b) => (Number(a) * 37 % 101) - (Number(b) * 37 % 101) || Number(a) - Number(b));
    const occupied = new Map(shuffled.slice(0, used).map((number, index) => [number, index]));
    const soon = [4, 9, 16, 24, 0, null];
    const seats = numbers.map(number => {
      const index = occupied.get(number);
      return {
        number, name: `${definition.code}-${number.padStart(3, "0")}`,
        status: definition.disabled ? "unknown" : index === undefined ? "available" : "occupied",
        remaining: index === undefined ? null : index < soon.length ? soon[index] : 40 + (index * 13 % 190),
      };
    });
    return { ...definition, total, used, available: total - used, operation: definition.disabled ? "disabled" : "open", seats };
  });
}

export function endingSoon(room) {
  if (room.operation !== "open") return [];
  return room.seats.filter(seat => seat.status === "occupied" && Number.isFinite(seat.remaining) && seat.remaining >= 0 && seat.remaining <= 30)
    .sort((a, b) => a.remaining - b.remaining || Number(a.number) - Number(b.number));
}

export function endTime(minutes) {
  if (!Number.isFinite(minutes)) return "미확인";
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).format(new Date(demoAt.getTime() + minutes * 60000));
}

export const reservationExamples = [
  { room: "1", start: 9, end: 11 }, { room: "1", start: 13, end: 15 },
  { room: "2", start: 10, end: 12 }, { room: "2", start: 16, end: 18 },
  { room: "3", start: 14, end: 16 }, { room: "3", start: 18, end: 20 },
  { room: "4", start: 11, end: 13 }, { room: "4", start: 18, end: 20 },
  { room: "5", start: 13, end: 16 }, { room: "5", start: 19, end: 21 },
  { room: "6", start: 10, end: 12 }, { room: "6", start: 17, end: 19 },
];

export function reservationsFor(date) {
  const offset = Math.round((Date.parse(`${date}T00:00:00Z`) - Date.parse(`${demoDate}T00:00:00Z`)) / 86400000);
  return reservationExamples.map(record => ({ ...record, room: String((Number(record.room) - 1 + offset) % 6 + 1) }));
}

export function currentStudyroom(number) {
  const minutes = 14 * 60 + 10;
  const records = reservationExamples.filter(record => record.room === number);
  const current = records.find(record => record.start * 60 + 30 <= minutes && minutes < record.end * 60 + 20);
  const next = records.find(record => record.start * 60 + 30 > minutes);
  return current
    ? { status: "occupied", note: `${String(current.end).padStart(2, "0")}:20까지 사용 중` }
    : { status: "available", note: next ? `${String(next.start).padStart(2, "0")}:30 예약 예정` : "이후 예시 예약 없음" };
}
