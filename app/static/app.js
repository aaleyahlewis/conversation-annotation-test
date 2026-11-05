'use strict';
let boot, current=null, preview=null, selected=null, label=null;
let regionsOpen=false, savedDocument=null, fieldSaveError=null, submitting=false;
let validationIssues=[],submitError='',actionBarObserver=null;
let dockMessage='',dockError=false,dockTimer=null;
let generation=0, savedGeneration=0, saving=null, timer=null;
const app=document.querySelector('#app'), notice=document.querySelector('#notice');
const cp=s=>Array.from(s);
function replaceApp(...nodes){actionBarObserver?.disconnect();app.replaceChildren(...nodes.filter(x=>x!==null&&x!==undefined));}
function el(tag,attrs={},...children){const n=document.createElement(tag);for(const [k,v] of Object.entries(attrs)){if(k.startsWith('on'))n.addEventListener(k.slice(2),v);else if(k==='class')n.className=v;else if(k==='text')n.textContent=v;else if(k==='checked')n.checked=v;else if(k==='value')n.dataset.initialValue=v;else if(v!==undefined&&v!==null)n.setAttribute(k,v);}for(const c of children.flat())if(c!==null&&c!==undefined)n.append(c instanceof Node?c:document.createTextNode(String(c)));if(Object.hasOwn(attrs,'value'))n.value=attrs.value;return n;}
const button=(text,fn,cls='')=>el('button',{type:'button',class:cls,onclick:fn},text);
function tell(text,error=false){if(current&&document.querySelector('#submission-status')){notice.textContent='';dockFeedback(text,error);return;}notice.textContent=text;notice.className=error?'error':'';}
function clearDockFeedback(){clearTimeout(dockTimer);dockMessage='';dockError=false;}
function dockFeedback(text,error=false){clearDockFeedback();dockMessage=text;dockError=error;refreshDockStatus();if(text&&!error&&!text.startsWith('Preparing'))dockTimer=setTimeout(()=>{dockMessage='';refreshDockStatus();},5000);}
function refreshDockStatus(){const n=document.querySelector('#submission-status');if(!n)return;const message=fieldSaveError?'Save failed — '+fieldSaveError:submitError||dockMessage||editorStatus();n.textContent=message;n.setAttribute('title',message);n.classList.toggle('error',!!fieldSaveError||!!submitError||dockError);}
function labelHint(text){const n=document.querySelector('#label-status');if(n)n.textContent=text;}
async function api(path,body){const r=await fetch(path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-Annotation-CSRF':boot.csrf},body:body===undefined?undefined:JSON.stringify(body)});const data=await r.json();if(!r.ok){const error=new Error(data.error||'Request failed');error.issues=data.issues;throw error;}return data;}
async function busy(b,fn){if(b.disabled)return;b.disabled=true;try{await fn();}catch(e){tell(e.message,true);}finally{b.disabled=false;}}
function action(text,fn,cls=''){let b=button(text,()=>busy(b,fn),cls);return b;}
function steps(active){return el('nav',{class:'steps','aria-label':'Import progress'},...['Import','Review','Annotate'].map((s,i)=>el('span',{class:i===active?'active':''},`${String(i+1).padStart(2,'0')}  ${s}`)));}
function localStatus(node,message,error=false){if(!node)return;node.textContent=message;node.classList.toggle('error',error);}
async function download(path,feedback=null){
 const inEditor=!!current&&path.startsWith('/api/conversations/');
 const conversationId=inEditor?current.id:null;
 const report=(message,error=false)=>{if(inEditor){if(current?.id===conversationId)dockFeedback(message,error);}else localStatus(feedback,message,error);};
 if(inEditor)submitError='';
 try{
  report('Preparing download…');await flush();
  const r=await fetch(path);if(!r.ok){const e=await r.json();throw new Error(e.error||'Download failed.');}
  const blob=await r.blob(),url=URL.createObjectURL(blob),a=el('a',{href:url,download:path.endsWith('.zip')?'annotation-data.zip':path.endsWith('/current.json')?'current-annotations.json':'annotations.json'});
  document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
  report(path.endsWith('.zip')?'Research ZIP downloaded.':'JSON downloaded.');
 }catch(e){report(e.message,true);if(!inEditor&&!feedback)tell(e.message,true);}
}
async function goHome(){await flush();tell('');current=null;selected=null;history.replaceState(null,'','#home');await home();}
async function home(){document.body.classList.remove('annotating');replaceApp(el('p',{class:'loading'},'Loading conversations…'));const rows=await api('/api/conversations');
 const intro=el('div',{class:'page-intro'},el('h1',{},'Conversation annotation'),el('p',{},'Import a conversation and review its messages. Then highlight passages and answer the questions. Answers save automatically so you can return later. Submit when ready for analysis.'));
 const url=el('input',{type:'url',id:'share-url',placeholder:'https://chatgpt.com/share/…','aria-label':'Public ChatGPT shared link'});
 const importButton=action('Preview conversation →',async()=>{if(!url.value.trim())throw Error('Paste a public ChatGPT shared link first.');tell('Fetching the shared page…');await loadPreview({kind:'url',url:url.value.trim()});});
 const file=el('input',{type:'file',accept:'.json,application/json',class:'file-input','aria-label':'Import one conversation JSON',onchange:async()=>{try{if(!file.files[0])return;if(file.files[0].size>5000000)throw Error('JSON file is too large (5 MB limit).');await loadPreview({kind:'json',conversation:JSON.parse(await file.files[0].text())});}catch(e){tell(e.message,true);}}});
 const importCard=el('section',{class:'card'},el('h2',{},'Import a conversation'),el('label',{class:'field-label',for:'share-url'},'Public ChatGPT shared link'),el('div',{class:'import-row'},url,importButton),el('p',{class:'helper'},'Review the text before creating an annotation task. No ChatGPT credentials are requested.'),el('div',{class:'callout warning'},'A public share link is accessible to people who have it. Removing content here does not remove it from the shared page. Text only; images and attachments are not captured.'),el('div',{class:'divider'}),el('div',{class:'row'},action('Load example conversation',()=>loadPreview({kind:'demo'}),'secondary'),action('Load example annotations',()=>loadPreview({kind:'annotated_demo'}),'quiet')),el('p',{class:'helper'},'Seven fictional messages about requesting a written workplace check-in.'),el('details',{},el('summary',{},'Have conversation JSON instead?'),el('p',{class:'helper'},'Upload a conversation JSON file from the converter or a Label Studio export. Existing annotations will not be imported.'),file));

 const list=el('section',{class:'conversations-section'},el('div',{class:'row between'},el('h2',{},'Saved conversations'),el('span',{class:'small-text'},`${rows.length} conversations`)));
 if(!rows.length)list.append(el('div',{class:'empty'},'No saved conversations. Import a shared link or load the example above.'));
 for(const r of rows){const state=r.submission_version?(r.has_changes?'Draft changes · v'+r.submission_version+' submitted':'Submitted · v'+r.submission_version):'Draft';list.append(el('article',{class:'conversation-card'},el('div',{},el('h3',{},r.data.title),el('div',{class:'small-text'},`${r.data.dialogue.length} messages · ${new Date(r.updated_at).toLocaleString()}`),r.sync_error?el('div',{class:'small-text'},'Label Studio sync needs attention'):null),el('div',{class:'row'},el('span',{class:'tag '+(r.submission_version?'submitted':'')},state),action(r.submission_version?'Open annotations →':'Continue →',()=>openConversation(r.id),'secondary'))));}
 const exportFeedback=el('p',{class:'operation-status',role:'status','aria-live':'polite'});
 const exportAll=action('Export submitted data',()=>download('/api/export.zip',exportFeedback),'secondary');
 const hasSubmitted=rows.some(r=>r.submission_version>0);exportAll.disabled=!hasSubmitted;
 const exports=el('details',{class:'research-export'},el('summary',{},'Researcher export'),el('p',{class:'helper'},hasSubmitted?'Download the latest submitted annotations from all saved conversations. Draft changes are excluded.':'No submitted annotations yet. Submit a conversation to enable this research export.'),exportAll,exportFeedback);

 replaceApp(intro,importCard,list,exports);
}
async function loadPreview(body){preview=await api('/api/preview',body);current=null;history.replaceState(null,'','#review');renderPreview();tell('Review every message before confirming. You can exclude messages or edit sensitive details.');}
function renderPreview(){document.body.classList.remove('annotating');const d=preview.data;const title=el('input',{type:'text',value:d.title,'aria-label':'Conversation title'});const inputs=[];const content=el('div',{});
 d.dialogue.forEach((m,i)=>{const check=el('input',{type:'checkbox',checked:true,'aria-label':`Include message ${i+1}`});const text=el('textarea',{value:m.text,'aria-label':`Message ${i+1}, ${m.author}`});const card=el('article',{class:'card review-message'},el('label',{},check,`${m.author} · Message ${i+1}`),text);check.addEventListener('change',()=>{card.classList.toggle('excluded',!check.checked);text.disabled=!check.checked;});inputs.push({check,text,m});content.append(card);});
 const confirm=action('Confirm & start annotation →',async()=>{const messages=inputs.filter(x=>x.check.checked).map(x=>({message_id:x.m.message_id,text:x.text.value}));if(!messages.length)throw Error('Include at least one message.');tell('Saving your confirmed conversation and creating its Label Studio task…');const r=await api('/api/confirm',{preview_id:preview.preview_id,title:title.value,messages});preview=null;await openConversation(r.id);tell(r.sync_error?'Conversation saved locally. '+r.sync_error:'',!!r.sync_error);});
 replaceApp(steps(1),el('div',{class:'page-top'},button('← Back to conversations',goHome,'quiet'),el('h1',{},'Review your conversation'),el('p',{class:'muted'},`${d.dialogue.length} messages found. Exclude anything you do not want to share, or edit details before annotating.`)),el('div',{class:'callout'},preview.warning),preview.demo_annotations?el('div',{class:'callout'},'Saved example annotations are loaded only if you keep all messages and their text unchanged. These are test selections, not validated research labels.'):null,el('div',{class:'card'},el('label',{class:'field-label'},'Conversation title'),title),el('div',{class:'divider'}),content,el('div',{class:'review-actions'},button('← Cancel',goHome,'secondary'),confirm));
}
async function openConversation(id){await flush();current=await api('/api/conversations/'+id);generation=0;savedGeneration=0;savedDocument=structuredClone(current.document);fieldSaveError=null;validationIssues=[];submitError='';clearDockFeedback();selected=null;label=null;regionsOpen=false;history.replaceState(null,'','#conversation/'+id);renderEditor();resetEditorScroll(id);}
function resetEditorScroll(id){
 const reset=()=>{if(current?.id!==id)return;const side=document.querySelector('.annotation-side');if(side)side.scrollTop=0;window.scrollTo?.({top:0,left:0,behavior:'instant'});};
 document.querySelector('#conversation-title')?.focus({preventScroll:true});reset();
 if(typeof requestAnimationFrame==='function')requestAnimationFrame(reset);
}

function changed(){generation++;fieldSaveError=null;submitError='';clearDockFeedback();validationIssues=validationIssues.filter(issue=>requiredIssues(current.document).some(m=>m.region_id===issue.region_id&&m.field===issue.field));clearTimeout(timer);refreshAnswerFeedback();timer=setTimeout(()=>{save().catch(e=>tell(e.message,true));},650);}
function metadata(r){for(const k of ['revision','submission_version','has_changes','synced_version','sync_error','task_id','annotation_id','updated_at'])current[k]=r[k];}
function savedAnswer(regionId,name){const scope=regionId?savedDocument?.regions.find(r=>r.id===regionId)?.answers:savedDocument?.context;return scope?.[name]||'';}
function refreshAnswerFeedback(){
 document.querySelectorAll('.text-answer').forEach(q=>{
  const input=q.querySelector('.answer-input'),value=input.value,stored=savedAnswer(q.dataset.regionId,q.dataset.field);
  q.querySelector('.character-count').textContent=`${cp(value).length} characters`;
  q.querySelector('.answer-count').textContent=`${stored.length?1:0} / 1 saved answers`;
  const dirty=value!==stored,state=q.querySelector('.answer-state');
  state.textContent=dirty?(fieldSaveError?'Not saved. Retry saving.':saving?'Saving…':'Not saved yet'):(stored?'Saved to draft':'');
  state.classList.toggle('error',dirty&&!!fieldSaveError);
  q.querySelector('.retry-saving').hidden=!(dirty&&!!fieldSaveError);
 });
 refreshValidationFeedback();
 refreshDockStatus();
 const help=document.querySelector('#export-help');if(help){help.textContent=!current.submission_version?'Submit to enable research ZIP. Current JSON includes drafts.':current.has_changes||generation!==savedGeneration?'You have draft changes. Submit again to include them in research ZIP.':'Research ZIP contains the latest submitted version.';const control=document.querySelector('#zip-control');if(control){control.setAttribute('title',help.textContent);control.setAttribute('aria-label',help.textContent);}}
}
async function save(){
 if(!current||savedGeneration===generation)return;
 if(saving){await saving;return save();}
 const id=current.id,g=generation,document=structuredClone(current.document),revision=current.revision;
 fieldSaveError=null;refreshAnswerFeedback();
 saving=(async()=>{
  try{const r=await api(`/api/conversations/${id}/save`,{revision,document});metadata(r);savedDocument=structuredClone(document);savedGeneration=g;fieldSaveError=null;refreshAnswerFeedback();}
  catch(e){fieldSaveError=e.message;refreshAnswerFeedback();throw e;}
  finally{saving=null;refreshAnswerFeedback();}
 })();
 refreshAnswerFeedback();await saving;
}
async function flush(){clearTimeout(timer);if(saving)await saving;if(current&&savedGeneration!==generation)await save();}
async function retrySaving(){clearDockFeedback();await flush();refreshAnswerFeedback();}
function requiredIssues(doc){
 const issues=[];
 boot.codebook.fields.filter(f=>f.group==='conversation'&&f.required).forEach(f=>{const v=doc.context[f.name];if(typeof v==='string'?!v.trim():!v?.length)issues.push({region_id:'',region_number:null,field:f.name,prompt:f.prompt});});
 doc.regions.forEach((r,i)=>{
  const group=r.passage_type==='my text'?'user':'ai';
  boot.codebook.fields.filter(f=>f.group===group&&f.required).forEach(f=>{const v=r.answers[f.name];if(typeof v==='string'?!v.trim():!v?.length)issues.push({region_id:r.id,region_number:i+1,field:f.name,prompt:f.prompt});});
 });return issues;
}
function refreshValidationFeedback(){
 document.querySelectorAll('.question').forEach(q=>{const missing=validationIssues.some(m=>m.region_id===q.dataset.regionId&&m.field===q.dataset.field);q.classList.toggle('invalid',missing);const message=q.querySelector('.field-error');if(message)message.textContent=missing?'This answer is required.':'';const input=q.querySelector('.answer-input');if(input)input.setAttribute('aria-invalid',String(missing));});
}
function editorStatus(){
 const s=current.submission_version,unsaved=generation!==savedGeneration;
 const copy=s?`v${s} ${current.synced_version===s?'synced':'sync pending'}`:'';
 if(fieldSaveError)return 'Save failed — '+fieldSaveError;
 if(unsaved)return `${saving?'Saving…':'Unsaved changes'}${s?' · '+copy:''}`;
 if(!s)return 'Draft saved · not submitted';
 return current.has_changes?`Draft changes saved · ${copy}`:`Submitted ${copy}`;
}

async function submit(){
 if(submitting)return;submitting=true;submitError='';clearDockFeedback();
 document.querySelectorAll('#app button,#app input,#app textarea,#app select').forEach(n=>n.disabled=true);
 try{
  await flush();validationIssues=requiredIssues(current.document);
  if(validationIssues.length){selected=validationIssues[0].region_id;regionsOpen=true;submitError=`Complete ${validationIssues.length} required answer(s) before submitting. Your draft has been saved.`;return;}
  const document=structuredClone(current.document),g=generation;
  const r=await api(`/api/conversations/${current.id}/submit`,{revision:current.revision,document});
  metadata(r);savedDocument=structuredClone(document);savedGeneration=g;fieldSaveError=null;
  submitError=r.sync_error?'Submitted locally. The researcher storage copy needs attention; see Researcher: storage status.':'';
 }catch(e){validationIssues=e.issues||[];if(validationIssues.length){selected=validationIssues[0].region_id;regionsOpen=true;}submitError=e.message;}
 finally{
  submitting=false;renderEditor();
  if(validationIssues.length){const input=document.querySelector('#field-'+validationIssues[0].field);if(input){const focusable=input.matches?.('input,textarea')?input:input.querySelector('input');focusable?.focus();}}
 }
}
function chooseRegion(id){if(submitting)return;selected=id;label=null;window.getSelection()?.removeAllRanges();renderEditor();}
function regionQuote(r){return r.segments.map(s=>s.text).join('\n');}
function armLabel(value){
 if(submitting)return;
 label=value;
 document.querySelectorAll('[data-passage-label]').forEach(b=>{const armed=b.dataset.passageLabel===label;b.setAttribute('aria-pressed',String(armed));b.classList.toggle('armed',armed);});
 labelHint(`${label} selected. Highlight the exact text now.`);
}
function passageLabels(){
 return el('div',{class:'passage-labels',role:'group','aria-label':'Choose a label before highlighting'},...['my text',"AI's text"].map((value,i)=>buttonLabel(value,i)));
}
function buttonLabel(value,i){return el('button',{type:'button',class:'passage-label '+(i?'ai-label':'user-label')+(label===value?' armed':''),'data-passage-label':value,'aria-pressed':String(label===value),onclick:()=>armLabel(value)},el('span',{},value),el('kbd',{},i+1));}
function makeRegion(segments){
 if(!label||!segments?.length||submitting)return;
 const r={id:crypto.randomUUID().replaceAll('-','').slice(0,16),passage_type:label,segments:structuredClone(segments),answers:{}};
 current.document.regions.push(r);selected=r.id;label=null;window.getSelection()?.removeAllRanges();changed();renderEditor();
 const heading=document.querySelector('#question-heading');if(heading)heading.focus({preventScroll:true});
}
function findSelection(){
 if(!current||submitting)return;
 const sel=window.getSelection();if(!sel||sel.isCollapsed||!sel.rangeCount)return;
 const range=sel.getRangeAt(0),nodes=[...document.querySelectorAll('.message-text')];
 if(!nodes.some(n=>n.contains(range.startContainer))||!nodes.some(n=>n.contains(range.endContainer)))return;
 if(!label){labelHint('Choose my text (1) or AI’s text (2) before highlighting a new passage.');return;}
 const segments=[];
 for(const node of nodes){
  if(!range.intersectsNode(node))continue;
  const m=current.data.dialogue.find(m=>m.message_id===node.dataset.mid);let start=0,end=cp(m.text).length;
  if(node.contains(range.startContainer)){const r=document.createRange();r.selectNodeContents(node);r.setEnd(range.startContainer,range.startOffset);start=cp(r.toString()).length;}
  if(node.contains(range.endContainer)){const r=document.createRange();r.selectNodeContents(node);r.setEnd(range.endContainer,range.endOffset);end=cp(r.toString()).length;}
  if(end>start)segments.push({message_id:m.message_id,start,end,text:cp(m.text).slice(start,end).join('')});
 }
 if(segments.length)makeRegion(segments);
}
function messageNode(m,i){const body=el('div',{class:'message-text','data-mid':m.message_id});const text=cp(m.text),intervals=[];for(const r of current.document.regions)for(const s of r.segments)if(s.message_id===m.message_id)intervals.push({a:s.start,b:s.end,r});const bounds=[...new Set([0,text.length,...intervals.flatMap(x=>[x.a,x.b])])].sort((a,b)=>a-b);
 for(let k=0;k<bounds.length-1;k++){const a=bounds[k],b=bounds[k+1],active=intervals.filter(x=>x.a<=a&&x.b>=b),chunk=text.slice(a,b).join('');if(!active.length)body.append(document.createTextNode(chunk));else{const ids=active.map(x=>x.r.id);const span=el('span',{class:'highlight '+(active.length>1?'overlap':active[0].r.passage_type==="AI's text"?'ai':'')+(ids.includes(selected)?' selected':''),tabindex:'0',role:'button','aria-label':`Select ${active.length>1?'overlapping highlights':'highlight'}: ${chunk}`,onkeydown:e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseRegion(ids[0]);}},onclick:()=>{if(!window.getSelection()?.isCollapsed)return;chooseRegion(ids[0]);if(ids.length>1)tell('Overlapping highlights: choose the intended passage in the Regions list.');}},chunk);body.append(span);}}
 return el('article',{class:'message '+m.role},el('div',{class:'message-header'},el('span',{class:'speaker'},`${m.author} · ${i+1}`),button('Select whole message',()=>{if(!label){labelHint('Choose my text (1) or AI’s text (2), then select a whole message.');return;}makeRegion([{message_id:m.message_id,start:0,end:text.length,text:m.text}]);},'quiet small')),body);}
function question(f,answers){
 const id='field-'+f.name,regionId=f.group==='conversation'?'':selected;
 const q=el('div',{class:'question','data-field':f.name,'data-region-id':regionId});
 q.append(el('label',{for:id},f.prompt));
 if(f.help)q.append(el('p',{class:'help'},f.help));
 const error=el('p',{id:id+'-error',class:'field-error',role:'status'});
 if(f.type==='text'){
  q.classList.add('text-answer');
  const input=el(f.rows===1?'input':'textarea',{id,class:'answer-input',...(f.rows===1?{type:'text'}:{rows:String(f.rows||3)}),value:answers[f.name]||'','aria-describedby':id+'-feedback '+id+'-error','aria-required':String(!!f.required),...(f.required?{required:''}:{}),oninput:e=>{answers[f.name]=e.target.value;changed();}});
  const retry=action('Retry saving',retrySaving,'secondary retry-saving');retry.hidden=true;
  const feedback=el('div',{id:id+'-feedback',class:'answer-feedback'},el('div',{class:'answer-metadata'},el('span',{class:'character-count'}),el('span',{class:'answer-count'}),el('span',{class:'answer-state',role:'status','aria-live':'polite'})),retry);
  q.append(input,feedback,error);
 }else{
  const group=el('div',{id,role:f.type==='single'?'radiogroup':'group','aria-label':f.prompt,'aria-required':String(!!f.required),'aria-describedby':id+'-error'});
  f.options.forEach((option,i)=>{
   const checkbox=el('input',{type:f.type==='single'?'radio':'checkbox',name:f.name,id:`${id}-${i}`,checked:(answers[f.name]||[]).includes(option),onchange:e=>{const values=answers[f.name]||[];answers[f.name]=f.type==='single'?[option]:e.target.checked?[...values,option]:values.filter(v=>v!==option);changed();}});
   group.append(el('label',{class:'option',for:`${id}-${i}`},checkbox,option));
  });q.append(group,button('Clear this answer',()=>{answers[f.name]=[];changed();renderEditor();},'quiet small'),error);
 }return q;
}
function renderEditor(){if(!current)return;document.body.classList.add('annotating');const doc=current.document;const active=doc.regions.find(r=>r.id===selected);const top=el('div',{class:'editor-top'},el('div',{},button('← Your conversations',()=>goHome().catch(e=>tell(e.message,true)),'quiet back'),el('h1',{id:'conversation-title',tabindex:'-1'},current.data.title),el('p',{class:'small-text'},`${current.data.dialogue.length} messages`)));
 const convo=el('section',{class:'editor-conversation','aria-label':'Conversation transcript',onmouseup:()=>setTimeout(findSelection,0),onkeyup:e=>{if(e.key==='Shift')findSelection();}},
  el('h2',{},'Your conversation'),
  el('p',{class:'annotation-instructions'},"To annotate: 1) choose ‘my text’ (key 1) or ‘AI’s text’ (key 2), 2) highlight the exact text with your mouse. Choose the label again before each new highlight. To annotate a whole message, choose a label and use Select whole message. Highlights can overlap."),
  passageLabels(),el('p',{id:'label-status',class:'label-status',role:'status','aria-live':'polite'},label?`${label} selected. Highlight the exact text now.`:'Choose a label before highlighting.'),
  ...current.data.dialogue.map(messageNode));
 const regions=el('details',{class:'regions-panel',ontoggle:e=>{if(e.target.isConnected)regionsOpen=e.target.open;}});
 regions.open=regionsOpen;
 regions.append(el('summary',{},`Regions (${doc.regions.length})`,selected?el('span',{class:'selected-region-note'},` · selected #${doc.regions.findIndex(r=>r.id===selected)+1}`):null));
 if(!doc.regions.length)regions.append(el('p',{class:'small-text'},'Your highlights will appear here. You can also click a highlight in the conversation to edit its answers.'));
 const regionList=el('div',{class:'region-list'});doc.regions.forEach((r,i)=>regionList.append(regionButton(r,i)));regions.append(regionList);
 const questions=el('section',{class:'annotation-panel '+(active?.passage_type==="AI's text"?'ai-panel':'user-panel')});
 if(active){questions.append(el('div',{class:'panel-heading'},el('h2',{id:'question-heading',tabindex:'-1'},active.passage_type==='my text'?'Your words':"AI’s text"),button('Deselect',()=>chooseRegion(null),'quiet small')),el('blockquote',{class:'selected-passage'},regionQuote(active)));
 const roles=active.segments.map(s=>current.data.dialogue.find(m=>m.message_id===s.message_id).role);const expected=active.passage_type==='my text'?'user':'assistant';if(roles.some(r=>r!==expected))questions.append(el('div',{class:'callout warning'},'This passage label differs from one or more source-message roles. Both values are preserved; this is not automatically corrected.'));
 boot.codebook.fields.filter(f=>f.group===(active.passage_type==='my text'?'user':'ai')).forEach(f=>questions.append(question(f,active.answers)));
 questions.append(el('div',{class:'submit-box'},button('Delete this highlight',()=>{if(!confirm('Delete this highlight and its answers?'))return;doc.regions=doc.regions.filter(r=>r.id!==active.id);selected=null;changed();renderEditor();},'danger')));
 }
 const context=el('section',{class:'annotation-panel conversation-panel'},el('h2',{},'About this conversation'),el('p',{class:'small-text'},'Background for the whole conversation, independent of individual highlights.'));boot.codebook.fields.filter(f=>f.group==='conversation').forEach(f=>context.append(question(f,doc.context)));
 const jsonButton=action('Download current JSON',()=>download(`/api/conversations/${current.id}/current.json`),'secondary');
 const zipButton=action('Download research ZIP',()=>download(`/api/conversations/${current.id}/export.zip`),'secondary');
 zipButton.disabled=!current.submission_version;jsonButton.setAttribute('title','Download current saved work, including drafts.');zipButton.setAttribute('aria-describedby','export-help');
 const zipControl=el('span',{id:'zip-control',class:'download-control',...(zipButton.disabled?{tabindex:'0',role:'group'}:{})},zipButton);
 const research=el('section',{class:'research-panel action-dock','aria-label':'Annotation actions'},
  el('div',{class:'action-dock-inner'},
   el('div',{class:'dock-main'},
    el('div',{id:'submission-status',class:'dock-status',role:'status','aria-live':'polite'},editorStatus()),
    el('div',{class:'button-bar'},jsonButton,zipControl,action('Submit annotations',submit))),
   el('span',{id:'export-help',class:'visually-hidden'})));
 const storage=el('details',{class:'storage-details'},el('summary',{},'Researcher: storage status'),el('p',{class:'small-text'},'Label Studio keeps a copy of submitted annotations. Drafts are stored locally. Retrying storage does not submit drafts.'));
 storage.append(el('p',{class:'small-text'},current.sync_error|| (current.submission_version&&current.synced_version===current.submission_version?'The submitted copy is up to date.':current.submission_version?'The submitted copy is pending.':'No submitted annotations to copy yet.')));
 if(current.sync_error||(current.submission_version&&current.synced_version<current.submission_version)){
  const feedback=el('p',{class:'operation-status',role:'status','aria-live':'polite'});
  storage.append(action('Retry storage copy',async()=>{try{await flush();const r=await api(`/api/conversations/${current.id}/sync`,{});metadata(r);refreshAnswerFeedback();localStatus(feedback,r.sync_error||'Storage copy is up to date.',!!r.sync_error);}catch(e){localStatus(feedback,e.message,true);}},'secondary'),feedback);
 }


 notice.textContent='';replaceApp(top,el('div',{class:'editor-grid'},convo,el('aside',{class:'annotation-side'},regions,active?questions:null,context,storage)),research);
 if(typeof ResizeObserver!=='undefined'){actionBarObserver=new ResizeObserver(entries=>{document.documentElement.style.setProperty('--action-dock-height',`${Math.ceil(entries[0].target.getBoundingClientRect().height)}px`);});actionBarObserver.observe(research);}
 refreshAnswerFeedback();}
function regionButton(r,i){const b=button('',()=>chooseRegion(r.id),'region-item'+(r.id===selected?' active':''));b.append(el('span',{},`${i+1} · ${r.passage_type} · ${Object.values(r.answers).filter(v=>v.length).length} answers`),regionQuote(r).slice(0,130));return b;}
window.addEventListener('keydown',e=>{if(!current||submitting||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)||e.ctrlKey||e.metaKey||e.altKey)return;if(e.key==='1'||e.key==='2'){e.preventDefault();armLabel(e.key==='1'?'my text':"AI's text");}});
window.addEventListener('beforeunload',e=>{if(generation!==savedGeneration){e.preventDefault();e.returnValue='';}});
(async()=>{try{boot=await api('/api/bootstrap');const match=location.hash.match(/^#conversation\/([a-f0-9]+)$/);if(match)await openConversation(match[1]);else await home();}catch(e){replaceApp(el('div',{class:'callout warning'},e.message));}})();
