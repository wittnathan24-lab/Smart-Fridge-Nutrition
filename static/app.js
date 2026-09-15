const api = async (url, options = {}) => {
    const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
    if (!response.ok) throw new Error((await response.json()).detail || "Une erreur est survenue.");
    return response.json();
};

const formDataAsObject = (form) => Object.fromEntries(new FormData(form).entries());

const renderInventory = (items) => {
    const list = document.querySelector("#fridge-list");
    if (!items.length) {
        list.innerHTML = '<p class="empty-state">Votre frigo est encore vide.<br><span>Ajoutez vos premiers ingrédients pour commencer.</span></p>';
        return;
    }
    list.innerHTML = items.map((item) => `<div class="ingredient-row"><strong>${item.name}</strong><small>${item.quantity_g} g</small></div>`).join("");
};

const renderRecipes = (recipes) => {
    const list = document.querySelector("#recipe-list");
    document.querySelector("#recipe-count").textContent = `${recipes.length} suggestion${recipes.length > 1 ? "s" : ""}`;
    if (!recipes.length) {
        list.innerHTML = '<div class="recipe-placeholder"><span>○</span><p>Aucune recette trouvée pour le moment.</p><small>Essayez avec un autre ingrédient.</small></div>';
        return;
    }
    list.innerHTML = recipes.slice(0, 6).map((recipe) => `<article class="recipe-card"><span class="meal-id">RECIPE / ${recipe.meal_id}</span><h3>${recipe.name}</h3><p>${recipe.category || "Suggestion Smart Fridge"}</p></article>`).join("");
};

document.querySelector("#profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const feedback = document.querySelector("#profile-feedback");
    try {
        const profile = formDataAsObject(event.target);
        profile.weight_kg = Number(profile.weight_kg); profile.height_cm = Number(profile.height_cm); profile.age = Number(profile.age);
        const needs = await api("/profile/nutrition", { method: "POST", body: JSON.stringify(profile) });
        document.querySelector("#target-calories").textContent = Math.round(needs.target_calories_kcal).toLocaleString("fr-FR");
        document.querySelector("#bmr").textContent = Math.round(needs.bmr_kcal).toLocaleString("fr-FR");
        document.querySelector("#tdee").textContent = Math.round(needs.tdee_kcal).toLocaleString("fr-FR");
        feedback.textContent = "Profil calculé. Votre cible est prête.";
    } catch (error) { feedback.textContent = error.message; }
});

document.querySelector("#fridge-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const feedback = document.querySelector("#fridge-feedback");
    try {
        const item = formDataAsObject(event.target); item.quantity_g = Number(item.quantity_g);
        await api("/fridge/items", { method: "POST", body: JSON.stringify(item) });
        renderInventory(await api("/fridge/items")); event.target.reset(); feedback.textContent = "Ingrédient ajouté.";
    } catch (error) { feedback.textContent = error.message; }
});

document.querySelector("#suggestions-button").addEventListener("click", async () => {
    const feedback = document.querySelector("#fridge-feedback");
    feedback.textContent = "Recherche des recettes…";
    try { renderRecipes(await api("/fridge/suggestions")); document.querySelector("#recipes").scrollIntoView({ behavior: "smooth" }); feedback.textContent = "Suggestions mises à jour."; }
    catch (error) { feedback.textContent = error.message; }
});

api("/fridge/items").then(renderInventory).catch(() => {});