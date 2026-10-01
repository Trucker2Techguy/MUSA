'use strict';
const $ = id => document.getElementById(id);
let selectedGame = 'maze', selectedMode = 'network';
const canvas = $('map'), ctx = canvas.getContext('2d');
let session = null, state = null, socket = null, busy = false, pending = null;
let retry = 0, reconnectTimer = null, heartbeat = null, commandTimer = null, awaitingResume = false, resumeSelected = false;
try { session = JSON.parse(localStorage.getItem('musa-session') || 'null'); } catch { localStorage.removeItem('musa-session'); }
if(session?.code&&session?.token){$('selection').hidden=true;$('saved-session').hidden=false;$('entry').hidden=true}
else session=null;
function alertUser(message){const box=$('toast');box.textContent=message;box.hidden=false;clearTimeout(box.timer);box.timer=setTimeout(()=>box.hidden=true,3500)}
function send(data){if(socket?.readyState!==WebSocket.OPEN)return false;socket.send(JSON.stringify(data));return true}
function openSocket(){
 if(socket && (socket.readyState===WebSocket.CONNECTING||socket.readyState===WebSocket.OPEN))return;
 socket=new WebSocket(window.MUSA_WS_URL);
 socket.onopen=()=>{
  retry=0;$('signal').textContent='SIGNAL NOMINAL';
  if(resumeSelected&&session?.code&&session?.token){awaitingResume=true;send({action:'resume',...session});}
  else if(pending)send(pending);
  clearInterval(heartbeat);heartbeat=setInterval(()=>send({action:'ping'}),4*60*1000);
 };
 socket.onmessage=e=>{let message;try{message=JSON.parse(e.data)}catch{return}
  if(message.type==='pong')return;
  if(message.type==='error'){
   if(message.requestId && pending?.requestId && message.requestId!==pending.requestId)return;
   clearTimeout(commandTimer);busy=false;
   if(awaitingResume&&session&&/expired|not a member|not found/i.test(message.error||'')){
    session=null;state=null;awaitingResume=false;resumeSelected=false;localStorage.removeItem('musa-session');$('game').hidden=true;$('saved-session').hidden=true;$('entry').hidden=false;$('selection').hidden=false;
   }
   pending=null;alertUser(message.error||'Command rejected.');return;
  }
  if(message.type==='session'){
   session={code:message.code,token:message.token};resumeSelected=true;localStorage.setItem('musa-session',JSON.stringify(session));
   pending=null;busy=false;if(message.state)render(message.state);return;
  }
  if(message.type==='state'){
   if(!state||message.state.version>=state.version)render(message.state);
   if(awaitingResume){awaitingResume=false;if(pending?.requestId){send(pending);scheduleRetry()}return}
   if(pending?.requestId && message.requestId===pending.requestId){clearTimeout(commandTimer);busy=false;pending=null}
  }
 };
 socket.onclose=()=>{
  clearInterval(heartbeat);$('signal').textContent='LINK INTERRUPTED';
  if(state)$('message').textContent='> Reconnecting to simulation…';
  if(!session&&pending?.action!=='create'&&pending?.action!=='join')pending=null;
  // Resend an unacknowledged mutation with its original ID after resume.
  clearTimeout(commandTimer);awaitingResume=false;
  if(!session)busy=false;
  clearTimeout(reconnectTimer);reconnectTimer=setTimeout(openSocket,Math.min(15000,600*2**Math.min(retry++,5)));
 };
 socket.onerror=()=>{};
}
function createOrJoin(action){if(busy)return;busy=true;pending={action,name:$('name').value,code:$('code').value,...(action==='create'?{gameType:selectedGame,mode:selectedMode}:{})};if(!send(pending))openSocket()}
function scheduleRetry(){clearTimeout(commandTimer);commandTimer=setTimeout(()=>{if(pending?.requestId&&socket?.readyState===WebSocket.OPEN){send(pending);scheduleRetry()}},8000)}
function act(action,extra={}){if(busy||!session||socket?.readyState!==WebSocket.OPEN)return;
 busy=true;pending={action,...extra,requestId:crypto.randomUUID()};send(pending);scheduleRetry();
}
function render(next){state=next;$('selection').hidden=true;$('mode-selection').hidden=true;const ttt=(state.gameType||'maze')==='tictactoe';$('map').hidden=ttt;$('ttt-board').hidden=!ttt;$('controls').hidden=ttt;$('relays').hidden=ttt;$('saved-session').hidden=true;$('entry').hidden=true;$('game').hidden=false;$('roomcode').textContent=state.code;$('phase').textContent=state.phase.toUpperCase();$('elapsed').textContent=`${String(Math.floor(state.elapsed/60)).padStart(2,'0')}:${String(state.elapsed%60).padStart(2,'0')}`;$('commands').textContent=String(state.commands).padStart(3,'0');$('signal').textContent='SIGNAL NOMINAL';$('message').textContent='> '+state.message;const owner=state.you;
 $('people').replaceChildren(...state.players.map((p,i)=>{const div=document.createElement('div');div.className='person';const left=document.createElement('div');const name=document.createElement('strong');name.textContent=p.name;const small=document.createElement('small');small.textContent=ttt?`PLAYER ${i+1} / ${p.mark}`:`OPERATOR 0${i+1} / FACING ${p.facing}`;left.append(name,small);const badge=document.createElement('div');badge.className='badge';badge.textContent=ttt&&state.mode==='computer'&&i===1?'COMPUTER':p.delay>0?'DELAY '+Math.ceil(p.delay)+'s':i===owner?'YOU':'LINKED';div.append(left,badge);return div}));
 if(!ttt)for(let i=0;i<2;i++){const landmark=state.landmarks.find(item=>item.kind==='relay'&&item.owner===i);const el=$('relay'+i);el.textContent=`RELAY 0${i+1} / ${state.activated[i]?'ACTIVE':landmark?'LOCATED':'UNLOCATED'}`;el.classList.toggle('active',state.activated[i])}
 $('start').hidden=!(state.phase==='lobby'&&owner===0&&state.players.length===2);$('replay').hidden=!(['won','draw'].includes(state.phase)&&owner===0);$('controls').querySelectorAll('button').forEach(b=>b.disabled=state.phase!=='playing'||state.players[owner].delay>0);$('replay').textContent=ttt?'NEW MATCH ↗':'GENERATE NEW MAZE ↗';$('hint').textContent=ttt?(state.mode==='computer'?'YOU: X · M.U.S.A.: O · SELECT AN EMPTY SQUARE':'PLAYER 1: X · PLAYER 2: O · SELECT AN EMPTY SQUARE ON YOUR TURN'):'KEYBOARD: A / ↑ or W / D · TURNS AND STEPS ARE SEPARATE COMMANDS';$('legend').textContent=ttt?'THREE IN A ROW · ROW / COLUMN / DIAGONAL':'◈ YOU · ◇ PARTNER · ◆ RELAY · ⊞ EXTRACTION · ! INTERFERENCE';if(ttt){$('coverage').textContent=state.phase==='playing'?`TURN: PLAYER ${state.turn+1}`:state.phase.toUpperCase();$('ttt-board').querySelectorAll('button').forEach((b,i)=>{b.textContent=state.board[i]||'';b.disabled=state.phase!=='playing'||state.turn!==owner||state.board[i]!==null;b.classList.toggle('winning',state.winningLine.includes(i));b.setAttribute('aria-label',`Square ${i+1}: ${state.board[i]||'empty'}`)});return}$('coverage').textContent=`DISCOVERY ${Math.round(state.cells.length/(state.size*state.size)*100)}%`;draw()}
function draw(){if(!state)return;const w=canvas.width,n=state.size,pad=28,step=(w-pad*2)/n;ctx.fillStyle='#030b06';ctx.fillRect(0,0,w,w);ctx.strokeStyle='#14301d';ctx.lineWidth=1;for(let i=0;i<=n;i++){let c=pad+i*step;ctx.beginPath();ctx.moveTo(c,pad);ctx.lineTo(c,w-pad);ctx.moveTo(pad,c);ctx.lineTo(w-pad,c);ctx.stroke()}
 const cellMap=new Map(state.cells.map(([x,y,type])=>[`${x},${y}`,type]));for(const [x,y,type] of state.cells){const px=pad+x*step,py=pad+y*step;ctx.fillStyle=type==='wall'?'#173d22':'#0b2011';ctx.fillRect(px+2,py+2,step-4,step-4);if(type==='floor'){ctx.strokeStyle='#528e59';ctx.strokeRect(px+4,py+4,step-8,step-8);for(const [dx,dy] of [[1,0],[0,1]])if(cellMap.get(`${x+dx},${y+dy}`)==='floor'){ctx.fillStyle='#0b2011';ctx.fillRect(px+dx*step+4,py+dy*step+4,step-8,step-8);ctx.strokeStyle='#528e59';ctx.beginPath();if(dx){ctx.moveTo(px+step-4,py+4);ctx.lineTo(px+step+4,py+4);ctx.moveTo(px+step-4,py+step-4);ctx.lineTo(px+step+4,py+step-4)}else{ctx.moveTo(px+4,py+step-4);ctx.lineTo(px+4,py+step+4);ctx.moveTo(px+step-4,py+step-4);ctx.lineTo(px+step-4,py+step+4)}ctx.stroke()}}}
 const cx=x=>pad+(x+.5)*step,cy=y=>pad+(y+.5)*step;ctx.textAlign='center';ctx.textBaseline='middle';ctx.font='bold 22px Courier New';for(const item of state.landmarks){ctx.fillStyle=item.kind==='hazard'?'#c3b985':item.active?'#70b87a':'#d3ffd8';ctx.fillText(item.kind==='hazard'?'!':item.kind==='exit'?'⊞':`◆`,cx(item.x),cy(item.y));if(item.kind==='relay'){ctx.font='12px Courier New';ctx.fillText(String(item.owner+1),cx(item.x)+11,cy(item.y)+11);ctx.font='bold 22px Courier New'}}state.players.forEach((p,i)=>{if(!cellMap.has(`${p.x},${p.y}`))return;ctx.fillStyle=i===state.you?'#e1ffe6':'#92cda0';ctx.beginPath();ctx.arc(cx(p.x),cy(p.y),step*.31,0,Math.PI*2);ctx.fill();ctx.fillStyle='#07170b';ctx.font='bold 14px Courier New';ctx.fillText(p.facing==='N'?'▲':p.facing==='E'?'▶':p.facing==='S'?'▼':'◀',cx(p.x),cy(p.y)+1)})}

$('resume').onclick=()=>{if(!session)return;resumeSelected=true;$('resume').disabled=true;if(!send({action:'resume',...session}))openSocket();else awaitingResume=true};
$('new-session').onclick=()=>{session=null;state=null;resumeSelected=false;awaitingResume=false;pending=null;busy=false;localStorage.removeItem('musa-session');$('saved-session').hidden=true;$('entry').hidden=false;$('selection').hidden=false;clearInterval(heartbeat);clearTimeout(reconnectTimer);if(socket){socket.onclose=null;socket.close();socket=null}openSocket()};
$('create').onclick=()=>createOrJoin('create');$('join').onclick=()=>createOrJoin('join');
$('start').onclick=()=>act('start');$('replay').onclick=()=>act('replay');
$('copy').onclick=async()=>{try{await navigator.clipboard.writeText(state.code);alertUser('Room code copied.')}catch{alertUser('Room code: '+state.code)}};
$('controls').onclick=e=>{const button=e.target.closest('button[data-action]');if(button&&!button.disabled)act('command',{command:button.dataset.action})};
window.addEventListener('keydown',e=>{if(!state||(state.gameType||'maze')!=='maze'||state.phase!=='playing'||document.activeElement.tagName==='INPUT')return;
 const command={ArrowLeft:'LEFT',a:'LEFT',A:'LEFT',ArrowRight:'RIGHT',d:'RIGHT',D:'RIGHT',ArrowUp:'FORWARD',w:'FORWARD',W:'FORWARD'}[e.key];
 if(command){e.preventDefault();act('command',{command})}
});
openSocket();

function selectSimulation(type){selectedGame=type;selectedMode='network';$('mode-selection').hidden=type!=='tictactoe';$('entry').hidden=type==='tictactoe';$('join-entry').hidden=false;$('create').textContent='CREATE NEW ROOM ↗';$('select-maze').classList.toggle('primary',type==='maze');$('select-ttt').classList.toggle('primary',type==='tictactoe');$('select-maze').setAttribute('aria-pressed',String(type==='maze'));$('select-ttt').setAttribute('aria-pressed',String(type==='tictactoe'));}
$('select-maze').onclick=()=>selectSimulation('maze');$('select-ttt').onclick=()=>selectSimulation('tictactoe');
$('ttt-board').onclick=e=>{const b=e.target.closest('button[data-square]');if(b&&!b.disabled)act('command',{ command:Number(b.dataset.square)})};

function selectMode(mode){selectedMode=mode;$('mode-selection').hidden=true;$('entry').hidden=false;$('join-entry').hidden=mode==='computer';$('create').textContent=mode==='computer'?'START VS M.U.S.A. ↗':'CREATE NEW ROOM ↗';}
$('mode-computer').onclick=()=>selectMode('computer');$('mode-network').onclick=()=>selectMode('network');
