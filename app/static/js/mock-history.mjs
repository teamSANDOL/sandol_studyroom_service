import { demoDate } from "./mock-data.mjs";

const dayMs = 86400000;
export const firstDate = shiftDate(demoDate, -89);
export const reasonLabels = {
  closed: "휴실", missing: "미수집", future: "미래", outside_retention: "보관 범위 밖", unsupported: "기록 대상 아님",
};

export function shiftDate(date, days) {
  return new Date(Date.parse(`${date}T00:00:00Z`) + days * dayMs).toISOString().slice(0, 10);
}

export function weekStart(date) {
  const weekday = new Date(`${date}T00:00:00Z`).getUTCDay();
  return shiftDate(date, -((weekday + 6) % 7));
}

function empty(reason) {
  return { percent: null, samples: 0, sum: 0, reason };
}

function aggregate(points) {
  const samples = points.reduce((sum, point) => sum + point.samples, 0);
  const sum = points.reduce((value, point) => value + point.sum, 0);
  if (samples) return { percent: Math.floor(sum / samples + 0.5), samples, sum, reason: null };
  const reasons = new Set(points.map(point => point.reason));
  const reason = ["unsupported", "outside_retention", "missing", "closed", "future"].find(value => reasons.has(value));
  return empty(reason || "missing");
}

export function dailyHistory(room, date) {
  const day = Math.floor(Date.parse(`${date}T00:00:00Z`) / dayMs);
  const seed = [...room.code].reduce((sum, letter) => sum + letter.charCodeAt(0), 0);
  const hours = Array.from({ length: 24 }, (_, hour) => {
    let reason = null;
    if (room.code === "D1") reason = "unsupported";
    else if (date < firstDate) reason = "outside_retention";
    else if (date > demoDate || date === demoDate && hour > 14) reason = "future";
    else if (hour < 7 || hour >= 23) reason = "closed";
    else if ((day + hour + seed) % 23 === 0) reason = "missing";
    if (reason) return { hour, ...empty(reason) };
    const samples = date === demoDate && hour === 14 ? 11 : 60;
    let sum = 0;
    for (let minute = 0; minute < samples; minute++) {
      const shape = Math.sin((hour - 7) / 16 * Math.PI) * 28 - 13;
      const variation = ((day + seed) % 13) - 6 + ((minute * 7 + hour * 3 + seed) % 9) - 4;
      const ratio = Math.max(0, Math.min(100, room.ratio * 100 + shape + variation));
      const used = Math.round(room.total * ratio / 100);
      sum += used / room.total * 100;
    }
    return { hour, percent: Math.floor(sum / samples + 0.5), samples, sum, reason: null };
  });
  const slots = Array.from({ length: 12 }, (_, index) => ({ hour: index * 2, ...aggregate(hours.slice(index * 2, index * 2 + 2)) }));
  return { date, hours, slots, summary: aggregate(hours) };
}

export function weeklyHistory(room, date) {
  const start = weekStart(date);
  const days = Array.from({ length: 7 }, (_, index) => dailyHistory(room, shiftDate(start, index)));
  return { start, end: shiftDate(start, 6), days, summary: aggregate(days.map(day => day.summary)) };
}
