const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync('static/realtime.js', 'utf8');

function boot(saved) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {hidden: id === 'saved-session', value: '', disabled: false,
      getContext: () => ({}), addEventListener() {}, querySelectorAll: () => [],
      focus() {}, append() {}, setAttribute() {}, replaceChildren() {}, classList: {toggle() {}}, textContent: ''});
    return elements.get(id);
  };
  const storage = new Map(saved ? [['musa-session', JSON.stringify(saved)]] : []);
  const sockets = [];
  const timers = [];
  class Socket {
    static OPEN = 1;
    static CONNECTING = 0;
    constructor() { this.readyState = 0; this.sent = []; sockets.push(this); }
    send(value) { this.sent.push(JSON.parse(value)); }
    close() { this.readyState = 3; if (this.onclose) this.onclose(); }
    connect() { this.readyState = 1; this.onopen(); }
  }
  vm.runInNewContext(script, {document: {getElementById: element, createElement: () => ({append() {}, classList: {toggle() {}}})}, window: {MUSA_WS_URL: 'wss://test', addEventListener() {}},
    localStorage: {getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)},
    WebSocket: Socket, setInterval: () => 1, clearInterval() {}, setTimeout: callback => { timers.push(callback); return timers.length; }, clearTimeout() {}, crypto: {randomUUID: () => 'id'}});
  return {element, storage, sockets, timers};
}

const saved = {code: 'ABCDE', token: 'secret'};
const resumed = boot(saved);
assert.equal(resumed.element('entry').hidden, true);
assert.equal(resumed.element('saved-session').hidden, false);
resumed.sockets[0].connect();
assert.deepEqual(resumed.sockets[0].sent, []);
resumed.element('resume').onclick();
assert.deepEqual(resumed.sockets[0].sent[0], {action: 'resume', ...saved});
resumed.sockets[0].close();
resumed.timers.shift()();
resumed.sockets[1].connect();
assert.deepEqual(resumed.sockets[1].sent[0], {action: 'resume', ...saved});

const fresh = boot(saved);
fresh.element('new-session').onclick();
assert.equal(fresh.storage.has('musa-session'), false);
assert.equal(fresh.element('saved-session').hidden, true);
assert.equal(fresh.element('entry').hidden, false);
fresh.sockets[1].connect();
assert.deepEqual(fresh.sockets[1].sent, []);
fresh.element('create').onclick();
assert.equal(fresh.sockets[1].sent[0].action, 'create');
console.log('saved-session startup regression passed');

const platform = boot();
platform.sockets[0].connect();
platform.element('select-ttt').onclick();
assert.equal(platform.element('mode-selection').hidden,false);
assert.equal(platform.element('entry').hidden,true);
platform.element('mode-network').onclick();
platform.element('create').onclick();
assert.equal(platform.sockets[0].sent[0].gameType, 'tictactoe');
const ttt = {code:'ABCDE',gameType:'tictactoe',phase:'playing',version:3,you:0,
 board:Array(9).fill(null),turn:0,winner:null,winningLine:[],
 players:[{name:'A',mark:'X'},{name:'B',mark:'O'}],commands:0,elapsed:0,message:'X to move'};
platform.sockets[0].onmessage({data:JSON.stringify({type:'session',code:'ABCDE',token:'token',state:ttt})});
assert.equal(platform.element('map').hidden,true);
assert.equal(platform.element('ttt-board').hidden,false);
assert.equal(platform.element('controls').hidden,true);
assert.equal(platform.element('selection').hidden,true);
platform.element('ttt-board').onclick({target:{closest:()=>({disabled:false,dataset:{square:'4'}})}});
assert.equal(platform.sockets[0].sent.at(-1).command,4);
assert.equal(platform.sockets[0].sent.at(-1).action,'command');
platform.sockets[0].onmessage({data:JSON.stringify({type:'state',requestId:'id',state:{...ttt,version:4,phase:'draw'}})});
assert.equal(platform.element('replay').hidden,false);
const joiner=boot();joiner.sockets[0].connect();joiner.element('join').onclick();
assert.equal('gameType' in joiner.sockets[0].sent[0],false);
console.log('simulation selection, room-derived rendering, square command and draw replay regressions passed');

const solo=boot();solo.sockets[0].connect();solo.element('select-ttt').onclick();
solo.element('mode-computer').onclick();
assert.equal(solo.element('join-entry').hidden,true);
assert.equal(solo.element('entry').hidden,false);
solo.element('create').onclick();
assert.equal(solo.sockets[0].sent[0].mode,'computer');
solo.sockets[0].onmessage({data:JSON.stringify({type:'session',code:'ABCDE',token:'human',state:{...ttt,mode:'computer'}})});
assert.equal(solo.element('mode-selection').hidden,true);
assert.equal(solo.element('ttt-board').hidden,false);
assert.equal(solo.element('hint').textContent.includes('M.U.S.A.'),true);
assert.equal(solo.element('start').hidden,true);
console.log('solo/network mode selection and shared solo renderer regressions passed');
