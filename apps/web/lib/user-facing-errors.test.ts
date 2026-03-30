import { describe, expect, it } from "vitest";
import { getUserFacingMessage } from "./user-facing-errors";

describe("getUserFacingMessage", () => {
  it("hides 5xx and proxy errors", () => {
    const msg = "Не удалось отправить письмо с кодом: The invision.kz domain is not verified";
    expect(getUserFacingMessage(500, msg)).toMatch(/Сервис временно недоступен/);
    expect(getUserFacingMessage(502, msg)).toMatch(/Сервис временно недоступен/);
    expect(getUserFacingMessage(503, msg)).toMatch(/Сервис временно недоступен/);
  });

  it("strips resend URLs from client-visible path", () => {
    const raw =
      "Не удалось отправить письмо с кодом: Please verify https://resend.com/domains";
    expect(getUserFacingMessage(400, raw)).toMatch(/Запрос не выполнен|Попробуйте позже/);
  });

  it("keeps short safe 400 messages", () => {
    expect(getUserFacingMessage(400, "Некорректная ссылка на документ")).toBe(
      "Некорректная ссылка на документ",
    );
  });

  it("maps 409 without echoing backend", () => {
    expect(getUserFacingMessage(409, "anything from server")).toBe("Этот email уже зарегистрирован.");
  });
});
