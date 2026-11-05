// Exercise the actual frontend state machine without a browser or UI automation.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
class Element {
 constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.attributes={};this.dataset={};this.events={};this.value='';this.disabled=false;this.isConnected=true;this.className='';this._text='';}
 append(...nodes){for(const n of nodes){const child=n instanceof Element?n:new Text(String(n));this.children.push(child);child.parent=this;}}
 replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes);}
 get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}
 set textContent(value){this._text=String(value);this.children=[];}
 addEventListener(name,fn){this.events[name]=fn;}
 setAttribute(name,value){this.attributes[name]=String(value);if(name==='id')this.id=String(value);if(name.startsWith('data-'))this.dataset[name.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(value);}
 getAttribute(name){return this.attributes[name]??null;}
 get classList(){const self=this;return{add(...names){self.className=[...new Set([...self.className.split(/\s+/).filter(Boolean),...names])].join(' ');},remove(...names){self.className=self.className.split(/\s+/).filter(n=>!names.includes(n)).join(' ');},toggle(name,force){const has=self.className.split(/\s+/).includes(name);const want=force===undefined?!has:force;if(want)this.add(name);else this.remove(name);return want;},contains(name){return self.className.split(/\s+/).includes(name);}};}
 matches(selector){if(selector.startsWith('#'))return this.id===selector.slice(1);if(selector.startsWith('.'))return this.classList.contains(selector.slice(1));if(selector==='[data-passage-label]')return !!this.dataset.passageLabel;return this.tagName===selector.toUpperCase();}
 querySelectorAll(selector){const selectors=selector.split(',').map(s=>s.trim());const out=[];function walk(node){for(const child of node.children){if(selectors.some(s=>child.matches(s.replace(/^#app /,''))))out.push(child);walk(child);}}walk(this);return out;}
 querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
 focus(){}click(){return this.events.click?.({target:this,currentTarget:this});}scrollIntoView(){}
}
class Text extends Element{constructor(text){super('#text');this._text=text;}}
function setup(){
 const body=new Element('body'),app=new Element('main'),notice=new Element();app.id='app';notice.id='notice';body.append(notice,app);
 const document={body,createElement:tag=>new Element(tag),createTextNode:t=>new Text(t),querySelector:s=>body.querySelector(s),querySelectorAll:s=>body.querySelectorAll(s)};
 let sequence=0;const state={rejectSave:false,gate:null,requests:[],revision:0,document:null,downloadError:false};
 const ctx=vm.createContext({document,Node:Element,console,structuredClone,URL,Blob,crypto:{randomUUID:()=>`test-region-${++sequence}`},confirm:()=>true,history:{replaceState(){}},location:{hash:''},window:{addEventListener(){},getSelection(){return{removeAllRanges(){},isCollapsed:true};}},setTimeout:()=>1,clearTimeout(){},fetch:async(url,options)=>{
  const payload=options?.body?JSON.parse(options.body):null;state.requests.push({url,payload});
  if(url.endsWith('/save')){if(state.gate)await state.gate;if(state.rejectSave)return{ok:false,json:async()=>({error:'Simulated offline save'})};state.document=structuredClone(payload.document);state.revision++;return{ok:true,json:async()=>({revision:state.revision,submission_version:0,synced_version:0,has_changes:true,sync_error:null})};}
  if(url.endsWith('/submit'))return{ok:true,json:async()=>({revision:++state.revision,submission_version:1,synced_version:1,has_changes:false,sync_error:null})};
  if((url.endsWith('.json')||url.endsWith('.zip'))&&state.downloadGate)await state.downloadGate;
  if(url.endsWith('.json')||url.endsWith('.zip'))return{ok:!state.downloadError,json:async()=>({error:'Export failed nearby'}),blob:async()=>new Blob(['test'])};
  throw Error('Unexpected request: '+url);
 }});
 let source=fs.readFileSync(path.join(ROOT,'app/static/app.js'),'utf8');source=source.slice(0,source.lastIndexOf('(async()=>{try{boot='));vm.runInContext(source,ctx);
 const fixture=JSON.parse(fs.readFileSync(path.join(ROOT,'fixtures/demo.json'),'utf8'));
 ctx.__data=fixture.data;ctx.__book=JSON.parse(fs.readFileSync(path.join(ROOT,'config/codebook.json'),'utf8'));
 vm.runInContext(`boot={csrf:'test',codebook:__book};current={id:'fake',data:__data,document:{regions:[],context:{}},revision:0,submission_version:0,synced_version:0,has_changes:true};savedDocument=structuredClone(current.document);renderEditor();`,ctx);
 return{ctx,state,document,app,run:s=>vm.runInContext(s,ctx)};
}
function add(s,type='my text'){
 s.ctx.__type=type;s.run(`armLabel(__type);makeRegion([{message_id:current.data.dialogue[0].message_id,start:0,end:6,text:current.data.dialogue[0].text.slice(0,6)}]);`);
}
function type(s,id,value){const input=s.document.querySelector('#'+id);assert.ok(input,'Text input must exist');input.value=value;input.events.input({target:input});return input;}
test('label-first flow, disarming, collapsed regions, no duplicate type selector',()=>{
 const s=setup();assert.equal(s.document.querySelectorAll('.passage-label').length,2);assert.doesNotMatch(s.app.textContent,/How to annotate|Questions marked/);
 s.run(`makeRegion([{message_id:current.data.dialogue[0].message_id,start:0,end:6,text:'I need'}])`);assert.equal(s.run('current.document.regions.length'),0);
 add(s);assert.equal(s.run('current.document.regions.length'),1);assert.equal(s.run('label'),null);
 assert.equal(s.document.querySelector('.regions-panel').open,false);assert.equal(s.document.querySelectorAll('select').length,0);
 assert.ok(s.document.querySelector('#field-user_why'));assert.equal(s.document.querySelector('#field-ai_behavior_explanation'),null);
 const details=s.document.querySelector('.regions-panel');details.open=true;details.events.toggle({target:details});s.run('renderEditor()');assert.equal(s.document.querySelector('.regions-panel').open,true);
 add(s,"AI's text");assert.ok(s.document.querySelector('#field-ai_behavior_explanation'));assert.equal(s.run('label'),null);
});
test('character counter and saved-answer status follow server acknowledgement',async()=>{
 const s=setup();add(s);let input=type(s,'field-user_why','Hi😀');let q=input.parent;
 assert.equal(q.querySelector('.character-count').textContent,'3 characters');assert.equal(q.querySelector('.answer-count').textContent,'0 / 1 saved answers');assert.equal(q.querySelector('.answer-state').textContent,'Not saved yet');
 let release;s.state.gate=new Promise(r=>release=r);const pending=s.run('save()');await Promise.resolve();assert.equal(q.querySelector('.answer-state').textContent,'Saving…');release();await pending;
 assert.equal(q.querySelector('.answer-state').textContent,'Saved to draft');assert.equal(q.querySelector('.answer-count').textContent,'1 / 1 saved answers');
 input=type(s,'field-user_why','');q=input.parent;await s.run('flush()');assert.equal(q.querySelector('.answer-count').textContent,'0 / 1 saved answers');assert.equal(s.state.document.regions[0].answers.user_why,'');
});
test('failed saves never report saved; retry recovers latest text',async()=>{
 const s=setup();add(s);const input=type(s,'field-user_why','Keep my explanation');s.state.rejectSave=true;
 await assert.rejects(s.run('save()'),/Simulated offline/);assert.match(s.document.querySelector('#submission-status').textContent,/Save failed/);assert.equal(input.parent.querySelector('.answer-count').textContent,'0 / 1 saved answers');assert.equal(input.parent.querySelector('.answer-state').textContent,'Not saved. Retry saving.');
 s.run("tell(fieldSaveError,true)");s.state.rejectSave=false;await input.parent.querySelector('.retry-saving').click();assert.doesNotMatch(s.document.querySelector('#submission-status').textContent,/offline|failed/i);assert.equal(input.parent.querySelector('.answer-state').textContent,'Saved to draft');assert.equal(s.state.document.regions[0].answers.user_why,'Keep my explanation');
});
test('in-flight edits and region switching do not lose text or mislabel saved status',async()=>{
 const s=setup();add(s);type(s,'field-user_why','First');let release;s.state.gate=new Promise(r=>release=r);const pending=s.run('save()');await Promise.resolve();type(s,'field-user_why','Latest');release();await pending;s.state.gate=null;
 assert.equal(s.document.querySelector('#field-user_why').parent.querySelector('.answer-state').textContent,'Not saved yet');await s.run('flush()');assert.equal(s.state.document.regions[0].answers.user_why,'Latest');
 s.run('chooseRegion(null)');s.run('chooseRegion(current.document.regions[0].id)');assert.equal(s.document.querySelector('#field-user_why').value,'Latest');assert.equal(s.document.querySelector('#field-user_why').parent.querySelector('.answer-count').textContent,'1 / 1 saved answers');
});
test('automatic saving includes latest global text in formal submission without manual save controls',async()=>{
 const s=setup();type(s,'field-conversation_accessibility_context','Support goal');type(s,'field-conversation_additional_context','Newest explanation');await s.run('submit()');
 const submission=s.state.requests.find(r=>r.url.endsWith('/submit'));assert.equal(submission.payload.document.context.conversation_accessibility_context,'Support goal');assert.equal(submission.payload.document.context.conversation_additional_context,'Newest explanation');assert.equal(s.run('submitting'),false);
 assert.equal(s.document.querySelector('.save-answer'),null);assert.equal(s.document.querySelector('.save-shortcut'),null);
 type(s,'field-conversation_additional_context','Draft after submission');assert.match(s.document.querySelector('#export-help').textContent,/draft changes/);assert.match(s.document.querySelector('#submission-status').textContent,/Unsaved changes/);
});
test('required rules and one-line Other input; optional wording is not repeated',async()=>{
 const s=setup();add(s);
 const other=s.document.querySelector('#field-user_where_other');assert.equal(other.tagName,'INPUT');assert.equal(other.attributes['aria-required'],'false');
 assert.equal(s.document.querySelector('#field-user_why').attributes['aria-required'],'true');assert.equal(s.document.querySelectorAll('.optional').length,0);assert.equal(s.document.querySelectorAll('.required-mark').length,0);
 assert.equal(s.document.querySelector('#field-user_why').parent.querySelector('.answer-state').textContent,'');
 await s.run('submit()');assert.equal(s.state.requests.some(r=>r.url.endsWith('/submit')),false);
 assert.match(s.document.querySelector('#submission-status').textContent,/required/);assert.equal(s.run('validationIssues.length'),11);
 for(const f of JSON.parse(fs.readFileSync(path.join(ROOT,'config/codebook.json'))).fields.filter(f=>f.group==='user'&&f.required)){s.ctx.__name=f.name;s.ctx.__value=f.type==='text'?'Required test answer':[f.options[0]];s.run('current.document.regions[0].answers[__name]=__value;changed()');}
 for(const f of JSON.parse(fs.readFileSync(path.join(ROOT,'config/codebook.json'))).fields.filter(f=>f.group==='conversation'&&f.required)){s.ctx.__name=f.name;s.ctx.__value='Required context';s.run('current.document.context[__name]=__value;changed()');}
 await s.run('submit()');assert.equal(s.state.requests.filter(r=>r.url.endsWith('/submit')).length,1);
});
test('research ZIP is disabled before submission, draft JSON remains usable and errors are inline',async()=>{
 const s=setup();const panel=s.document.querySelector('.research-panel'),buttons=panel.querySelectorAll('button');
 assert.equal(panel.classList.contains('action-dock'),true);assert.equal(panel.querySelector('.dock-description'),null);assert.equal(panel.querySelector('#save-status'),null);assert.equal(panel.querySelector('#export-help').classList.contains('visually-hidden'),true);assert.match(panel.querySelector('#zip-control').getAttribute('title'),/Submit to enable/);assert.equal(buttons[2].textContent,'Submit annotations');assert.equal(s.app.querySelectorAll('button').filter(b=>b.textContent==='Submit annotations').length,1);
 s.run("tell('Save failed near controls',true)");assert.equal(s.document.querySelector('#notice').textContent,'');assert.equal(s.document.querySelector('#submission-status').textContent,'Save failed near controls');
 s.run("labelHint('Choose a label first')");assert.equal(s.document.querySelector('#label-status').textContent,'Choose a label first');
 assert.equal(buttons[0].textContent,'Download current JSON');assert.equal(buttons[1].textContent,'Download research ZIP');assert.equal(buttons[1].disabled,true);
 assert.match(panel.textContent,/Submit to enable research ZIP/);await buttons[1].click();assert.equal(s.state.requests.length,0);
 s.state.downloadError=true;await buttons[0].click();assert.equal(s.document.querySelector('#submission-status').textContent,'Export failed nearby');assert.equal(s.document.querySelector('#notice').textContent,'');
 s.state.downloadError=false;await buttons[0].click();assert.match(s.document.querySelector('#submission-status').textContent,/JSON downloaded/);
 s.run('current.submission_version=1;current.synced_version=1;renderEditor()');const zip=s.document.querySelector('.research-panel').querySelectorAll('button')[1];await zip.click();assert.equal(s.document.querySelector('#submission-status').textContent,'Research ZIP downloaded.');assert.equal(s.document.querySelector('.research-panel').querySelector('.operation-status'),null);
});

test('a late download result cannot replace another conversation status',async()=>{
 const s=setup();let release;s.state.downloadGate=new Promise(r=>release=r);
 const pending=s.run("download('/api/conversations/fake/current.json')");await Promise.resolve();await Promise.resolve();
 s.run("current.id='another';clearDockFeedback();renderEditor()");release();await pending;
 assert.equal(s.document.querySelector('#submission-status').textContent,'Draft saved · not submitted');
});
