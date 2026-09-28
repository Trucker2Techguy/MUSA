const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync('static/realtime.js', 'utf8');

function boot(saved) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {hidden: id === 'saved-session', value: '', disabled: false,
      getContext: () => ({}), addEventListener() {}, querySelectorAll: () => [],
      replaceChildren() {}, classList: {toggle() {}}, textContent: ''});
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
  vm.runInNewContext(script, {document: {getElementById: element}, window: {MUSA_WS_URL: 'wss://test', addEventListener() {}},
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
