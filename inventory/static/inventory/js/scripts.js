
const form = document.querySelector("form");
const button = document.getElementById("submit-movement");

if (form && button) {
    form.addEventListener("submit", function () {
        button.disabled = true;
        button.textContent = "Registrando...";

        console.log("Formulário enviado!");
    });
}

// Mostrar ou ocultar senha
function togglePassword(button) {
    const input = button.parentElement.querySelector("input");

    if (input.type === "password") {
        input.type = "text";
        button.setAttribute("aria-label", "Ocultar senha");
    } else {
        input.type = "password";
        button.setAttribute("aria-label", "Mostrar senha");
    }
}
