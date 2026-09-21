const $ = (s) => document.querySelector(s);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
let session = null,
  needs = null;
let refreshRequest = null;
try {
  session = JSON.parse(sessionStorage.getItem("sf-session"));
} catch {
  sessionStorage.removeItem("sf-session");
}
const clearSession = async () => {
  session = null;
  sessionStorage.removeItem("sf-session");
  updateAccount();
  showNeeds(null);
  renderInventory([]);
  renderRecipes([]);
  $("#profile-form").reset();
  await loadPlan();
};
const refreshSession = async () => {
  if (!session?.refresh_token) throw Error("Votre session a expiré.");
  refreshRequest ??= fetch("/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: session.refresh_token }),
  })
    .then(async (response) => {
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || "Votre session a expiré.");
      session = { ...session, ...data };
      sessionStorage.setItem("sf-session", JSON.stringify(session));
    })
    .finally(() => {
      refreshRequest = null;
    });
  return refreshRequest;
};
const api = async (url, options = {}, canRefresh = true) => {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
    },
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw Error("Le serveur a renvoyé une réponse inattendue.");
  }
  if (!response.ok) {
    if (
      response.status === 401 &&
      !url.startsWith("/auth/") &&
      session &&
      canRefresh &&
      session.refresh_token
    ) {
      try {
        await refreshSession();
        return api(url, options, false);
      } catch {
        await clearSession();
      }
    } else if (response.status === 401 && session && !url.startsWith("/auth/")) {
      await clearSession();
    }
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : "Vérifiez les champs saisis.",
    );
  }
  return data;
};
const message = (id, text, error = false) => {
  $(id).textContent = text;
  $(id).classList.toggle("error", error);
};
const action = async (button, feedback, fn) => {
  button.disabled = true;
  try {
    await fn();
  } catch (e) {
    message(feedback, e.message, true);
  } finally {
    button.disabled = false;
  }
};
const requireAccount = () => {
  if (!session) {
    $("#auth-dialog").showModal();
    return false;
  }
  return true;
};
function updateAccount() {
  $("#open-auth").hidden = !!session;
  $("#demo-button").hidden = !!session;
  $("#logout").hidden = !session;
  message(
    "#account-feedback",
    session
      ? session.demo
        ? "Mode démonstration · données illustratives · espace individuel"
        : `Connecté : ${session.email}`
      : "",
  );
}
function showNeeds(value) {
  needs = value;
  for (const [id, key] of [
    ["target-calories", "target_calories_kcal"],
    ["bmr", "bmr_kcal"],
    ["tdee", "tdee_kcal"],
  ])
    $("#" + id).textContent = value
      ? Math.round(value[key]).toLocaleString("fr-FR")
      : "—";
}
function renderInventory(items) {
  $("#fridge-list").innerHTML = items.length
    ? items
        .map(
          (i) =>
            `<div class="ingredient-row"><strong>${esc(i.name)}</strong><label><span class="sr-only">Quantité de ${esc(i.name)} en grammes</span><input type="number" min="1" max="100000" value="${i.quantity_g}" data-quantity="${i.id}" data-name="${esc(i.name)}"></label><small>g</small><button class="text-button" data-delete="${i.id}" aria-label="Supprimer ${esc(i.name)}">×</button></div>`,
        )
        .join("")
    : '<p class="empty-state">Votre frigo attend ses premiers ingrédients.</p>';
}
function renderRecipes(recipes) {
  $("#recipe-count").textContent =
    `${recipes.length} suggestions ${session?.demo ? "· démonstration" : ""}`;
  $("#recipe-list").innerHTML = recipes.length
    ? recipes
        .map(
          (r, i) =>
            `<button class="recipe-card" data-recipe="${esc(r.meal_id)}"><div class="recipe-art" aria-hidden="true">${["◉", "✺", "❋"][i % 3]}</div><span class="meal-id">${session?.demo ? "DÉMONSTRATION" : "THEMEALDB"} / ${String(i + 1).padStart(2, "0")}</span><h3>${esc(r.name)}</h3><p>${esc(r.category || "À découvrir")} · Voir la recette ↗</p></button>`,
        )
        .join("")
    : '<div class="recipe-placeholder"><p>Aucune recette pour le moment.</p><small>Ajoutez des ingrédients et lancez les suggestions.</small></div>';
}
async function loadPlan() {
  const meals = session ? await api("/plan?day=" + $("#plan-day").value) : [];
  const sums = meals.reduce(
    (a, m) => {
      for (const k of Object.keys(a)) a[k] += m[k];
      return a;
    },
    { calories: 0, protein: 0, carbs: 0, fat: 0 },
  );
  $("#plan-calories").textContent = `${Math.round(sums.calories)} kcal`;
  $("#macro-gauges").innerHTML = [
    ["Énergie", "calories", "target_calories_kcal", "kcal"],
    ["Protéines", "protein", "protein_g", "g"],
    ["Glucides", "carbs", "carbs_g", "g"],
    ["Lipides", "fat", "fat_g", "g"],
  ]
    .map(
      ([label, key, target, unit]) =>
        `<label>${label}<strong>${Math.round(sums[key])} <small>/ ${needs ? Math.round(needs[target]) : "—"} ${unit}</small></strong><progress max="${needs ? needs[target] : 1}" value="${needs ? sums[key] : 0}" aria-label="${label}"></progress></label>`,
    )
    .join("");
  $("#plan-list").innerHTML = meals.length
    ? meals
        .map(
          (m) =>
            `<div class="ingredient-row"><strong>${esc(m.name)}</strong><small>${Math.round(m.calories)} kcal</small><button class="text-button" data-remove-meal="${m.id}" aria-label="Retirer ${esc(m.name)}">×</button></div>`,
        )
        .join("")
    : '<p class="empty-state">Une journée à composer.<br>Choisissez une recette pour ajouter votre premier repas.</p>';
}
async function hydrate() {
  updateAccount();
  if (!session) {
    renderInventory([]);
    renderRecipes([]);
    showNeeds(null);
    await loadPlan();
    return;
  }
  const [profile, items] = await Promise.all([
    api("/profile"),
    api("/fridge/items"),
  ]);
  if (profile.profile) {
    for (const [key, value] of Object.entries(profile.profile)) {
      const input = $("#profile-form").elements.namedItem(key);
      if (input) input.value = value;
    }
  }
  showNeeds(profile.needs);
  renderInventory(items);
  await loadPlan();
  if (session.demo) renderRecipes(await api("/demo/recipes"));
}
$("#open-auth").onclick = () => $("#auth-dialog").showModal();
document
  .querySelectorAll(".close-dialog")
  .forEach((b) => (b.onclick = () => b.closest("dialog").close()));
$("#auth-form").onsubmit = (e) => {
  e.preventDefault();
  action(e.submitter, "#auth-feedback", async () => {
    const credentials = Object.fromEntries(new FormData(e.target));
    if (e.submitter.value === "register" && credentials.password.length < 10) {
      throw Error("Pour créer un compte, choisissez un mot de passe d’au moins 10 caractères.");
    }
    const result = await api("/auth/" + e.submitter.value, {
      method: "POST",
      body: JSON.stringify(credentials),
    });
    if (result.confirmation_required) {
      message(
        "#auth-feedback",
        "Vérifiez votre boîte mail et les indésirables, puis cliquez sur le lien de confirmation. Si vous avez déjà un compte confirmé, utilisez Connexion.",
      );
      return;
    }
    session = result;
    sessionStorage.setItem("sf-session", JSON.stringify(session));
    e.target.reset();
    $("#auth-dialog").close();
    await hydrate();
  });
};
$("#resend-confirmation").onclick = (e) =>
  action(e.currentTarget, "#auth-feedback", async () => {
    const email = $("#auth-form").elements.namedItem("email");
    if (!email.reportValidity()) return;
    const result = await api("/auth/resend-confirmation", {
      method: "POST",
      body: JSON.stringify({ email: email.value }),
    });
    message("#auth-feedback", result.message);
  });
$("#demo-button").onclick = (e) =>
  action(e.target, "#account-feedback", async () => {
    session = await api("/auth/demo", { method: "POST" });
    sessionStorage.setItem("sf-session", JSON.stringify(session));
    await hydrate();
  });
$("#logout").onclick = () => {
  session = null;
  needs = null;
  sessionStorage.removeItem("sf-session");
  $("#profile-form").reset();
  hydrate();
};
$("#profile-form").onsubmit = (e) => {
  e.preventDefault();
  if (!requireAccount()) return;
  action(e.submitter, "#profile-feedback", async () => {
    const data = Object.fromEntries(new FormData(e.target));
    for (const k of ["weight_kg", "height_cm", "age"])
      data[k] = Number(data[k]);
    showNeeds(
      await api("/profile", { method: "PUT", body: JSON.stringify(data) }),
    );
    await loadPlan();
    message("#profile-feedback", "Profil enregistré. Vos repères sont à jour.");
  });
};
$("#fridge-form").onsubmit = (e) => {
  e.preventDefault();
  if (!requireAccount()) return;
  action(e.submitter, "#fridge-feedback", async () => {
    const data = Object.fromEntries(new FormData(e.target));
    if (!validateIngredient()) return;
    data.name = ingredientInput.value;
    data.quantity_g = Number(data.quantity_g);
    await api("/fridge/items", { method: "POST", body: JSON.stringify(data) });
    renderInventory(await api("/fridge/items"));
    e.target.reset();
    closeIngredients();
    message(
      "#ingredient-help",
      "Choisissez un ingrédient dans les suggestions.",
    );
    message("#fridge-feedback", "Ingrédient ajouté.");
  });
};
$("#fridge-list").onclick = (e) => {
  const b = e.target.closest("[data-delete]");
  if (b)
    action(b, "#fridge-feedback", async () => {
      await api("/fridge/items/" + b.dataset.delete, { method: "DELETE" });
      renderInventory(await api("/fridge/items"));
    });
};
$("#fridge-list").onchange = (e) => {
  const input = e.target.closest("[data-quantity]");
  if (!input) return;
  if (!input.checkValidity()) {
    input.reportValidity();
    return;
  }
  action(input, "#fridge-feedback", async () => {
    await api("/fridge/items/" + input.dataset.quantity, {
      method: "PUT",
      body: JSON.stringify({
        name: input.dataset.name,
        quantity_g: Number(input.value),
      }),
    });
    message("#fridge-feedback", "Quantité enregistrée.");
  });
};
$("#suggestions-button").onclick = (e) => {
  if (!requireAccount()) return;
  action(e.currentTarget, "#fridge-feedback", async () => {
    message("#fridge-feedback", "Recherche en cours…");
    renderRecipes(
      await api(session.demo ? "/demo/recipes" : "/fridge/suggestions"),
    );
    message("#fridge-feedback", "Suggestions mises à jour.");
    $("#recipes").scrollIntoView({ behavior: "smooth" });
  });
};
$("#plan-day").value = new Date(
  Date.now() - new Date().getTimezoneOffset() * 60000,
)
  .toISOString()
  .slice(0, 10);
$("#plan-day").onchange = () => {
  if ($("#plan-day").value)
    loadPlan().catch((e) => message("#account-feedback", e.message, true));
};
$("#plan-list").onclick = (e) => {
  const b = e.target.closest("[data-remove-meal]");
  if (b)
    action(b, "#account-feedback", async () => {
      await api("/plan/" + b.dataset.removeMeal, { method: "DELETE" });
      await loadPlan();
    });
};
$("#recipe-list").onclick = async (e) => {
  const button = e.target.closest("[data-recipe]");
  if (!button) return;
  const dialog = $("#recipe-dialog"),
    detail = $("#recipe-detail");
  detail.textContent = "Chargement de la recette…";
  dialog.showModal();
  try {
    const id = button.dataset.recipe;
    const recipe = await api("/recipes/" + id);
    let nutrition,
      complete = true;
    if (id.startsWith("demo-")) {
      const fixture = (await api("/demo/recipes")).find(
        (r) => r.meal_id === id,
      );
      nutrition = {
        calories: fixture.calories,
        protein: fixture.protein,
        carbs: fixture.carbs,
        fat: fixture.fat,
      };
    } else {
      const n = await api("/recipes/" + id + "/nutrition");
      nutrition = {
        calories: n.estimated_total.calories_kcal,
        protein: n.estimated_total.protein_g,
        carbs: n.estimated_total.carbs_g,
        fat: n.estimated_total.fat_g,
      };
      complete =
        n.ingredients.length > 0 &&
        n.ingredients.every(
          (i) =>
            i.estimated_nutrients &&
            Object.values(i.estimated_nutrients).every((v) => v !== null),
        );
    }
    detail.innerHTML = `<p class="eyebrow">${id.startsWith("demo-") ? "Démonstration · valeurs illustratives pour 1 portion" : "TheMealDB × USDA · total de la recette"}</p><h2>${esc(recipe.name)}</h2><div class="recipe-detail-macros">${Object.entries(
      nutrition,
    )
      .map(
        ([k, v]) =>
          `${{ calories: "Énergie", protein: "Protéines", carbs: "Glucides", fat: "Lipides" }[k]} : <strong>${v === null ? "inconnu" : Math.round(v)} ${k === "calories" ? "kcal" : "g"}</strong>`,
      )
      .join(
        " · ",
      )}</div>${!complete ? '<p class="notice">Estimation partielle : certaines quantités ou valeurs sont inconnues. L’ajout au plan est désactivé pour éviter un suivi incomplet.</p>' : ""}<h3>Ingrédients</h3><ul>${recipe.ingredients.map((i) => `<li>${esc(i.name)} — ${esc(i.measure)}</li>`).join("")}</ul><h3>Préparation</h3><p>${esc(recipe.instructions || "Instructions indisponibles.")}</p><label>Fraction de la recette <input id="meal-fraction" type="number" value="1" min="0.1" max="10" step="0.1"></label><button class="button button-accent" id="add-plan" ${complete ? "" : "disabled"}>Ajouter au ${esc($("#plan-day").value)}</button><p id="recipe-feedback" role="status"></p>`;
    $("#add-plan").onclick = (e) =>
      action(e.target, "#recipe-feedback", async () => {
        const input = $("#meal-fraction");
        if (!input.checkValidity()) {
          input.reportValidity();
          return;
        }
        const factor = Number(input.value);
        await api("/plan", {
          method: "POST",
          body: JSON.stringify({
            day: $("#plan-day").value,
            name: recipe.name,
            ...Object.fromEntries(
              Object.entries(nutrition).map(([k, v]) => [
                k,
                Math.round(v * factor * 100) / 100,
              ]),
            ),
          }),
        });
        await loadPlan();
        message("#recipe-feedback", "Repas ajouté à votre journée.");
      });
  } catch (error) {
    detail.textContent = error.message;
  }
};
async function initializeAccount() {
  const confirmation = new URLSearchParams(location.hash.slice(1));
  if (confirmation.has("access_token") || confirmation.has("error")) {
    // Remove credentials from the address bar before any asynchronous work.
    history.replaceState(null, "", location.pathname + location.search);
    if (confirmation.has("error")) {
      $("#auth-dialog").showModal();
      message("#auth-feedback", "Ce lien a expiré ou a déjà été utilisé. Connectez-vous si votre adresse est confirmée, sinon demandez un nouveau lien.", true);
    } else if (confirmation.get("refresh_token")) {
      const result = await api("/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token: confirmation.get("refresh_token") }),
      }, false);
      session = result;
      sessionStorage.setItem("sf-session", JSON.stringify(session));
    }
  }
  await hydrate();
}
initializeAccount().catch((e) => message("#account-feedback", e.message, true));

$("#generate-plan").onclick = (e) => {
  if (!requireAccount()) return;
  action(e.currentTarget, "#plan-feedback", async () => {
    message("#plan-feedback", "Composition de votre journée…");
    const result = await api("/plan/generate?day=" + $("#plan-day").value, {
      method: "POST",
    });
    await loadPlan();
    message("#plan-feedback", result.message);
  });
};

// Local suggestions stay available while typing, without a request per keystroke.
const ingredientInput = $("#ingredient-name");
const ingredientOptions = $("#ingredient-options");
let ingredientCatalogue = [],
  ingredientMatches = [],
  activeIngredient = -1;
const normalizeIngredient = (text) =>
  text
    .toLowerCase()
    .trim()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/œ/g, "oe")
    .replace(/æ/g, "ae")
    .replace(/’/g, "'")
    .replace(/\s+/g, " ");
function editDistance(a, b) {
  let row = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const next = [i];
    for (let j = 1; j <= b.length; j++)
      next[j] = Math.min(
        next[j - 1] + 1,
        row[j] + 1,
        row[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
    row = next;
  }
  return row[b.length];
}
function closeIngredients() {
  ingredientOptions.hidden = true;
  ingredientInput.setAttribute("aria-expanded", "false");
  ingredientInput.removeAttribute("aria-activedescendant");
  activeIngredient = -1;
}
function chooseIngredient(index) {
  const item = ingredientMatches[index];
  if (!item) return;
  ingredientInput.value = item.name;
  ingredientInput.setCustomValidity("");
  closeIngredients();
  message("#ingredient-help", `${item.name} : ingrédient reconnu.`);
  ingredientInput.focus();
}
function showIngredients() {
  const q = normalizeIngredient(ingredientInput.value);
  ingredientInput.setCustomValidity("");
  activeIngredient = -1;
  ingredientInput.removeAttribute("aria-activedescendant");
  ingredientMatches = ingredientCatalogue
    .map((item) => {
      const keys = [normalizeIngredient(item.name), ...item.aliases];
      let score = keys.some((k) => k === q)
        ? 0
        : keys.some((k) => k.startsWith(q))
          ? 1
          : keys.some((k) => k.includes(q))
            ? 2
            : 99;
      if (score === 99 && q.length >= 3) {
        const distance = Math.min(...keys.map((k) => editDistance(q, k)));
        if (distance <= (q.length > 5 ? 2 : 1)) score = 3 + distance;
      }
      return { ...item, score };
    })
    .filter((i) => i.score < 99)
    .sort((a, b) => a.score - b.score || a.name.localeCompare(b.name, "fr"))
    .slice(0, 8);
  ingredientOptions.innerHTML = ingredientMatches
    .map(
      (item, i) =>
        `<li id="ingredient-option-${i}" role="option" aria-selected="false" data-index="${i}">${esc(item.name)}</li>`,
    )
    .join("");
  ingredientOptions.hidden = !ingredientMatches.length;
  ingredientInput.setAttribute(
    "aria-expanded",
    String(!!ingredientMatches.length),
  );
  message(
    "#ingredient-help",
    ingredientCatalogue.length
      ? ingredientMatches.length
        ? `${ingredientMatches.length} suggestion${ingredientMatches.length > 1 ? "s" : ""}. Utilisez les flèches puis Entrée, ou cliquez sur un nom.`
        : "Aucun ingrédient reconnu. Essayez un autre nom."
      : "Le catalogue est indisponible. Rechargez la page pour réessayer.",
  );
}
function validateIngredient() {
  const q = normalizeIngredient(ingredientInput.value);
  const item = ingredientCatalogue.find(
    (i) => normalizeIngredient(i.name) === q || i.aliases.includes(q),
  );
  if (item) {
    ingredientInput.value = item.name;
    ingredientInput.setCustomValidity("");
    return true;
  }
  ingredientInput.setCustomValidity(
    "Choisissez un ingrédient reconnu dans les suggestions.",
  );
  ingredientInput.reportValidity();
  return false;
}
ingredientInput.addEventListener("input", showIngredients);
ingredientInput.addEventListener("focus", showIngredients);
ingredientInput.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    event.preventDefault();
    closeIngredients();
    return;
  }
  if (["ArrowDown", "ArrowUp"].includes(event.key)) {
    event.preventDefault();
    if (ingredientOptions.hidden) showIngredients();
    if (!ingredientMatches.length) return;
    if (activeIngredient === -1 && event.key === "ArrowUp")
      activeIngredient = 0;
    activeIngredient =
      (activeIngredient +
        (event.key === "ArrowDown" ? 1 : -1) +
        ingredientMatches.length) %
      ingredientMatches.length;
    [...ingredientOptions.children].forEach((el, i) =>
      el.setAttribute("aria-selected", String(i === activeIngredient)),
    );
    ingredientInput.setAttribute(
      "aria-activedescendant",
      `ingredient-option-${activeIngredient}`,
    );
    ingredientOptions.children[activeIngredient].scrollIntoView({
      block: "nearest",
    });
  } else if (event.key === "Enter" && !ingredientOptions.hidden) {
    event.preventDefault();
    if (activeIngredient >= 0) chooseIngredient(activeIngredient);
    else if (ingredientMatches.length === 1) chooseIngredient(0);
  }
});
ingredientOptions.addEventListener("pointerdown", (event) =>
  event.preventDefault(),
);
ingredientOptions.addEventListener("click", (event) => {
  const option = event.target.closest("[data-index]");
  if (option) chooseIngredient(Number(option.dataset.index));
});
ingredientInput.addEventListener("blur", closeIngredients);
api("/ingredients")
  .then((items) => {
    ingredientCatalogue = items;
    if (document.activeElement === ingredientInput) showIngredients();
  })
  .catch(() =>
    message(
      "#ingredient-help",
      "Le catalogue est indisponible. Rechargez la page pour réessayer.",
      true,
    ),
  );
