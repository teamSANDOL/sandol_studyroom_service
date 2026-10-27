import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { currentStudyroom, demoDate, endingSoon, endTime, makeRooms, reservationsFor } from "../app/static/js/mock-data.mjs";

const layouts = JSON.parse(await readFile(new URL("../app/static/data/readingroom-layouts.json", import.meta.url)));
const rooms = makeRooms(layouts);

test("가상 집계는 배치도와 위치 미확인 좌석을 포함한다", () => {
  for (const room of rooms) {
    assert.equal(new Set(room.seats.map(seat => seat.number)).size, room.total);
    if (room.operation === "open") {
      assert.equal(room.seats.filter(seat => seat.status === "occupied").length, room.used);
      assert.equal(room.seats.filter(seat => seat.status === "available").length, room.available);
      assert.equal(room.used + room.available, room.total);
    }
  }
  const c1 = rooms.find(room => room.code === "C1");
  for (const number of ["41", "42", "43", "44"]) {
    assert.ok(c1.seats.some(seat => seat.number === number));
    assert.ok(!layouts.C1.cells.some(cell => cell.seat === number));
  }
});

test("만료 목록은 0분을 보존하고 미확인 시간과 운영 중지를 제외한다", () => {
  const a1 = rooms.find(room => room.code === "A1");
  const ending = endingSoon(a1);
  assert.deepEqual(ending.map(seat => seat.remaining), [0, 4, 9, 16, 24]);
  assert.ok(ending.every(seat => seat.status === "occupied"));
  assert.equal(a1.seats.find(seat => seat.remaining === 0).status, "occupied");
  assert.equal(endTime(0), "14:10");
  assert.equal(endTime(null), "미확인");
  const disabled = rooms.find(room => room.code === "D1");
  assert.deepEqual(endingSoon(disabled), []);
  assert.ok(disabled.seats.every(seat => seat.status === "unknown"));
});

test("현재 상태는 시작 전 예약을 사용 중으로 해석하지 않는다", () => {
  assert.equal(currentStudyroom("1").status, "occupied");
  assert.equal(currentStudyroom("3").status, "available");
  assert.equal(currentStudyroom("3").note, "14:30 예약 예정");
});

test("예약 날짜가 달라져도 현재 상태는 유지하고 일정만 바꾼다", () => {
  const tomorrow = new Date(Date.parse(`${demoDate}T00:00:00Z`) + 86400000).toISOString().slice(0, 10);
  const current = currentStudyroom("1");
  const todayRecords = reservationsFor(demoDate);
  const tomorrowRecords = reservationsFor(tomorrow);
  assert.notDeepEqual(todayRecords, tomorrowRecords);
  assert.deepEqual(currentStudyroom("1"), current);
  for (const record of tomorrowRecords) {
    assert.ok(Number(record.room) >= 1 && Number(record.room) <= 6);
    assert.ok(record.start >= 9 && record.end <= 21 && record.end > record.start);
  }
});
