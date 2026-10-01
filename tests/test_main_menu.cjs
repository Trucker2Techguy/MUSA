'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function boot(client,saved){
 const elements=new Map(),storage=new Map(saved?[['musa-session',JSON.stringify(saved)]]:[]);
 const canvas=new Proxy({}, {get:(o,k)=>o[k]||(()=>{})});
 function element(id){if(!elements.has(id))elements.set(id,{hidden:false,value:'',disabled:false,textContent:'',
  focus(){this.focused=true},getContext:()=>canvas,querySelectorAll:()=>[],append(){},replaceChildren(){},setAttribute(){},classList:{toggle(){}}});return elements.get(id)}
 const timers=new Map(),intervals=new Map(),sockets=[],requests=[];let sequence=0;
 class Socket{
  static OPEN=1;static CONNECTING=0;
  constructor(){this.readyState=0;this.sent=[];sockets.push(this)}
  send(data){this.sent.push(JSON.parse(data))}
  connect(){this.readyState=1;this.onopen?.()}
  close(){this.readyState=3;this.onclose?.()}
 }
 const context=vm.createContext({document:{getElementById:element,createElement:()=>element(`generated-${++sequence}`),activeElement:{tagName:'BODY'}},
  window:{MUSA_WS_URL:'wss://test',addEventListener(){}},WebSocket:Socket,
  localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
  setTimeout:f=>{timers.set(++sequence,f);return sequence},clearTimeout:id=>timers.delete(id),
  setInterval:f=>{intervals.set(++sequence,f);return sequence},clearInterval:id=>intervals.delete(id),
  crypto:{randomUUID:()=>`request-${++sequence}`},
  fetch:(url,options)=>new Promise(resolve=>requests.push({url,options,resolve})),
 });
 vm.runInContext(fs.readFileSync(`static/${client}.js`,'utf8'),context);
 return {element,storage,timers,intervals,sockets,requests,context};
}
const snapshot=(type,mode,phase='playing')=>({code:'ABCDE',gameType:type,mode,phase,version:3,you:0,
 board:Array(9).fill(null),turn:0,winner:null,winningLine:[],players:[{name:'Human',mark:'X',facing:'N',delay:0},{name:'Other',mark:'O',facing:'N',delay:0}],
 commands:0,elapsed:0,message:'Ready',size:17,cells:[],landmarks:[],activated:[false,false]});
function checkMenu(app){
 assert.equal(app.element('selection').hidden,false);
 assert.equal(app.element('game').hidden,true);
 assert.equal(app.element('saved-session').hidden,true);
 assert.equal(app.element('mode-selection').hidden,true);
 assert.equal(app.element('entry').hidden,false);
 assert.equal(app.element('join-entry').hidden,false);
 assert.equal(app.storage.has('musa-session'),false);
 assert.equal(app.element('code').value,'');
 assert.equal(app.element('select-maze').focused,true);
 assert.equal(vm.runInContext('session===null && state===null && !busy',app.context),true);
}
async function settle(){await new Promise(resolve=>setImmediate(resolve))}
async function respond(request,value){request.resolve({ok:true,json:async()=>value});await settle()}
(async()=>{
 assert.match(fs.readFileSync('static/index.html','utf8'),/id="main-menu">&lt; MAIN MENU/);
 for(const [type,mode] of [['maze','network'],['tictactoe','computer'],['tictactoe','network']]){
  for(const phase of ['lobby','playing','won','draw']){
   if(type==='maze'&&phase==='draw')continue;
   const app=boot('realtime');const old=app.sockets[0];old.connect();
   const oldMessage=old.onmessage,oldClose=old.onclose;
   oldMessage({data:JSON.stringify({type:'session',code:'ABCDE',token:'secret',state:snapshot(type,mode,phase)})});
   app.element('code').value='STALE';
   vm.runInContext("act('command',{command:0})",app.context);
   app.element('main-menu').onclick();checkMenu(app);
   assert.equal(old.readyState,3);assert.equal(old.onmessage,null);
   assert.equal(app.timers.size,0);assert.equal(app.intervals.size,0);
   assert.equal(old.sent.filter(m=>m.action==='command').length,1);
   oldMessage({data:JSON.stringify({type:'session',code:'ABCDE',token:'secret',state:snapshot(type,mode)})});
   oldClose();checkMenu(app);assert.equal(app.timers.size,0);
   const fresh=app.sockets[1];fresh.connect();assert.equal(fresh.sent.length,0);
   app.element('select-ttt').onclick();app.element('mode-computer').onclick();app.element('create').onclick();
   assert.equal(fresh.sent[0].action,'create');assert.equal(fresh.sent[0].mode,'computer');
   assert.equal('token' in fresh.sent[0],false);
   assert.equal(fresh.sent.some(m=>['leave','delete','replay','resume'].includes(m.action)),false);
  }
  const local=boot('app');
  vm.runInContext(`connect(${JSON.stringify({token:'secret',state:snapshot(type,mode)})})`,local.context);
  const poll=vm.runInContext('poll()',local.context);const latePoll=local.requests.at(-1);
  const move=vm.runInContext("act('command',{action:0})",local.context);const lateMove=local.requests.at(-1);
  local.element('main-menu').onclick();checkMenu(local);assert.equal(local.intervals.size,0);
  local.element('select-ttt').onclick();local.element('mode-network').onclick();
  local.element('create').onclick();const freshRequest=local.requests.at(-1);
  assert.equal(JSON.parse(freshRequest.options.body).mode,'network');
  await respond(latePoll,snapshot(type,mode));await poll;
  await respond(lateMove,{state:snapshot(type,mode)});await move;
  assert.equal(vm.runInContext('busy',local.context),true);
  assert.equal(local.element('game').hidden,true);assert.equal(local.storage.has('musa-session'),false);
  await respond(freshRequest,{token:'new-token',state:snapshot('tictactoe','network','lobby')});
  assert.equal(local.element('game').hidden,false);assert.equal(JSON.parse(local.storage.get('musa-session')).token,'new-token');
 }
 // Cancel in-flight create: the late response must not restore the abandoned room.
 const pending=boot('app');pending.element('create').onclick();const request=pending.requests[0];pending.element('main-menu').onclick();
 await respond(request,{token:'abandoned',state:snapshot('maze','network')});checkMenu(pending);assert.equal(pending.intervals.size,0);
 // Preserve saved-session resume unless the user deliberately chooses MAIN MENU.
 const saved={code:'ABCDE',token:'secret'},resume=boot('realtime',saved);resume.sockets[0].connect();resume.element('resume').onclick();
 assert.deepEqual(resume.sockets[0].sent[0],{action:'resume',...saved});resume.element('main-menu').onclick();checkMenu(resume);
 const startup=boot('app',saved);const delayed=startup.requests[0];startup.element('main-menu').onclick();
 await respond(delayed,snapshot('tictactoe','computer'));checkMenu(startup);assert.equal(startup.intervals.size,0);
 // MAIN MENU is available during mode selection too.
 const modeScreen=boot('realtime');modeScreen.element('select-ttt').onclick();modeScreen.element('main-menu').onclick();checkMenu(modeScreen);
 console.log('MAIN MENU regressions passed: both clients, all games/modes, active/completed/lobby screens, stale replies, pending requests, fresh creation and saved resume');
})().catch(error=>{console.error(error);process.exitCode=1});
