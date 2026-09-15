const $ = s => document.querySelector(s);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let session = null, needs = null;
try { session = JSON.parse(sessionStorage.getItem('sf-session')); } catch { sessionStorage.removeItem('sf-session'); }
const api = async (url, options={}) => {
    const response = await fetch(url, {...options, headers:{'Content-Type':'application/json', ...(session ? {Authorization:`Bearer ${session.access_token}`} : {})}});
    let data; try {data = await response.json();} catch {throw Error('Le serveur a renvoyé une réponse inattendue.');}
    if (!response.ok) {
        if (response.status === 401 && session) { session=null; sessionStorage.removeItem('sf-session'); updateAccount(); }
        throw Error(typeof data.detail === 'string' ? data.detail : 'Vérifiez les champs saisis.');
    }
    return data;
};
const message = (id,text,error=false) => {$(id).textContent=text;$(id).classList.toggle('error',error);};
const action = async (button,feedback,fn) => {button.disabled=true;try{await fn();}catch(e){message(feedback,e.message,true);}finally{button.disabled=false;}};
const requireAccount = () => {if(!session){$('#auth-dialog').showModal();return false;}return true;};
function updateAccount(){
    $('#open-auth').hidden=!!session;$('#demo-button').hidden=!!session;$('#logout').hidden=!session;
    message('#account-feedback',session ? (session.demo ? 'Mode démonstration · données illustratives · espace individuel' : `Connecté : ${session.email}`) : '');
}
function showNeeds(value){needs=value;for(const [id,key] of [['target-calories','target_calories_kcal'],['bmr','bmr_kcal'],['tdee','tdee_kcal']])$('#'+id).textContent=value?Math.round(value[key]).toLocaleString('fr-FR'):'—';}
function renderInventory(items){
    $('#fridge-list').innerHTML=items.length?items.map(i=>`<div class="ingredient-row"><strong>${esc(i.name)}</strong><label><span class="sr-only">Quantité de ${esc(i.name)} en grammes</span><input type="number" min="1" max="100000" value="${i.quantity_g}" data-quantity="${i.id}" data-name="${esc(i.name)}"></label><small>g</small><button class="text-button" data-delete="${i.id}" aria-label="Supprimer ${esc(i.name)}">×</button></div>`).join(''):'<p class="empty-state">Votre frigo attend ses premiers ingrédients.</p>';
}
function renderRecipes(recipes){
    $('#recipe-count').textContent=`${recipes.length} suggestions ${session?.demo?'· démonstration':''}`;
    $('#recipe-list').innerHTML=recipes.length?recipes.map((r,i)=>`<button class="recipe-card" data-recipe="${esc(r.meal_id)}"><div class="recipe-art" aria-hidden="true">${['◉','✺','❋'][i%3]}</div><span class="meal-id">${session?.demo?'DÉMONSTRATION':'THEMEALDB'} / ${String(i+1).padStart(2,'0')}</span><h3>${esc(r.name)}</h3><p>${esc(r.category||'À découvrir')} · Voir la recette ↗</p></button>`).join(''):'<div class="recipe-placeholder"><p>Aucune recette pour le moment.</p><small>Ajoutez des ingrédients et lancez les suggestions.</small></div>';
}
async function loadPlan(){
    const meals=session?await api('/plan?day='+$('#plan-day').value):[];
    const sums=meals.reduce((a,m)=>{for(const k of Object.keys(a))a[k]+=m[k];return a;},{calories:0,protein:0,carbs:0,fat:0});
    $('#plan-calories').textContent=`${Math.round(sums.calories)} kcal`;
    $('#macro-gauges').innerHTML=[['Énergie','calories','target_calories_kcal','kcal'],['Protéines','protein','protein_g','g'],['Glucides','carbs','carbs_g','g'],['Lipides','fat','fat_g','g']].map(([label,key,target,unit])=>`<label>${label}<strong>${Math.round(sums[key])} <small>/ ${needs?Math.round(needs[target]):'—'} ${unit}</small></strong><progress max="${needs?needs[target]:1}" value="${needs?sums[key]:0}" aria-label="${label}"></progress></label>`).join('');
    $('#plan-list').innerHTML=meals.length?meals.map(m=>`<div class="ingredient-row"><strong>${esc(m.name)}</strong><small>${Math.round(m.calories)} kcal</small><button class="text-button" data-remove-meal="${m.id}" aria-label="Retirer ${esc(m.name)}">×</button></div>`).join(''):'<p class="empty-state">Une journée à composer.<br>Choisissez une recette pour ajouter votre premier repas.</p>';
}
async function hydrate(){
    updateAccount();if(!session){renderInventory([]);renderRecipes([]);showNeeds(null);await loadPlan();return;}
    const [profile,items]=await Promise.all([api('/profile'),api('/fridge/items')]);
    if(profile.profile){for(const [key,value] of Object.entries(profile.profile)){const input=$('#profile-form').elements.namedItem(key);if(input)input.value=value;}}
    showNeeds(profile.needs);renderInventory(items);await loadPlan();
    if(session.demo)renderRecipes(await api('/demo/recipes'));
}
$('#open-auth').onclick=()=>$('#auth-dialog').showModal();
document.querySelectorAll('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());
$('#auth-form').onsubmit=e=>{e.preventDefault();action(e.submitter,'#auth-feedback',async()=>{session=await api('/auth/'+e.submitter.value,{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(e.target)))});sessionStorage.setItem('sf-session',JSON.stringify(session));e.target.reset();$('#auth-dialog').close();await hydrate();});};
$('#demo-button').onclick=e=>action(e.target,'#account-feedback',async()=>{session=await api('/auth/demo',{method:'POST'});sessionStorage.setItem('sf-session',JSON.stringify(session));await hydrate();});
$('#logout').onclick=()=>{session=null;needs=null;sessionStorage.removeItem('sf-session');$('#profile-form').reset();hydrate();};
$('#profile-form').onsubmit=e=>{e.preventDefault();if(!requireAccount())return;action(e.submitter,'#profile-feedback',async()=>{const data=Object.fromEntries(new FormData(e.target));for(const k of ['weight_kg','height_cm','age'])data[k]=Number(data[k]);showNeeds(await api('/profile',{method:'PUT',body:JSON.stringify(data)}));await loadPlan();message('#profile-feedback','Profil enregistré. Vos repères sont à jour.');});};
$('#fridge-form').onsubmit=e=>{e.preventDefault();if(!requireAccount())return;action(e.submitter,'#fridge-feedback',async()=>{const data=Object.fromEntries(new FormData(e.target));data.quantity_g=Number(data.quantity_g);await api('/fridge/items',{method:'POST',body:JSON.stringify(data)});renderInventory(await api('/fridge/items'));e.target.reset();message('#fridge-feedback','Ingrédient ajouté.');});};
$('#fridge-list').onclick=e=>{const b=e.target.closest('[data-delete]');if(b)action(b,'#fridge-feedback',async()=>{await api('/fridge/items/'+b.dataset.delete,{method:'DELETE'});renderInventory(await api('/fridge/items'));});};
$('#fridge-list').onchange=e=>{const input=e.target.closest('[data-quantity]');if(!input)return;if(!input.checkValidity()){input.reportValidity();return;}action(input,'#fridge-feedback',async()=>{await api('/fridge/items/'+input.dataset.quantity,{method:'PUT',body:JSON.stringify({name:input.dataset.name,quantity_g:Number(input.value)})});message('#fridge-feedback','Quantité enregistrée.');});};
$('#suggestions-button').onclick=e=>{if(!requireAccount())return;action(e.currentTarget,'#fridge-feedback',async()=>{message('#fridge-feedback','Recherche en cours…');renderRecipes(await api(session.demo?'/demo/recipes':'/fridge/suggestions'));message('#fridge-feedback','Suggestions mises à jour.');$('#recipes').scrollIntoView({behavior:'smooth'});});};
$('#plan-day').value=new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,10);
$('#plan-day').onchange=()=>{if($('#plan-day').value)loadPlan().catch(e=>message('#account-feedback',e.message,true));};
$('#plan-list').onclick=e=>{const b=e.target.closest('[data-remove-meal]');if(b)action(b,'#account-feedback',async()=>{await api('/plan/'+b.dataset.removeMeal,{method:'DELETE'});await loadPlan();});};
$('#recipe-list').onclick=async e=>{
    const button=e.target.closest('[data-recipe]');if(!button)return;
    const dialog=$('#recipe-dialog'), detail=$('#recipe-detail');detail.textContent='Chargement de la recette…';dialog.showModal();
    try{
        const id=button.dataset.recipe;const recipe=await api('/recipes/'+id);
        let nutrition,complete=true;
        if(id.startsWith('demo-')){const fixture=(await api('/demo/recipes')).find(r=>r.meal_id===id);nutrition={calories:fixture.calories,protein:fixture.protein,carbs:fixture.carbs,fat:fixture.fat};}
        else{const n=await api('/recipes/'+id+'/nutrition');nutrition={calories:n.estimated_total.calories_kcal,protein:n.estimated_total.protein_g,carbs:n.estimated_total.carbs_g,fat:n.estimated_total.fat_g};complete=n.ingredients.length>0&&n.ingredients.every(i=>i.estimated_nutrients&&Object.values(i.estimated_nutrients).every(v=>v!==null));}
        detail.innerHTML=`<p class="eyebrow">${id.startsWith('demo-')?'Démonstration · valeurs illustratives pour 1 portion':'TheMealDB × USDA · total de la recette'}</p><h2>${esc(recipe.name)}</h2><div class="recipe-detail-macros">${Object.entries(nutrition).map(([k,v])=>`${({calories:'Énergie',protein:'Protéines',carbs:'Glucides',fat:'Lipides'})[k]} : <strong>${v===null?'inconnu':Math.round(v)} ${k==='calories'?'kcal':'g'}</strong>`).join(' · ')}</div>${!complete?'<p class="notice">Estimation partielle : certaines quantités ou valeurs sont inconnues. L’ajout au plan est désactivé pour éviter un suivi incomplet.</p>':''}<h3>Ingrédients</h3><ul>${recipe.ingredients.map(i=>`<li>${esc(i.name)} — ${esc(i.measure)}</li>`).join('')}</ul><h3>Préparation</h3><p>${esc(recipe.instructions||'Instructions indisponibles.')}</p><label>Fraction de la recette <input id="meal-fraction" type="number" value="1" min="0.1" max="10" step="0.1"></label><button class="button button-accent" id="add-plan" ${complete?'':'disabled'}>Ajouter au ${esc($('#plan-day').value)}</button><p id="recipe-feedback" role="status"></p>`;
        $('#add-plan').onclick=e=>action(e.target,'#recipe-feedback',async()=>{const input=$('#meal-fraction');if(!input.checkValidity()){input.reportValidity();return;}const factor=Number(input.value);await api('/plan',{method:'POST',body:JSON.stringify({day:$('#plan-day').value,name:recipe.name,...Object.fromEntries(Object.entries(nutrition).map(([k,v])=>[k,Math.round(v*factor*100)/100]))})});await loadPlan();message('#recipe-feedback','Repas ajouté à votre journée.');});
    }catch(error){detail.textContent=error.message;}
};
hydrate().catch(e=>message('#account-feedback',e.message,true));
