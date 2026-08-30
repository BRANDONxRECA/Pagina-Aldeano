document.addEventListener("DOMContentLoaded", () => {
    
    const modalForm = document.querySelector("#myModal form");
    if (modalForm) {
        modalForm.addEventListener("submit", (e) => {
            const email = document.querySelector("#myModal #email").value.trim();
            const password = document.querySelector("#myModal #pwd").value.trim();

            if (!email || !password) {
                e.preventDefault();
                alert("Por favor completa todos los campos de acceso.");
            }
        });
    }

    
    const commentForm = document.querySelector("form textarea#comment")?.closest("form");
    if (commentForm) {
        const sendBtn = commentForm.querySelector("button");
        sendBtn?.addEventListener("click", () => {
            const email = commentForm.querySelector("#email").value.trim();
            const comment = commentForm.querySelector("#comment").value.trim();

            if (!email || !comment) {
                alert("Debes ingresar un email y un mensaje antes de enviar.");
                return;
            }

            alert("¡Mensaje enviado con éxito!");
            commentForm.reset();
        });
    }
});
