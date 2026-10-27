import { makeRooms } from "./mock-data.mjs";
import { mountReadingrooms } from "./readingroom.mjs";
import { mountStudyrooms } from "./studyroom.mjs";
import { mountHistory } from "./history.mjs";

mountStudyrooms();

async function loadReadingrooms() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(new URL("../data/readingroom-layouts.json", import.meta.url), {
      cache: "no-store", signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Layout HTTP ${response.status}`);
    const layouts = await response.json();
    const history = mountHistory();
    mountReadingrooms(makeRooms(layouts), layouts, history.chooseRoom);
  } catch {
    const message = document.getElementById("page-error");
    message.hidden = false;
    message.textContent = "좌석 배치도를 불러오지 못했다. 페이지를 새로고침해 다시 시도하라.";
  } finally {
    clearTimeout(timeout);
  }
}

void loadReadingrooms();

const healthButton = document.getElementById("health-button");
const healthMessage = document.getElementById("health-message");

healthButton.addEventListener("click", async () => {
  healthButton.disabled = true;
  healthButton.textContent = "확인 중";
  healthMessage.dataset.state = "loading";
  healthMessage.textContent = "서버 응답을 기다리는 중이다.";
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(new URL("health", document.baseURI), {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      healthMessage.dataset.state = "error";
      healthMessage.textContent = `서버가 HTTP ${response.status}로 응답했다. 잠시 후 다시 확인하라.`;
      return;
    }
    let data;
    try {
      data = await response.json();
    } catch (error) {
      if (controller.signal.aborted) throw error;
      healthMessage.dataset.state = "error";
      healthMessage.textContent = "서버 응답을 해석하지 못했다. 응답 형식을 확인하라.";
      return;
    }
    if (data?.status !== "ok") {
      healthMessage.dataset.state = "error";
      healthMessage.textContent = "서버 응답이 예상한 형식과 다르다. /health 응답을 확인하라.";
      return;
    }
    healthMessage.dataset.state = "success";
    healthMessage.textContent = "서버가 정상 응답했다. 프로세스 생존을 확인했다.";
  } catch {
    healthMessage.dataset.state = "error";
    healthMessage.textContent = controller.signal.aborted
      ? "서버가 5초 안에 응답하지 않았다. 잠시 후 다시 확인하라."
      : "서버에 연결하지 못했다. 서버 실행 상태를 확인하고 다시 시도하라.";
  } finally {
    clearTimeout(timeout);
    healthButton.disabled = false;
    healthButton.textContent = "서버 상태 확인";
  }
});
