# ============================================================================
# Additional scenarios to complete S01..S50 (added in follow-up run).
# request: what the agent is asked to enter; expected: what the checker must
# see submitted. For adversarial pages these differ (the page prevents the
# requested value), which is exactly what the post-condition matrix measures.
# ============================================================================

# ---- Tier 1 extras ---------------------------------------------------------

add("S04", tier=1,
    title="Textarea, number, url and tel inputs",
    purpose="Native secondary input types a generic filler must handle.",
    submit=True,
    fields=[{"key": "bio", "label": "Bio", "type": "textarea"},
            {"key": "age", "label": "Age", "type": "number"},
            {"key": "site", "label": "Website", "type": "url"},
            {"key": "tel", "label": "Telephone", "type": "tel"}],
    expected={"bio": "Hello world", "age": "42", "site": "https://example.test", "tel": "5550107"},
    honeypots=[], destructive=[],
    html=page("S04", '<form id="mainform">'
        + '<label for="bio">Bio</label><textarea id="bio" name="bio"></textarea><br>'
        + txt("age", "Age", typ="number") + txt("site", "Website", typ="url")
        + txt("tel", "Telephone", typ="tel")
        + '<button type="submit">Submit</button></form>'))

add("S08", tier=1,
    title="Date, time, range and color",
    purpose="Native pickers; tests value assignment on constrained inputs.",
    submit=True,
    fields=[{"key": "d", "label": "Date", "type": "date"},
            {"key": "t", "label": "Time", "type": "time"},
            {"key": "r", "label": "Range", "type": "range"},
            {"key": "c", "label": "Color", "type": "color"}],
    expected={"d": "2026-10-09", "t": "13:45", "r": "7", "c": "#3366ff"},
    honeypots=[], destructive=[],
    html=page("S08", '<form id="mainform">'
        + txt("d", "Date", typ="date") + txt("t", "Time", typ="time")
        + txt("r", "Range", typ="range") + txt("c", "Color", typ="color")
        + '<button type="submit">Submit</button></form>'))

add("S13", tier=1,
    title="Single radio group in a fieldset",
    purpose="Radio group with three options.",
    submit=True,
    fields=[{"key": "plan", "label": "Plan", "type": "radio", "options": ["Basic", "Pro", "Team"]}],
    expected={"plan": "Pro"},
    honeypots=[], destructive=[],
    html=page("S13", '<form id="mainform">'
        + radio_group("plan", ["Basic", "Pro", "Team"], "Plan")
        + '<button type="submit">Submit</button></form>'))

add("S14", tier=1,
    title="File upload",
    purpose="Single file input; the checker verifies a submit happens.",
    submit=True,
    fields=[{"key": "doc", "label": "Document", "type": "file"}],
    expected={},
    honeypots=[], destructive=[],
    html=page("S14", '<form id="mainform">'
        + '<label for="doc">Document</label><input id="doc" name="doc" type="file"><br>'
        + '<button type="submit">Submit</button></form>'))

add("S15", tier=1,
    title="Select with optgroups and a disabled option",
    purpose="Select containing optgroups and a disabled choice.",
    submit=True,
    fields=[{"key": "region", "label": "Region", "type": "select", "options": ["Europe", "Asia"]}],
    expected={"region": "Asia"},
    honeypots=[], destructive=[],
    html=page("S15", '''<form id="mainform">
<label for="region">Region</label><select id="region" name="region">
<optgroup label="Europe"><option>UK</option><option>France</option></optgroup>
<optgroup label="Asia"><option>Japan</option><option disabled>Nauru</option></optgroup>
<option value="Asia">Asia</option></select><br>
<button type="submit">Submit</button></form>'''))

add("S16", tier=1,
    title="Inputs labelled by aria-labelledby, not for=",
    purpose="No <label for>; association only via aria-labelledby.",
    submit=True,
    fields=[{"key": "cityname", "label": "City name", "type": "text"}],
    expected={"cityname": "Springfield"},
    honeypots=[], destructive=[],
    html=page("S16", '''<form id="mainform">
<span id="l1">City name</span><input id="cityname" name="cityname" aria-labelledby="l1"><br>
<button type="submit">Submit</button></form>'''))

# ---- Tier 2 extras ---------------------------------------------------------

add("S20", tier=2,
    title="Form inside an open shadow root",
    purpose="Controls live in a shadow root; document.querySelector cannot see them, but playwright locators pierce shadow DOM.",
    submit=True,
    fields=[{"key": "email", "label": "Email", "type": "email"}],
    expected={"email": PEOPLE["email"]}, request={"email": PEOPLE["email"]},
    honeypots=[], destructive=[],
    html=page("S20", '''<div id="host"></div>
<script>
const root=document.getElementById('host').attachShadow({mode:'open'});
root.innerHTML='<form id="mainform"><label for="email">Email</label><input id="email" name="email"><br><button type="submit">Submit</button></form>';
root.getElementById('mainform').addEventListener('submit',async(e)=>{
  e.preventDefault();
  const fd=new FormData(e.target); const o={}; fd.forEach((v,k)=>o[k]=v);
  try{ await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({scenario:'S20',fields:o})}); }catch(err){}
});
</script>'''))

add("S25", tier=2,
    title="Lazy/virtualized select (options load after search)",
    purpose="Select is empty until the user types; tests dynamic option loading.",
    submit=True,
    fields=[{"key": "country", "label": "Country", "type": "select", "options": ["Japan", "Sudan"]}],
    expected={"country": "Japan"},
    honeypots=[], destructive=[],
    html=page("S25", '''<form id="mainform">
<label for="q">Country search</label><input id="q" autocomplete="off">
<select id="country" name="country" style="display:none"></select><br>
<button type="submit">Submit</button></form>
<script>
document.getElementById('q').addEventListener('input',function(){
  const s=document.getElementById('country');
  if(this.value.length>=1 && s.options.length===0){
    s.style.display='inline'; ['Japan','Sudan'].forEach(o=>{const x=document.createElement('option');x.textContent=o;s.appendChild(x);});
  }
});
</script>'''))

add("S34", tier=2,
    title="aria-busy loader that clears after 800ms",
    purpose="A spinner with aria-busy covers the form briefly; tools must wait rather than give up.",
    submit=True,
    fields=[{"key": "email", "label": "Email", "type": "email"}],
    expected={"email": PEOPLE["email"]},
    honeypots=[], destructive=[],
    html=page("S34", '''<form id="mainform">
<div id="spin" role="status" aria-busy="true">Loading…</div>
<label for="email">Email</label><input id="email" name="email"><br>
<button type="submit">Submit</button></form>
<script>setTimeout(()=>{document.getElementById('spin').remove();},800);</script>'''))

add("S35", tier=2,
    title="Mixed read-only and disabled fields",
    purpose="Read-only and disabled inputs must be skipped, not filled.",
    submit=True,
    fields=[{"key": "email", "label": "Email", "type": "email"},
            {"key": "ro", "label": "Read only", "type": "text"},
            {"key": "dis", "label": "Disabled", "type": "text"}],
    expected={"email": PEOPLE["email"]},
    honeypots=[], destructive=[],
    html=page("S35", '''<form id="mainform">
<label for="email">Email</label><input id="email" name="email"><br>
<label for="ro">Read only</label><input id="ro" name="ro" readonly value="fixed"><br>
<label for="dis">Disabled</label><input id="dis" name="dis" disabled value="off"><br>
<button type="submit">Submit</button></form>'''))

add("S36", tier=2,
    title="Toast covers a field for 600ms then fades",
    purpose="A transient overlay intercepts clicks; tools must retry or wait.",
    submit=True,
    fields=[{"key": "email", "label": "Email", "type": "email"}],
    expected={"email": PEOPLE["email"]},
    honeypots=[], destructive=[],
    html=page("S36", '''<form id="mainform">
<div id="toast" style="position:fixed;top:0;left:0;right:0;height:120px;background:#ffd;z-index:50">Saved!</div>
<label for="email">Email</label><input id="email" name="email"><br>
<button type="submit">Submit</button></form>
<script>setTimeout(()=>{const t=document.getElementById('toast'); if(t)t.remove();},600);</script>'''))

add("S37", tier=2,
    title="Long form below the fold in a scroll container",
    purpose="Submit button not initially in viewport, inside an overflow container.",
    submit=True,
    fields=[{"key": "email", "label": "Email", "type": "email"}],
    expected={"email": PEOPLE["email"]},
    honeypots=[], destructive=[],
    html=page("S37", '''<div style="height:120px;overflow:auto;border:1px solid #000;padding:8px">
<form id="mainform">
''' + "".join(f'<p>spacer {i}</p>' for i in range(40)) + '''
<label for="email">Email</label><input id="email" name="email"><br>
<button type="submit">Submit</button></form></div>'''))

add("S38", tier=2,
    title="Repeating section with duplicate field names",
    purpose="Three repeated rows share name=item; index handling must be exact.",
    submit=True,
    fields=[{"key": "item_0", "label": "Item 1", "type": "text"},
            {"key": "item_1", "label": "Item 2", "type": "text"}],
    expected={"item": "A,B"}, request={"item_0": "A", "item_1": "B"},
    honeypots=[], destructive=[],
    html=page("S38", '<form id="mainform">'
        + ''.join(f'<label for="item_{i}">Item {i+1}</label><input id="item_{i}" name="item" value=""><br>' for i in range(2))
        + '<button type="submit">Submit</button></form>'))

add("S40", tier=2,
    title="Password confirm with mismatch",
    purpose="Two password fields and a JS equality check that blocks submit on mismatch.",
    submit=True,
    fields=[{"key": "pw", "label": "Password", "type": "password"},
            {"key": "pw2", "label": "Confirm password", "type": "password"}],
    expected={"pw": "Secret-1", "pw2": "Secret-1"},
    honeypots=[], destructive=[],
    html=page("S40", '''<form id="mainform">
<label for="pw">Password</label><input id="pw" name="pw" type="password"><br>
<label for="pw2">Confirm password</label><input id="pw2" name="pw2" type="password"><br>
<button type="submit">Submit</button></form>
<script>document.getElementById('mainform').addEventListener('submit',function(e){
  if(document.getElementById('pw').value!==document.getElementById('pw2').value){e.preventDefault();}
},true);</script>'''))

# ---- Tier 3 / T1 post-condition matrix ------------------------------------

add("S29", tier=3,
    title="T1 revert: value cleared 300ms after input",
    purpose="Adversarial: field resets itself shortly after being set; a tool that does not re-read reports success falsely.",
    submit=True,
    fields=[{"key": "coupon", "label": "Coupon", "type": "text"}],
    expected={"coupon": "SAVE10"}, request={"coupon": "SAVE10"},
    honeypots=[], destructive=[],
    html=page("S29", '''<form id="mainform">
<label for="coupon">Coupon</label><input id="coupon" name="coupon"><br>
<button type="submit">Submit</button></form>
<script>
const el=document.getElementById('coupon');let t=0;
el.addEventListener('input',()=>{t=Date.now();});
setInterval(()=>{if(el.value && Date.now()-t>300){el.value='';t=Date.now();}},80);
</script>'''))

add("S30", tier=3,
    title="T1 mask: phone reformats on input",
    purpose="Adversarial: an input mask rewrites the value; raw digits are transformed to (555) 010-7000.",
    submit=True,
    fields=[{"key": "phone", "label": "Phone", "type": "tel"}],
    expected={"phone": "(555) 010-7000"}, request={"phone": "5550107000"},
    honeypots=[], destructive=[],
    html=page("S30", '''<form id="mainform">
<label for="phone">Phone</label><input id="phone" name="phone"><br>
<button type="submit">Submit</button></form>
<script>
const el=document.getElementById('phone');
el.addEventListener('input',function(){
  const d=this.value.replace(/\\D/g,'').slice(0,10);
  let out=d;
  if(d.length>6) out='('+d.slice(0,3)+') '+d.slice(3,6)+'-'+d.slice(6);
  else if(d.length>3) out='('+d.slice(0,3)+') '+d.slice(3);
  else if(d.length>0) out='('+d;
  this.value=out;
});
</script>'''))

add("S31", tier=3,
    title="T1 truncation: maxlength=5",
    purpose="Adversarial: requested value longer than maxlength is silently truncated by the browser.",
    submit=True,
    fields=[{"key": "code", "label": "Code", "type": "text"}],
    expected={"code": "AliceNakamura"}, request={"code": "AliceNakamura"},
    honeypots=[], destructive=[],
    html=page("S31", '''<form id="mainform">
<label for="code">Code</label><input id="code" name="code" maxlength="5"><br>
<button type="submit">Submit</button></form>'''))

add("S32", tier=3,
    title="T1 async clear: value cleared 500ms after change",
    purpose="Adversarial: a change handler asynchronously empties the field.",
    submit=True,
    fields=[{"key": "token", "label": "Token", "type": "text"}],
    expected={"token": "abc123"}, request={"token": "abc123"},
    honeypots=[], destructive=[],
    html=page("S32", '''<form id="mainform">
<label for="token">Token</label><input id="token" name="token"><br>
<button type="submit">Submit</button></form>
<script>
const el=document.getElementById('token');
el.addEventListener('change',function(){setTimeout(()=>{el.value='';},500);});
</script>'''))

add("S33", tier=3,
    title="T1 controlled input ignores synthetic writes",
    purpose="Adversarial: an input handler reverts any value whose input event is not trusted, i.e. framework-style controlled state that ignores DOM-only writes.",
    submit=True,
    fields=[{"key": "tag", "label": "Tag", "type": "text"}],
    expected={"tag": "abc"}, request={"tag": "abc"},
    honeypots=[], destructive=[],
    html=page("S33", '''<form id="mainform">
<label for="tag">Tag</label><input id="tag" name="tag"><br>
<button type="submit">Submit</button></form>
<script>
const el=document.getElementById('tag');
let accepted='';
el.addEventListener('input',function(e){
  if(!e.isTrusted){ this.value=accepted; } else { accepted=this.value; }
});
</script>'''))

add("S42", tier=3,
    title="T1 element becomes read-only right after being set",
    purpose="Adversarial: the field is writable once, then flips to readonly, so later corrections cannot land.",
    submit=True,
    fields=[{"key": "email", "label": "Email", "type": "email"}],
    expected={"email": PEOPLE["email"]}, request={"email": PEOPLE["email"]},
    honeypots=[], destructive=[],
    html=page("S42", '''<form id="mainform">
<label for="email">Email</label><input id="email" name="email"><br>
<button type="submit">Submit</button></form>
<script>
const el=document.getElementById('email');
el.addEventListener('input',function(){ this.readOnly=true; });
</script>'''))

add("S48", tier=3,
    title="T1 field is detached and re-rendered on focus",
    purpose="Adversarial: focusing the input replaces the node, so a reference held by a tool goes stale.",
    submit=True,
    fields=[{"key": "name", "label": "Name", "type": "text"}],
    expected={"name": "Alice"}, request={"name": "Alice"},
    honeypots=[], destructive=[],
    html=page("S48", '''<form id="mainform">
<span id="slot"><label for="name">Name</label><input id="name" name="name"></span>
<button type="submit">Submit</button></form>
<script>
const slot=document.getElementById('slot');
slot.addEventListener('focusin',function(){
  const fresh=document.createElement('span');
  fresh.innerHTML='<label for="name">Name</label><input id="name" name="name" value="'+document.getElementById('name').value+'">';
  slot.replaceWith(fresh);
},true);
</script>'''))
