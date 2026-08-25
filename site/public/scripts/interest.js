const form = document.querySelector("[data-interest-form]");

if (form instanceof HTMLFormElement) {
  const status = form.querySelector("[data-form-status]");
  const submit = form.querySelector('button[type="submit"]');
  const email = form.querySelector('input[name="email"]');

  if (
    new URLSearchParams(window.location.search).get("joined") === "1" &&
    status instanceof HTMLElement
  ) {
    status.dataset.state = "success";
    status.textContent = "You’re on the hosted Atpiano interest list. Thank you.";
    window.history.replaceState(null, "", `${window.location.pathname}#hosted`);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (
      !form.reportValidity() ||
      !(status instanceof HTMLElement) ||
      !(submit instanceof HTMLButtonElement) ||
      !(email instanceof HTMLInputElement)
    ) {
      return;
    }

    submit.disabled = true;
    submit.textContent = "Joining…";
    status.dataset.state = "pending";
    status.textContent = "Saving your interest…";

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" },
      });
      const result = await response.json();

      if (!response.ok || !result.ok) {
        throw new Error(result.message ?? "Could not save your interest.");
      }

      form.reset();
      window.turnstile?.reset();
      status.dataset.state = "success";
      status.textContent = "You’re on the hosted Atpiano interest list. Thank you.";
    } catch (error) {
      window.turnstile?.reset();
      status.dataset.state = "error";
      status.textContent =
        error instanceof Error
          ? error.message
          : "Could not save your interest. Please try again.";
    } finally {
      submit.disabled = false;
      submit.textContent = "I’d try hosted Atpiano";
    }
  });
}
