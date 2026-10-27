const form = document.querySelector("form");
const button = document.getElementById("submit-movement");

form.addEventListener("submit", function () {
    button.disabled = true;
    button.textContent = "Registrando...";
    
    console.log("Formulário enviado!");
});