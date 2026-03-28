"use client";

import { useEffect } from "react";

const MQ = "(max-width: 900px)";

/**
 * Только для страницы регистрации. На узких экранах: зелёный фон у html/body (без белых полос)
 * и блокировка скролла документа. На входе (/login) не используется.
 */
export function AuthViewportLock() {
  useEffect(() => {
    const mq = window.matchMedia(MQ);

    function apply() {
      if (!mq.matches) {
        document.documentElement.classList.remove("auth-mobile");
        document.body.classList.remove("auth-mobile");
        return;
      }
      document.documentElement.classList.add("auth-mobile");
      document.body.classList.add("auth-mobile");
    }

    apply();
    mq.addEventListener("change", apply);
    return () => {
      mq.removeEventListener("change", apply);
      document.documentElement.classList.remove("auth-mobile");
      document.body.classList.remove("auth-mobile");
    };
  }, []);

  return null;
}
