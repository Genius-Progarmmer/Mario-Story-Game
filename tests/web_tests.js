// Headless tests for web.html: runs the REAL game script with a fake DOM / canvas / localStorage.
//   node tests/web_tests.js web.html
const { runInGame } = require('./web_env.js');
const htmlPath = process.argv[2] || 'web.html';

const tests = String.raw`
;(function(){
const results=[];
const T=(name,cond,extra)=>{results.push([name,!!cond]);console.log((cond?'PASS ':'FAIL ')+name+(!cond&&extra!==undefined?'  ['+extra+']':''));};
const keyDown=(code,o={})=>docHandlers.keydown({code,repeat:!!o.repeat,preventDefault(){}});
const keyUp=(code)=>docHandlers.keyup({code,preventDefault(){}});
const key=(code)=>{keyDown(code);keyUp(code);};          // one complete key press: down, then up
const ptr=(id,type,o={})=>{const h=els[id]&&els[id].handlers[type]; if(h)h({preventDefault(){},pointerId:o.id===undefined?1:o.id,clientX:o.x||0,clientY:o.y||0});};
const touch=(id,type='pointerdown')=>ptr(id,type);
const realSave=(lv,i=0)=>checkpointSpots(lv)[i];
const put=o=>localStorage.setItem(SAVE_KEY,JSON.stringify(o));
const frames=n=>{for(let i=0;i<n;i++)update();};

try{
// ---- 16. lives ----
T('16 lives: a new Player has 3 lives (same as Python)', new Player(0,0).lives===3);
newGame(); T('16 lives: New Game starts with 3 lives', mario.lives===3 && (lg()||{}).lives===3);

// ---- 2. Continue only for a healthy save ----
const good={lv:7,lives:2,cp:realSave(7),um:7,pw:null,pt:0};
T('2 validate: a healthy save is accepted', !!validateSave(good));
T('2 validate: an old save without power fields is accepted', !!validateSave({lv:3,lives:1,cp:null,um:3}));
const bad=[['level 0',{...good,lv:0}],['level 51',{...good,lv:51}],['level 7.5',{...good,lv:7.5}],['level as text',{...good,lv:'7'}],
  ['level true',{...good,lv:true}],['lives 0',{...good,lives:0}],['lives 4 (more than the maximum)',{...good,lives:4}],['lives 1.5',{...good,lives:1.5}],
  ['lives null',{...good,lives:null}],['checkpoint 4600 (not one of the level)',{...good,cp:4600}],['checkpoint of ANOTHER level',{...good,cp:realSave(7)+1}],
  ['checkpoint as text',{...good,cp:String(good.cp)}],['unknown power',{...good,pw:'laser',pt:50}],['power time too big',{...good,pw:'fly',pt:POWER_DUR+1}],
  ['negative power time',{...good,pw:'fly',pt:-3}],['an array',[1,2]],['null',null],['a number',5]];
for(const [n,d] of bad) T('2 validate: rejects '+n, validateSave(d)===null);
localStorage.setItem(SAVE_KEY,'{broken'); T('2 corrupt JSON: no Continue', !hs()&&lg()===null);
showMenu(); T('2 menu: the Continue button is hidden for a corrupt save', els.btnCont.style.display==='none');
put({...good,lives:99}); showMenu(); T('2 menu: hidden for invalid lives', els.btnCont.style.display==='none');
put(good); showMenu(); T('2 menu: shown for a healthy save', els.btnCont.style.display==='block');
put({...good,lives:0}); STATE='menu'; els.btnCont.handlers.click(); T('2 clicking Continue on a save that went bad does not start a game', STATE!=='playing');

// ---- 1. New Game replaces the old save ----
put({lv:7,lives:2,cp:realSave(7),um:7,pw:null,pt:0});
newGame();
let d=lg(); T('1 new game: the save is replaced at once (level 1, 3 lives, no checkpoint, furthest 1)', d&&d.lv===1&&d.lives===3&&d.cp===null&&d.um===1&&d.pw===null, JSON.stringify(d));
mario.lives=1; loseLife(); T('1 new game: losing right away -> game over', STATE==='falling_text');
d=lg(); T('1 new game: Continue after that still offers the NEW game (level 1), not the old level 7', d&&d.lv===1);
contGame(d); T('1 new game: Continue starts level 1', curLv===1&&STATE==='playing');
const realSet=localStorage.setItem; put({lv:7,lives:2,cp:null,um:7,pw:null,pt:0});
localStorage.setItem=()=>{throw new Error('full');};      // the browser refuses to write (quota / private mode)
newGame(); localStorage.setItem=realSet;
T('1 new game: if the save cannot be written, the old one is deleted', !hs());

// ---- 3. level 51 ----
put({lv:49,lives:3,cp:null,um:49,pw:null,pt:0}); contGame(lg());
nextLv(); frames(0);
d=lg(); T('3 level 49 -> 50 is saved as level 50 with a full set of lives', curLv===50&&d&&d.lv===50&&d.lives===3&&d.cp===null, JSON.stringify(d));
const before=localStorage.getItem(SAVE_KEY);
curLv=50; nextLv();
T('3 after level 50 the counter stays at 50 (no level 51)', curLv===50);
T('3 after level 50 nothing new is saved', localStorage.getItem(SAVE_KEY)===before);
T('3 after level 50 the ending plays', STATE==='cutscene'&&cs&&cs.id==='final');
T('3 the save never becomes invalid after the ending', hs());
cs.after&&cs.after(); T('3 ending -> menu', STATE==='menu');

// ---- 4. thin walls ----
function ent(x,y,vx,vy){return{rect:{x,y,w:32,h:38},vx,vy,_rx:0,_ry:0,dashing:true};}
let e=ent(100,300,12,0); let r=moveWithCollision(e,[{x:150,y:290,w:4,h:60}],{stopDashOnWall:true});
for(let i=0;i<5&&!r.hitWallR;i++)r=moveWithCollision(e,[{x:150,y:290,w:4,h:60}],{stopDashOnWall:true});
T('4 a 4px wall stops a 12px/frame dash (does not skip over it)', r.hitWallR&&e.rect.x+e.rect.w===150&&e.vx===0&&!e.dashing, 'x='+e.rect.x);
e=ent(300,300,-12,0); const wL=[{x:250,y:290,w:4,h:60}]; r={};
for(let i=0;i<8&&!r.hitWallL;i++)r=moveWithCollision(e,wL,{});
T('4 same going left', r.hitWallL&&e.rect.x===254, 'x='+e.rect.x);
e=ent(100,300,200,0); r=moveWithCollision(e,[{x:150,y:290,w:1,h:60}],{});
T('4 even a 200px jump over a 1px wall is stopped', r.hitWallR&&e.rect.x===118, 'x='+e.rect.x);

// ---- 5. sub-pixel vertical movement ----
e=ent(100,100,0,0.5); r=moveWithCollision(e,[],{});
T('5 vy=0.5: no forced 1px step', e.rect.y===100&&Math.abs(e._ry-0.5)<1e-9, 'y='+e.rect.y+' ry='+e._ry);
r=moveWithCollision(e,[],{}); T('5 ...the two halves add up to one pixel', e.rect.y===101&&Math.abs(e._ry)<1e-9, 'y='+e.rect.y);
e=ent(100,100,0,-0.5); moveWithCollision(e,[],{}); T('5 vy=-0.5 does not move up', e.rect.y===100);
const floor=[{x:0,y:550,w:4800,h:50}];
e=ent(100,512,0,0.3); r=moveWithCollision(e,floor,{});
T('5 standing on the ground with a tiny vy is still "on ground"', r.onGround&&e.vy===0&&e.rect.y===512);
e=ent(100,300,0,-3); r=moveWithCollision(e,floor,{}); T('5 rising is not "on ground"', !r.onGround);
e=ent(100,500,0,0); r=moveWithCollision(e,floor,{}); T('5 1px above... is not on ground when 12px up', !r.onGround);
T('5 Mario really stands on the ground in a real level and can jump', (()=>{newGame();mario.jl=1;frames(5);const ok=mario.onGround&&mario.rect.y+mario.rect.h===GY&&mario.jl===2;mario.jump();return ok&&mario.vy<0;})());

// ---- 6 + 12. boss: player's hit first; stomp and punch both hurt ----
function bossSetup(hp){loadLv(10);mario.lives=3;const b=level.boss;b.hp=hp;b.maxHp=Math.max(hp,2);b.hurt=0;return b;}
function onBoss(b){mario.rect.x=b.rect.x+30;mario.rect.y=b.rect.y+30;mario.vy=0;mario.vx=0;mario.inv=0;mario.facing=1;}
let b=bossSetup(1); onBoss(b); mario.bossHits=BOSS_HIT_LIMIT-1; mario.punching=true;mario.punchT=10;mario.punchRect={x:0,y:0,w:40,h:24};
update();
T('6 last punch kills the boss', !b.alive);
T('6 ...and the boss body does NOT cost the last heart / a life the same frame', mario.lives===3&&mario.bossHits===BOSS_HIT_LIMIT-1&&STATE==='playing', 'lives='+mario.lives+' hits='+mario.bossHits+' state='+STATE);
b=bossSetup(1); onBoss(b); mario.rect.y=b.rect.y-32; mario.vy=8; mario.bossHits=BOSS_HIT_LIMIT-1;
update();
T('6 last STOMP kills the boss', !b.alive, 'hp='+b.hp);
T('6 ...and Mario is safe', mario.lives===3&&mario.bossHits===BOSS_HIT_LIMIT-1);
b=bossSetup(1); onBoss(b); b.punchRect={x:mario.rect.x,y:mario.rect.y,w:30,h:30}; mario.bossHits=BOSS_HIT_LIMIT-1;
mario.punchRect={x:b.rect.x,y:b.rect.y,w:50,h:50}; mario.punching=true;mario.punchT=10;
update(); T('6 a boss killed by Mario cannot land its own punch in the same frame', !b.alive&&mario.lives===3);
b=bossSetup(5); onBoss(b); mario.bossHits=BOSS_HIT_LIMIT-1; update();
T('6 sanity: a side touch on a living boss still hurts', mario.lives===2||mario.bossHits===0&&STATE==='falling_text'||mario.lives<3, 'lives='+mario.lives);
b=bossSetup(5); onBoss(b); mario.rect.y=b.rect.y-32; mario.vy=8; update();
T('12 stomping the boss hurts it by 1 HP', b.hp===4&&mario.bossHits===0, 'hp='+b.hp);
T('12 ...and bounces Mario up', mario.vy<0);
const hp1=b.hp; onBoss(b); mario.rect.y=b.rect.y-32; mario.vy=8; update();
T('12 a second stomp during the boss hurt-flash does not double count', b.hp===hp1, 'hp='+b.hp);
b=bossSetup(5); onBoss(b); mario.punching=true;mario.punchT=10;mario.punchRect={x:0,y:0,w:40,h:24}; mario.inv=999; update();
T('12 punching the boss hurts it by 1 HP', b.hp===4, 'hp='+b.hp);
T('12 boss text: sidebar names the same number of hits as the code', els.sbBossHits.textContent.startsWith(BOSS_HIT_LIMIT+' hits'), els.sbBossHits.textContent);
T('12 boss text: no stale "5 hits" / "only punch" text left', !/5 hits/i.test(html)&&!/Only PUNCH/i.test(html)&&!/shells/i.test(html.slice(html.indexOf('BOSS FIGHT'),html.indexOf('BOSS FIGHT')+400)));

// ---- 7. goal flag ----
let flagCalls=0; const origFlag=drawGoalFlag; drawGoalFlag=(...a)=>{flagCalls++;origFlag(...a);};
loadLv(1); curZoom=1; drawScene(level.goal.x-300,0);
T('7 normal level: the end-of-level flag is drawn near the goal', flagCalls===1);
flagCalls=0; drawScene(0,0); T('7 ...and not when the goal is off screen', flagCalls===0);
flagCalls=0; loadLv(10); curZoom=1; drawScene(level.goal.x-300,0); T('7 boss level: no flag (the portal appears after the boss)', flagCalls===0);
loadLv(1); mario.rect.x=level.goal.x-mario.rect.w; mario.rect.y=GY-38; STATE='playing'; const lvBefore=curLv; update(); T('7 touching the pole (goal.x) ends a normal level', curLv===lvBefore+1||STATE==='falling_text'&&curLv===2, 'lv='+curLv);

let pipesAtGoal=0; for(let n=1;n<=50;n++){const L=buildLv(n,50);if(L.pipes.some(p=>p.lip.x+p.lip.w>L.goal.x-100))pipesAtGoal++;}
T('7 no level has a pipe covering the flag or blocking the way to it', pipesAtGoal===0, pipesAtGoal);

// ---- 8. enemies on platforms ----
let onPlat=0,total=0,inside=0,notStanding=0;
for(let n=1;n<=50;n++){const L=buildLv(n,50);for(const en of L.enemies){total++;if(en.rect.y+en.rect.h<GY-20){onPlat++;
  const p=L.platforms.find(p=>p.h!==50&&en.rect.x+en.rect.w>p.x&&en.rect.x<p.x+p.w&&en.rect.y+en.rect.h===p.y); if(!p)notStanding++;}
  if(L.solids.some(s=>ov(en.rect,s)))inside++;}}
T('8 enemies now stand on floating platforms ('+onPlat+' of '+total+' over 50 levels)', onPlat>20, onPlat);
T('8 every platform enemy stands exactly on its platform', notStanding===0, notStanding);
T('8 no enemy starts inside a wall, pipe or block', inside===0, inside);
T('8 levels are still built the same way twice', JSON.stringify(buildLv(5,50).platforms)===JSON.stringify(buildLv(5,50).platforms)&&buildLv(5,50).enemies.length===buildLv(5,50).enemies.length);
// they stay on the platform
loadLv(1); const pe=(()=>{for(let n=1;n<=50;n++){const L=buildLv(n,50);const en=L.enemies.find(en=>en.rect.y+en.rect.h<GY-20);if(en)return n;}})();
loadLv(pe); const penemy=level.enemies.find(en=>en.rect.y+en.rect.h<GY-20); const startY=penemy.rect.y; mario.rect.x=4000; mario.rect.y=GY-38;
for(let i=0;i<600;i++){penemy.upd(level.solids,level.solids);}
T('8 a platform enemy patrols without falling off', penemy.rect.y===startY, penemy.rect.y+' vs '+startY);

// ---- 9. power is saved and restored ----
newGame(); mario.power='crush'; mario.powerT=100; const cp0=level.cps[0];
mario.rect.x=cp0.wx-10; update(); d=lg();
T('9 touching a checkpoint saves the power and its time', d&&d.pw==='crush'&&d.pt>=98&&d.pt<=100&&d.cp===cp0.wx, JSON.stringify(d));
contGame(d); T('9 Continue brings the power and the time back', mario.power==='crush'&&mario.powerT===d.pt);
mario.power='jump'; mario.powerT=77; STATE='paused'; key('KeyQ'); d=lg();
T('9 Pause + Q saves the power too', d&&d.pw==='jump'&&d.pt===77&&STATE==='falling_text', JSON.stringify(d));
put({lv:1,lives:3,cp:null,um:1,pw:'fly',pt:0}); T('9 an expired power (time 0) is loaded as no power', lg().pw===null&&lg().pt===0);
mario=null; newGame(); mario.power='fly';mario.powerT=50; mario.rect.x=level.cps[0].wx-10; update(); nextLv && (curLv=1, 0);
sg(2,START_LIVES,null,2,null,0); T('9 a new level is saved without a power', lg().pw===null&&lg().lives===3);

// ---- 10. Continue start position ----
for(const lvl of [1,12,25,40,50]){
  const spots=checkpointSpots(lvl);
  for(const cpx of spots){
    put({lv:lvl,lives:3,cp:cpx,um:lvl,pw:null,pt:0}); contGame(lg());
    const g0=GY, m=mario.rect;
    const okM = m.y+m.h===g0 && m.x===cpx && !blockedAt(m);
    let okC=true,det='';
    for(const c of companions){ const near=c.rect.x>=cpx-c.offset-1&&c.rect.x<=cpx+1; if(!(c.rect.y+c.rect.h===g0&&near&&!blockedAt(c.rect))){okC=false;det+=c.type+'@'+c.rect.x+' ';} }
    T('10 level '+lvl+' checkpoint '+cpx+': Mario stands on the ground at the checkpoint', okM, JSON.stringify(m));
    T('10 level '+lvl+' checkpoint '+cpx+': '+companions.length+' companion(s) wait close behind him, none stuck', okC&&(lvl<12?companions.length===0:companions.length>=2), det);
    frames(45); T('10 level '+lvl+' cp '+cpx+': after 45 frames Mario is still on the ground', mario.onGround&&mario.rect.y+mario.rect.h===g0&&mario.lives===3&&STATE==='playing', 'state='+STATE+' y='+mario.rect.y);
  }
}
loadLv(1); T('10 fresh level: Mario starts at x=50 on the ground', mario.rect.x===50&&mario.rect.y+mario.rect.h===GY);
put({lv:25,lives:3,cp:null,um:25,pw:null,pt:0}); contGame(lg());
T('10 Continue without a checkpoint starts at the level start', mario.rect.x===50&&companions.length===3);

// ---- respawn (HTML twin of Python item 13) ----
newGame(); mario.jl=0; mario.jheld=true; mario.onGround=false; mario.vy=-9; mario.dashing=true; mario.punchT=9; mario.punching=true; mario.rect.y=100;
respawn(); T('respawn: jump state reset, standing on the ground', mario.jl===2&&!mario.jheld&&mario.onGround&&!mario.dashing&&mario.vy===0&&mario.rect.y+mario.rect.h===GY&&!mario.punching);
mario.jump(); T('respawn: Mario can jump on the very first frame', mario.vy<0&&mario.jl===1);
newGame(); mario.lives=3; loseLife(); T('respawn: message shows the lives left', flash&&flash.t==='♥ 2 left', flash&&flash.t);

// ---- 11. touch controls and the pause button ----
newGame(); frames(3); STATE='paused'; mario.jl=2; mario.punching=false; mario.dashCd=0; mario.dashing=false; mario.vy=0;
touch('mcJ'); touch('mcZ'); touch('mcD'); ptr('mcStick','pointerdown',{x:140,y:75}); ptr('mcStick','pointerup'); ptr('mcStick','pointerdown',{x:10,y:75}); touch('mcT');
T('11 while PAUSED the touch buttons do nothing (no jump, punch, dash, switch)', mario.jl===2&&mario.vy===0&&!mario.punching&&!mario.dashing&&mario.activeChar==='mario');
ptr('mcStick','pointerup'); touch('mcJ','pointerup'); touch('mcZ','pointerup'); touch('mcD','pointerup'); touch('mcT','pointerup');
STATE='cutscene'; touch('mcJ'); touch('mcZ'); T('11 in a cutscene they do nothing either', mario.jl===2&&!mario.punching);
STATE='playing'; mario.vx=0; touch('mcJ'); T('11 while PLAYING the jump button works', mario.vy<0&&mario.jl===1);
touch('mcZ'); T('11 ...the punch button works', mario.punching);
mario.dashCd=0; touch('mcD'); T('11 ...the dash button works (it called a missing method before)', mario.dashing);
touch('mcP'); T('11 the pause button pauses', STATE==='paused');
window.syncPauseBox(); T('11 ...and shows the RESUME / SAVE & QUIT buttons', els.pausebox.style.display==='flex');
els.btnSaveQuit.handlers.click({currentTarget:els.btnSaveQuit}); T('11 SAVE & QUIT saves and goes to the menu', STATE==='falling_text'&&hs());
newGame(); STATE='paused'; els.btnResume.handlers.click({currentTarget:els.btnResume}); T('11 RESUME continues the game', STATE==='playing');
window.syncPauseBox(); T('11 ...and hides the buttons', els.pausebox.style.display==='none');
STATE='playing'; touch('mcP'); touch('mcP'); T('11 the pause button toggles back', STATE==='playing');
pipeDying=true; touch('mcP'); T('11 cannot pause while sinking into a pipe', STATE==='playing'); pipeDying=false;
STATE='menu'; touch('mcP'); T('11 the pause button does nothing in the menu', STATE==='menu');
STATE='playing'; key('Escape'); T('11 Esc still pauses', STATE==='paused'); key('Enter'); T('11 Enter still resumes', STATE==='playing');


// ---- joystick, buttons, fullscreen, rotate (phone layout) ----
newGame(); frames(3); STATE='playing'; keys.ArrowLeft=keys.ArrowRight=keys.Space=false;
ptr('mcStick','pointerdown',{x:140,y:75});               // push right
T('stick: pushing right sets ArrowRight only', keys.ArrowRight===true&&!keys.ArrowLeft);
const x0=mario.rect.x; frames(10); T('stick: Mario walks right', mario.rect.x>x0+30, mario.rect.x-x0);
ptr('mcStick','pointermove',{x:5,y:75});                 // slide to the left
T('stick: sliding to the left switches direction', keys.ArrowLeft===true&&!keys.ArrowRight);
const x1=mario.rect.x; frames(10); T('stick: Mario walks left', mario.rect.x<x1-30);
ptr('mcStick','pointermove',{x:80,y:75});                // back to the middle (dead zone)
T('stick: the middle is a dead zone (nothing pressed)', !keys.ArrowLeft&&!keys.ArrowRight);
ptr('mcStick','pointermove',{x:120,y:75}); T('stick: a small push right already counts', keys.ArrowRight===true);
ptr('mcStick','pointerup'); T('stick: letting go stops Mario', !keys.ArrowLeft&&!keys.ArrowRight&&els.stickKnob.style.transform==='translate(0px,0px)');
frames(15); T('stick: ...and he really stands still', Math.abs(mario.vx)<0.01, mario.vx);
ptr('mcStick','pointerdown',{x:140,y:75,id:7}); ptr('mcStick','pointerdown',{x:5,y:75,id:8});
T('stick: a second finger on the stick is ignored', keys.ArrowRight===true&&!keys.ArrowLeft);
ptr('mcStick','pointermove',{x:5,y:75,id:8}); T('stick: ...also when it moves', keys.ArrowRight===true);
ptr('mcStick','pointerup',{id:8}); T('stick: ...and when it lifts', keys.ArrowRight===true);
// two fingers: stick held with one, jump with the other
ptr('mcJ','pointerdown',{id:9}); T('multi-touch: jump works while the stick is held', mario.vy<0&&keys.ArrowRight===true&&keys.Space===true);
ptr('mcZ','pointerdown',{id:10}); T('multi-touch: ...and punch too', mario.punching===true);
ptr('mcJ','pointerup',{id:9}); T('multi-touch: jump button released: Space and jump-hold are released', keys.Space===false&&mario.jheld===false&&keys.ArrowRight===true);
ptr('mcStick','pointerup',{id:7}); T('multi-touch: stick released at last', !keys.ArrowRight);
ptr('mcJ','pointercancel',{id:1}); ptr('mcJ','pointerup',{id:99});   // stray events must not break anything
T('stick: pointermove of a stranger does nothing', (ptr('mcStick','pointermove',{x:140,y:75,id:55}),!keys.ArrowRight));
// dash with a double flick
newGame(); frames(3); mario.dashCd=0; ptr('mcStick','pointerdown',{x:140,y:75}); ptr('mcStick','pointerup'); ptr('mcStick','pointerdown',{x:140,y:75});
T('stick: pushing the same way twice quickly dashes', mario.dashing===true); ptr('mcStick','pointerup');
// flying: hold jump to rise, pull the stick down to sink
newGame(); frames(3); mario.power='fly'; mario.powerT=180; ptr('mcJ','pointerdown'); frames(5);
T('fly: holding the jump button lifts Mario', mario.vy<0||mario.rect.y<GY-38-5, mario.vy); ptr('mcJ','pointerup');
ptr('mcStick','pointerdown',{x:75,y:140}); T('fly: pulling the stick down sets ArrowDown', keys.ArrowDown===true); ptr('mcStick','pointerup'); T('fly: ...and it is released', !keys.ArrowDown);
// the controls are only visible in play / pause
STATE='playing'; window.syncPauseBox(); T('ui: controls visible while playing', els.touchui.style.visibility==='visible');
STATE='paused';  window.syncPauseBox(); T('ui: controls visible while paused (pause button must work)', els.touchui.style.visibility==='visible');
STATE='menu';    window.syncPauseBox(); T('ui: controls hidden in the menu', els.touchui.style.visibility==='hidden');
STATE='cutscene'; window.syncPauseBox(); T('ui: controls hidden in a cutscene', els.touchui.style.visibility==='hidden');
// tap the screen to skip a cutscene
let skipped=false; playCS('ch1_end',()=>{skipped=true;}); els.c.handlers.pointerdown({});
T('cutscene: a tap on the screen skips it', skipped&&cs===null);
STATE='playing'; els.c.handlers.pointerdown({}); T('cutscene: a tap during play does nothing', STATE==='playing');
// HTML / CSS structure for phones
T('html: viewport blocks zoom and uses the full screen (notch)', /user-scalable=no/.test(html)&&/viewport-fit=cover/.test(html));
T('html: rotate message exists and only shows on a portrait TOUCH screen', /id="rotate"/.test(html)&&/@media\(orientation:portrait\)\{html\.touch #rotate\{display:flex/.test(html));
T('html: side panels are hidden on phones (html.touch) so the game gets the whole screen', /html\.touch \.sidebar\{display:none\}/.test(html)&&/html\.touch #shell\{display:flex/.test(html));
T('html: the "touch" class is decided by the script, and NOT by hover:none (desktops without a mouse report it)', /classList\.toggle\('touch'/.test(html)&&!/mq\('\(hover:none\)'\)/.test(html));
T('html: the controls are shown by a rule that beats #touchui{display:none} (this bug hid every button on phones)', (()=>{
  const base=html.indexOf('#touchui{display:none'), show=html.indexOf('html.touch #touchui{display:block}');
  return base>=0&&show>base;   // later in the file AND more specific
})());
T('html: jump button is bottom-right, joystick bottom-left, punch above jump', /#mcStick\{left:[^}]*bottom:/.test(html)&&/#mcJ\{right:[^}]*bottom:calc\(var\(--sb\) \+ var\(--b\)\)/.test(html)&&/#mcZ\{right:[^}]*bottom:calc\(var\(--sb\) \+ var\(--b\) \+ var\(--j\)/.test(html));
T('html: the old left/right arrow buttons are gone', !/id="mcL"|id="mcR"/.test(html));
// fullscreen: with and without the browser API
const de=document.documentElement; let fsCalls=0; de.requestFullscreen=()=>{fsCalls++;return Promise.resolve();};
els.fsbtn.handlers.click({currentTarget:els.fsbtn}); T('fullscreen: the button asks the browser for full screen', fsCalls===1);
delete de.requestFullscreen; delete de.webkitRequestFullscreen; els.fsbtn.handlers.click({currentTarget:els.fsbtn});
T('fullscreen: on an iPhone (no API) a hint about "Add to Home Screen" is shown', els.toast.style.display==='block'&&/Home Screen/.test(els.toast.textContent));


// ---- Dash of the real Player against a thin wall (item: Dash + thin wall) ----
{
  newGame(); frames(2);
  const world=[{x:0,y:550,w:4800,h:50},{x:300,y:400,w:4,h:150}];      // ground + a 4px wall
  mario.rect.x=240; mario.rect.y=512; mario.vx=0; mario.vy=0; mario.dashing=false; mario.dashCd=0; mario.inv=0;
  mario._dash(1);
  T('dash: starts at the dash speed (12 px/frame)', mario.dashing&&mario.vx===DASH_SPD);
  let hitFrames=0; for(let i=0;i<8;i++){mario.upd(world); if(mario.rect.x+mario.rect.w>304)hitFrames++;}
  T('dash: Mario never gets through a 4px wall', hitFrames===0&&mario.rect.x+mario.rect.w<=300, 'x='+mario.rect.x);
  T('dash: it stops right at the wall and the WALL (not the timer) ends the dash', mario.rect.x+mario.rect.w===300&&!mario.dashing&&mario.dashT>3, 'x='+mario.rect.x+' dashing='+mario.dashing+' dashT='+mario.dashT);
  // same dash without a wall travels far
  mario.rect.x=240; mario.vx=0; mario.dashing=false; mario.dashCd=0; mario._dash(1); const xs=mario.rect.x; for(let i=0;i<10;i++)mario.upd([world[0]]);
  T('dash: without a wall it really covers ground (control test)', mario.rect.x-xs>=100, mario.rect.x-xs);
  // to the left as well
  mario.rect.x=340; mario.vx=0; mario.dashing=false; mario.dashCd=0; mario._dash(-1); for(let i=0;i<4;i++)mario.upd(world);   // wall after ~3 frames, the 14-frame dash timer is still running
  T('dash: left dash stops at the wall...', mario.rect.x===304, 'x='+mario.rect.x);
  T('dash: ...and the wall (not the timer) ends the dash', !mario.dashing&&mario.dashT>5, 'dashing='+mario.dashing+' dashT='+mario.dashT);
  // double tap on the keyboard path
  newGame(); frames(2); mario.dashCd=0; mario.dashing=false; mario.tryDash(1); mario.upd(level.platforms); mario.tryDash(1);
  T('dash: double tap in the same direction starts a dash', mario.dashing===true);
  mario.dashing=false; mario.dashCd=20; mario.lRt=-99; mario.tryDash(-1); mario.tryDash(-1);
  T('dash: not while it is cooling down', mario.dashing===false);
}


// ---- "SPACE to skip" on LEVEL / GAME OVER screens must really skip ----
{
  newGame(); frames(2);
  trigFL('LEVEL  2','#ffd200',52,'playing','x'); T('skip: a falling-text screen is showing', STATE==='falling_text');
  key('Space'); T('skip: Space ends it and the game goes on', STATE==='playing'&&fa===null, STATE);
  trigFL('LEVEL  3','#ffd200',52,'playing','x'); key('Enter'); T('skip: Enter works too', STATE==='playing');
  trigFL('LEVEL  4','#ffd200',52,'playing','x'); els.c.handlers.pointerdown({}); T('skip: a tap on the screen works too (phone)', STATE==='playing');
  trigFL('GAME  OVER','#dc1e1e',52,'menu','Press ENTER'); key('Enter'); T('skip: GAME OVER + Enter goes to the menu', STATE==='menu'&&els.btnCont!==undefined);
  STATE='playing'; key('Space'); T('skip: Space during play does not skip anything (it jumps)', STATE==='playing');
  trigFL('LEVEL  5','#ffd200',52,'playing','x'); frames(300); T('skip: without a key the screen still ends by itself', STATE==='playing');
}
// ---- a platform right before / above a pipe must not make the jump over it impossible ----
{
  let blocking=0,levelsHit=0;
  for(let n=1;n<=50;n++){const L=buildLv(n,50);let hit=false;
    for(const pp of L.pipes)for(const pl of L.platforms){ if(pl.h>=50)continue; if(pl.x<pp.lip.x+pp.lip.w+PIPE_ZONE_R&&pl.x+pl.w>pp.lip.x-PIPE_ZONE_L){blocking++;hit=true;} }
    if(hit)levelsHit++;
    // and no enemy is left floating where a platform was removed
    for(const en of L.enemies){ if(en.rect.y+en.rect.h<GY-20 && !L.platforms.some(p=>p.h<50&&en.rect.y+en.rect.h===p.y&&en.rect.x+en.rect.w>p.x&&en.rect.x<p.x+p.w)){blocking++;} } }
  T('levels: no platform within 100px before / above a pipe, no enemy floating in the air (all 50 levels)', blocking===0, blocking+' problems in '+levelsHit+' levels');
  T('levels: removing platforms keeps most platforms (not a bulldozer)', (()=>{let c=0;for(let n=1;n<=50;n++)c+=buildLv(n,50).platforms.length-1;return c>=120;})());
}

// =====================================================================================================
// NEW CHECKS for the ten fixes (keyboard, new-game reset, game clock, crush, boss arena, heroes, menu, saving)
// =====================================================================================================
const baseState=()=>{keys.ArrowLeft=keys.ArrowRight=keys.Space=false;};

// ---- A. keyboard: a HELD key must not fire a command again ----
{
  newGame(); frames(3); baseState();
  mario.jl=2; keyDown('Space');
  T('A jump: the first press jumps', mario.jl===1&&mario.vy<0);
  for(let i=0;i<6;i++)keyDown('Space',{repeat:true});
  T('A jump: holding Space (browser auto-repeat) does NOT trigger the double jump', mario.jl===1, 'jl='+mario.jl);
  keyDown('Space');   // no keyup in between: the key is still down, so this is NOT a new press either
  T('A jump: a keydown without a keyup in between is not a new press', mario.jl===1, 'jl='+mario.jl);
  keyUp('Space'); keyDown('Space');
  T('A jump: releasing and pressing again DOES double jump', mario.jl===0);
  keyUp('Space');

  newGame(); frames(3); mario.dashCd=0; mario.dashing=false; mario.lRt=mario.lLt=-99;
  keyDown('ArrowRight'); frames(1); for(let i=0;i<8;i++){keyDown('ArrowRight',{repeat:true});frames(1);}
  T('A dash: holding the arrow key does NOT dash (auto-repeat looks like a double tap)', !mario.dashing);
  keyUp('ArrowRight'); keyDown('ArrowRight'); frames(1); keyUp('ArrowRight'); keyDown('ArrowRight');
  T('A dash: two real taps still dash', mario.dashing===true);
  keyUp('ArrowRight');
  newGame(); frames(3); mario.dashCd=0; mario.dashing=false; mario.lRt=mario.lLt=-99;
  keyDown('KeyD'); frames(1); keyDown('KeyD',{repeat:true});
  T('A dash: same for D', !mario.dashing); keyUp('KeyD');
  mario.dashCd=0; mario.lLt=-99; keyDown('KeyA'); frames(1); keyDown('KeyA',{repeat:true}); T('A dash: same for A / left', !mario.dashing); keyUp('KeyA');

  loadLv(25); STATE='playing'; mario.activeChar='mario'; baseState();
  keyDown('KeyT'); T('A switch hero: T switches once', mario.activeChar==='luigi', mario.activeChar);
  for(let i=0;i<5;i++)keyDown('KeyT',{repeat:true});
  T('A switch hero: holding T does NOT keep switching', mario.activeChar==='luigi', mario.activeChar);
  keyUp('KeyT'); keyDown('KeyT'); T('A switch hero: a new press switches again', mario.activeChar==='princess'); keyUp('KeyT');

  newGame(); frames(3); mario.punching=false; mario.punchT=0; keyDown('KeyZ'); T('A punch: Z punches', mario.punching);
  frames(30); T('A punch: the punch ends', !mario.punching); keyDown('KeyZ',{repeat:true}); T('A punch: holding Z does not punch again', !mario.punching); keyUp('KeyZ');

  newGame(); frames(2); keyDown('Escape'); T('A pause: Esc pauses', STATE==='paused');
  keyDown('Escape',{repeat:true}); T('A pause: holding Esc does not flicker back into the game', STATE==='paused'); keyUp('Escape');
  keyDown('Escape'); T('A pause: a new Esc press resumes', STATE==='playing'); keyUp('Escape');

  STATE='cutscene'; cs={id:'ch1_end',t:0,after:()=>{STATE='playing';}}; keyDown('Space',{repeat:true});
  T('A cutscene: a held key does not skip it', STATE==='cutscene'); cs=null; STATE='playing';
  keyDown('Space'); keyUp('Space');
  newGame(); frames(2); keyDown('ArrowRight'); T('A walking still follows a held key', keys.ArrowRight===true); keyDown('ArrowRight',{repeat:true}); frames(10);
  T('A walking: ...and Mario walks while it is held', mario.rect.x>50+20); keyUp('ArrowRight'); T('A walking: ...and stops when it is released', keys.ArrowRight===false);
}

// ---- B. a new game starts COMPLETELY clean ----
{
  newGame(); frames(3);
  flash={t:'OLD MESSAGE',d:99}; shake=9; keys.ArrowRight=true; keys.KeyZ=true; kbHeld.Space=true; cs={id:'ch1_end',t:5,after:null};
  fa=new FL('X','#fff',10); faSub='old'; faNext='playing'; faT=30; pipeDying=true; pauseMsg='old'; parts.push({x:0,y:0,vx:0,vy:0,col:'#fff',life:50,ml:50,sz:3}); hb=.7; curZoom=.5;
  ptr('mcStick','pointerdown',{id:5,x:140,y:75}); ptr('mcJ','pointerdown',{id:3});   // a finger on the stick and one on JUMP...
  T('B new game (setup): the finger on JUMP lights the button', els.mcJ.classList.contains('on'));
  newGame();                                                                            // ...and the new game starts while they are still down
  T('B new game: the old message is gone', flash===null, JSON.stringify(flash));
  T('B new game: screen shake is 0', shake===0);
  T('B new game: no key is still "held"', Object.values(keys).every(v=>!v)&&Object.values(kbHeld).every(v=>!v), JSON.stringify(keys));
  T('B new game: no old cutscene, falling text or pipe death', cs===null&&fa===null&&faSub===''&&faNext===null&&faT===0&&!pipeDying);
  T('B new game: no old particles, no old pause message, zoom back to 1', parts.length===0&&pauseMsg===''&&curZoom===1);
  T('B new game: Mario is not walking by himself', mario.vx===0);
  frames(10); T('B new game: ...and stays at the start after 10 frames', mario.rect.x===50, mario.rect.x);
  T('B new game: the JUMP button is no longer lit by the old finger', !els.mcJ.classList.contains('on'));
  ptr('mcStick','pointerdown',{id:6,x:140,y:75});     // a NEW finger on the stick (the old one, id 5, never lifted)
  T('B new game: the joystick answers a new finger straight away (the old finger was forgotten)', keys.ArrowRight===true);
  ptr('mcStick','pointerup',{id:6}); ptr('mcStick','pointerup',{id:5}); ptr('mcJ','pointerup',{id:3});
  // Continue starts clean too
  put({lv:7,lives:2,cp:null,um:7,pw:null,pt:0}); flash={t:'OLD',d:50}; shake=5; keys.ArrowLeft=true; contGame(lg());
  T('B continue: starts clean too (message, shake, keys)', flash===null&&shake===0&&!keys.ArrowLeft);
}

// ---- C. game clock: logic runs at 60 steps per REAL second, whatever the frame rate ----
{
  const stepsOver=(fps,seconds,jitter=0)=>{resetClock();let t=5000,sum=0;const first=clockSteps(t);const n=Math.round(fps*seconds);for(let i=0;i<n;i++){t+=1000/fps+(i%2?jitter:-jitter);sum+=clockSteps(t);}return sum;};
  for(const fps of [144,120,60,30,20,15,10]){const got=stepsOver(fps,10);T('C clock: at '+fps+' fps the logic still runs 600 steps in 10 real seconds', Math.abs(got-600)<=2, got);}
  T('C clock: ...also with an uneven frame time (60 fps with jitter)', Math.abs(stepsOver(60,10,2)-600)<=2, stepsOver(60,10,2));
  resetClock(); clockSteps(1000); T('C clock: a 10 second freeze is capped (no endless catch-up)', clockSteps(11000)===CFG.CATCH_UP);
  T('C clock: ...and the backlog is dropped, the next normal frame runs 1 step', clockSteps(11016.7)===1);
  resetClock(); clockSteps(0); T('C clock: a frame with no time passed runs nothing', clockSteps(0)===0);
  T('C clock: time going backwards runs nothing and does not break', clockSteps(-50)===0);

  const realSeconds=(fps,fn)=>{resetClock();let t=100000,start=null;loop(t);let el=0;const dtv=1000/fps;for(let i=0;i<fps*10&&!fn.done();i++){t+=dtv;el+=dtv;loop(t);}return el;};
  for(const fps of [60,30,20]){
    newGame(); frames(2); resetClock(); loop(100000); mario.rect.x=50; applyPower(P_JUMP); let ms=0,t=100000;const dtv=1000/fps;
    while(mario.power&&ms<6000){t+=dtv;ms+=dtv;loop(t);}
    T('C powers: at '+fps+' fps a 3 second power lasts 3 real seconds (+-1 frame)', mario.power===null&&Math.abs(ms-3000)<=dtv+17, Math.round(ms)+' ms, state='+STATE);
  }
  const walk=(fps)=>{newGame();frames(2);resetClock();let t=100000;loop(t);mario.rect.x=50;keys.ArrowRight=true;const dtv=1000/fps;for(let ms=0;ms<500;ms+=dtv){t+=dtv;loop(t);}keys.ArrowRight=false;return mario.rect.x-50;};
  const d60=walk(60),d30=walk(30),d20=walk(20);
  T('C speed: walking for 0.5 s covers the same distance at 60, 30 and 20 fps', Math.abs(d60-d30)<=12&&Math.abs(d60-d20)<=18&&d60>130, d60+' / '+d30+' / '+d20);
  newGame(); frames(2); resetClock(); loop(1000); mario.punching=true; mario.punchT=18; let t2=1000; for(let i=0;i<9;i++){t2+=1000/30;loop(t2);}
  T('C speed: a punch (18 steps) lasts 0.3 real seconds at 30 fps too', mario.punchT===0, mario.punchT);
}

// ---- D. CRUSH: near in BOTH directions, same range at the start and while it lasts ----
{
  const setup=(dx,dy,power=true)=>{newGame();frames(2);level.enemies.length=0;mario.rect.x=1000;mario.rect.y=GY-38;mario.inv=9999;mario.vy=0;
    const e=new Mush(mario.rect.x+dx,mario.rect.y+6+dy,340);level.enemies.push(e);if(power){mario.power='crush';mario.powerT=180;}return e;};
  let e=setup(40,0); update(); T('D crush: an enemy right next to Mario is defeated', !e.alive);
  e=setup(40,-250); update(); T('D crush: an enemy 250px ABOVE Mario is NOT defeated (the reported bug)', e.alive, 'alive='+e.alive);
  e=setup(40,-120); update(); T('D crush: ...nor one 120px above', e.alive);
  mario.rect.y=100; e=setup(40,0); mario.rect.y=GY-38; // (sanity helper above leaves Mario on the ground)
  newGame(); frames(2); level.enemies.length=0; mario.rect.x=1000; mario.rect.y=150; mario.inv=9999; mario.power='crush'; mario.powerT=180; mario.vy=-0.1;
  const low=new Mush(1040,GY-40,340); level.enemies.push(low); update(); T('D crush: an enemy far BELOW Mario is NOT defeated either', low.alive);
  e=setup(70,0); update(); T('D crush: 70px away on the same level: defeated', !e.alive);
  e=setup(130,0); update(); T('D crush: 130px away on the same level: NOT defeated', e.alive);
  const below=(lift)=>{newGame();frames(2);level.enemies.length=0;mario.rect.x=1000;mario.rect.y=GY-38-lift;mario.inv=9999;mario.vy=-0.1;mario.power='crush';mario.powerT=180;
    const en=new Mush(1010,GY-32,340);level.enemies.push(en);update();return en;};
  T('D crush: an enemy about one body below Mario (he is 40px up): defeated', !below(40).alive);
  T('D crush: an enemy 100px lower than Mario: NOT defeated', below(100).alive);
  // the same range when the power STARTS (picking up the block) as while it lasts
  for(const [dx,dy,name] of [[150,0,'150px beside'],[40,-250,'250px above'],[40,0,'right next to'],[70,40,'70px beside / 40px below']]){
    const a=setup(dx,dy,false); applyPower(P_CRUSH); const atStart=!a.alive;
    const b2=setup(dx,dy,true); update(); const during=!b2.alive;
    T('D crush: '+name+' Mario: the result is the same at the start ('+atStart+') and while it lasts ('+during+')', atStart===during);
  }
  e=setup(150,0,false); applyPower(P_CRUSH); T('D crush: at activation an enemy 150px away survives (it used to be hit up to 200px)', e.alive);
  e=setup(40,0,false); applyPower(P_CRUSH); T('D crush: at activation a close enemy is defeated at once', !e.alive);
  e=setup(40,0,false); update(); T('D crush: without the power an enemy beside Mario is not defeated by crush', e.alive, 'alive='+e.alive);
}

// ---- E. BOSS: fixed fight zone, never through pipes or obstacles (all five boss levels) ----
{
  for(const n of [10,20,30,40,50]){
    for(let seed=1;seed<=30;seed++){const Z=buildLv(n,seed*37+n);const bad=Z.platforms.filter(p=>p.h<50&&p.x+p.w>Z.boss.arenaL).length+Z.lbs.filter(b=>b.rect.x+b.rect.w>Z.boss.arenaL).length+Z.enemies.filter(e=>e.rect.x+e.rect.w>Z.boss.arenaL).length+Z.pipes.filter(p=>p.lip.x+p.lip.w>Z.boss.arenaL-40).length;
      if(bad){T('E boss level '+n+', layout '+seed+': the fight zone must be completely free', false, bad+' objects inside');break;}
      if(seed===30)T('E boss level '+n+': in 30 different random layouts the fight zone is always free of pipes, platforms, blocks and enemies', true);}
    const L=buildLv(n,50); const lastPipe=L.pipes.reduce((m,p)=>Math.max(m,p.lip.x+p.lip.w),0);
    const intruders=L.platforms.filter(p=>p.h<50&&p.x+p.w>L.boss.arenaL).length+L.lbs.filter(b=>b.rect.x+b.rect.w>L.boss.arenaL).length+L.enemies.filter(e=>e.rect.x+e.rect.w>L.boss.arenaL).length;
    T('E boss level '+n+': the fight zone has no floating platform, block or enemy in it (nothing to hide on)', intruders===0, intruders);
    T('E boss level '+n+': every pipe lies before the fight zone ('+L.pipes.length+' pipes, last ends at '+lastPipe+', zone starts at '+L.boss.arenaL+')', lastPipe<L.boss.arenaL);
    loadLv(n); STATE='playing'; const b=level.boss; mario.inv=999999; let outside=0,inSolid=0,minX=1e9,maxRight=0;
    for(let i=0;i<1800;i++){mario.rect.x=100;mario.rect.y=GY-38;mario.vx=0;mario.vy=0;update(); minX=Math.min(minX,b.rect.x);maxRight=Math.max(maxRight,b.rect.x+b.rect.w);
      if(b.rect.x<b.arenaL||b.rect.x+b.rect.w>LW)outside++; if(level.solids.some(s=>ov(b.rect,s)))inSolid++; if(STATE!=='playing')break;}
    T('E boss level '+n+': with Mario far away, the boss never leaves the fight zone (lowest x '+~~minX+', zone starts at '+b.arenaL+')', outside===0&&minX>=b.arenaL, 'outside='+outside);
    T('E boss level '+n+': ...never overlaps a pipe, block or platform', inSolid===0, inSolid);
    T('E boss level '+n+': ...but it really chases Mario to the edge of its zone', Math.abs(b.rect.x-b.arenaL)<=b.spd, b.rect.x);
    // goes back and forth: still inside
    let out2=0; for(let i=0;i<1200;i++){mario.rect.x=(~~(i/200)%2)?4600:3000;mario.rect.y=GY-38;mario.vx=0;mario.vy=0;update();if(b.rect.x<b.arenaL||b.rect.x+b.rect.w>LW)out2++;if(STATE!=='playing')break;}
    T('E boss level '+n+': Mario running from one side to the other: the boss stays in the zone', out2===0);
  }
  // an obstacle INSIDE the zone must stop it as well (the old code walked straight through)
  loadLv(10); STATE='playing'; const bb=level.boss; const pipe=new Pipe(4000); level.pipes.push(pipe); level.solids.push(pipe.shaft,pipe.lip); mario.inv=999999; let through=0;
  for(let i=0;i<900;i++){mario.rect.x=3950;mario.rect.y=GY-38;mario.vx=0;mario.vy=0;update(); if(bb.rect.x<pipe.lip.x+pipe.lip.w-0.5&&bb.rect.x+bb.rect.w>pipe.lip.x)through++; if(STATE!=='playing')break;}
  T('E boss: a pipe in its way stops it (it cannot pass through)', through===0&&bb.rect.x>=pipe.lip.x+pipe.lip.w-0.5, 'x='+bb.rect.x+' through='+through);
}

// ---- F. switching heroes: all four, no duplicates ----
{
  const looks=()=>[mario.activeChar,...companions.map(c=>c._drawAs||c.type)].sort().join(',');
  loadLv(25); STATE='playing'; mario.activeChar='mario';
  const seq=[]; for(let i=0;i<5;i++){mario.switchChar();seq.push(mario.activeChar);}
  T('F heroes: with all four unlocked T cycles Mario > Luigi > Princess > Yoshi > Mario > Luigi', seq.join('>')==='luigi>princess>yoshi>mario>luigi', seq.join('>'));
  loadLv(25); mario.activeChar='mario'; let dup=0; for(let i=0;i<9;i++){mario.switchChar(); if(looks()!=='luigi,mario,princess,yoshi')dup++;}
  T('F heroes: after every switch each of the four characters is shown exactly once (no twin on screen)', dup===0, looks());
  loadLv(15); mario.activeChar='mario'; const s3=[]; for(let i=0;i<4;i++){mario.switchChar();s3.push(mario.activeChar);}
  T('F heroes: with Luigi and the Princess (levels 11-20) the cycle has three heroes', s3.join('>')==='luigi>princess>mario>luigi', s3.join('>'));
  loadLv(15); mario.activeChar='mario'; dup=0; for(let i=0;i<6;i++){mario.switchChar(); if(looks()!=='luigi,mario,princess')dup++;} T('F heroes: ...without duplicates', dup===0);
  loadLv(5); mario.switchChar(); T('F heroes: in chapter 1 (nobody to switch to) T does nothing', mario.activeChar==='mario');
  // drawing
  const calls={};const wrap=n=>{const f=eval(n);const w=(...a)=>{calls[n]=(calls[n]||0)+1;return f(...a);};eval(n+'=w');return()=>eval(n+'=f');};
  const undo=['drawMario','drawPrincess','drawYoshi','drawLuigi'].map(wrap);
  loadLv(25); STATE='playing'; mario.inv=0; mario.dashing=false; mario.vx=0;
  for(const k of ['mario','luigi','princess','yoshi']){ for(const n in calls)delete calls[n]; mario.activeChar=k; mario.draw(0);
    const want={mario:'drawMario',luigi:'drawMario',princess:'drawPrincess',yoshi:'drawYoshi'}[k];
    T('F heroes: playing as '+k+' draws the '+k+' sprite', calls[want]>=1&&(k==='mario'||k==='luigi'||!calls.drawMario), JSON.stringify(calls)); }
  for(const n in calls)delete calls[n]; companions.find(c=>c.type==='luigi')._drawAs='mario'; companions.find(c=>c.type==='luigi').draw(0);
  T('F heroes: a team member that has taken Mario\'s place is drawn as Mario', calls.drawMario===1&&!calls.drawLuigi, JSON.stringify(calls));
  undo.forEach(f=>f());
  loadLv(25); for(const k of ['mario','luigi','princess','yoshi']){mario.activeChar=k; STATE='playing'; drawPlay();}
  T('F heroes: the whole play screen draws with each hero without an error', true);
}

// ---- G. menu keyboard ----
{
  localStorage.removeItem(SAVE_KEY); STATE='menu'; showMenu();
  T('G menu: without a save only NEW GAME exists and it is selected', menuOpts().join()==='new'&&els.btnNew.classList.contains('sel')&&els.btnCont.style.display==='none');
  key('ArrowDown'); key('ArrowUp'); T('G menu: Up / Down with one option change nothing', menuIdx===0&&STATE==='menu');
  keyDown('Enter',{repeat:true}); T('G menu: a held Enter does not start anything', STATE==='menu'); keyUp('Enter');
  key('Enter'); T('G menu: without a save, ENTER starts a New Game (the reported bug)', STATE==='playing'&&curLv===1&&mario&&mario.lives===3);
  localStorage.removeItem(SAVE_KEY); STATE='menu'; showMenu(); key('Space'); T('G menu: SPACE starts a New Game too', STATE==='playing'&&curLv===1);
  const sv={lv:7,lives:2,cp:realSave(7),um:7,pw:null,pt:0};
  put(sv); STATE='menu'; showMenu();
  T('G menu: with a save both options exist and CONTINUE is selected (Enter never wipes a save by accident)', menuOpts().join()==='new,cont'&&menuIdx===1&&els.btnCont.classList.contains('sel')&&!els.btnNew.classList.contains('sel'));
  key('ArrowUp'); T('G menu: Up selects NEW GAME', menuIdx===0&&els.btnNew.classList.contains('sel')&&!els.btnCont.classList.contains('sel'));
  key('ArrowDown'); T('G menu: Down selects CONTINUE', menuIdx===1);
  key('KeyW'); T('G menu: W moves up', menuIdx===0); key('KeyS'); T('G menu: S moves down', menuIdx===1);
  key('ArrowDown'); T('G menu: Down on the last option wraps around', menuIdx===0); key('ArrowUp'); T('G menu: Up on the first option wraps around', menuIdx===1);
  key('Enter'); T('G menu: ENTER confirms CONTINUE', STATE==='playing'&&curLv===7&&mario.lives===2, 'lv='+curLv);
  put(sv); STATE='menu'; showMenu(); key('ArrowUp'); key('Space');
  d=lg(); T('G menu: SPACE confirms NEW GAME (and replaces the save)', STATE==='playing'&&curLv===1&&d&&d.lv===1, 'lv='+curLv);
  put({...sv,lives:0}); STATE='menu'; showMenu(); T('G menu: a damaged save shows no Continue', menuOpts().join()==='new'); key('Enter'); T('G menu: ...so Enter starts a New Game', STATE==='playing'&&curLv===1);
  newGame(); menuIdx=0; frames(2); key('ArrowDown'); key('Enter'); T('G menu: Up / Down / Enter do not touch the menu while playing', menuIdx===0&&STATE==='playing'&&curLv===1);
  T('G menu: the page tells the player the keys', /id="menuHint"/.test(html)&&/\.btn\.sel\{/.test(html));
}

// ---- H. saving: the message must tell the truth ----
{
  const setItemReal=localStorage.setItem; const noStore=()=>{localStorage.setItem=()=>{throw new Error('QuotaExceeded');};}; const silent=()=>{localStorage.setItem=()=>{};}; const fix=()=>{localStorage.setItem=setItemReal;};
  newGame(); frames(2); STATE='paused'; localStorage.removeItem(SAVE_KEY); noStore();
  key('KeyQ');
  T('H save: when the save FAILS, Q does not say SAVED / does not leave the game', STATE==='paused'&&fa===null, STATE);
  T('H save: ...a clear error is shown on the pause screen', /FAILED/.test(pauseMsg)&&/NOT saved/.test(pauseMsg), pauseMsg);
  T('H save: ...and nothing was stored', !hs()&&localStorage.getItem(SAVE_KEY)===null);
  drawPause(); T('H save: the pause screen draws with the error', true);
  fix(); key('KeyQ'); T('H save: trying again after the problem is gone works: SAVED and back to the menu', STATE==='falling_text'&&faNext==='menu'&&hs()&&pauseMsg==='');
  // the storage accepts the call but keeps nothing (silent failure): must still be reported
  newGame(); frames(2); STATE='paused'; localStorage.removeItem(SAVE_KEY); silent(); key('KeyQ');
  T('H save: a storage that silently keeps nothing is detected too (read-back check)', STATE==='paused'&&/FAILED/.test(pauseMsg)&&!hs());
  fix(); T('H save: sg() returns true only for a real save', sg(3,3)===true&&lg().lv===3);
  newGame(); frames(2); STATE='paused'; pauseMsg='SAVE FAILED'; key('Escape'); T('H save: the error is cleared when the game resumes', STATE==='playing'&&pauseMsg==='');
  // checkpoint autosave
  newGame(); frames(2); level.enemies.length=0; noStore(); const cpA=level.cps[0]; mario.rect.x=cpA.wx-10; mario.rect.y=GY-38; update();
  T('H save: an autosave that fails at a checkpoint says so (not just CHECKPOINT!)', flash&&/SAVE FAILED/.test(flash.t)&&!/^✔/.test(flash.t), flash&&flash.t); fix();
  newGame(); frames(2); level.enemies.length=0; mario.rect.x=level.cps[0].wx-10; mario.rect.y=GY-38; update(); T('H save: ...and a successful one still says CHECKPOINT', flash&&/^✔ CHECKPOINT/.test(flash.t), flash&&flash.t);
  // new level autosave
  newGame(); frames(2); noStore(); nextLv(); T('H save: a new level that could not be saved says so', flash&&/SAVE FAILED/.test(flash.t)&&curLv===2, flash&&flash.t); fix();
  newGame(); frames(2); nextLv(); T('H save: ...and a normal new level shows no error', !(flash&&/FAILED/.test(flash.t))&&lg().lv===2);
  // new game when saving does not work at all
  put({lv:7,lives:2,cp:null,um:7,pw:null,pt:0}); noStore(); newGame(); T('H save: New Game when saving is impossible: warns the player and removes the old save', flash&&/NOT be saved/.test(flash.t)&&!hs(), flash&&flash.t); fix();
}

// ---- randomised soak: no exceptions, no NaN, saves always valid ----
let seed=12345; const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
let soakOk=true,soakMsg='';
for(const lvl of [1,10,25,50]){
  put({lv:lvl,lives:3,cp:null,um:lvl,pw:null,pt:0}); contGame(lg());
  try{
    for(let i=0;i<4000;i++){
      if(i%25===0){keys.ArrowRight=rnd()<.8;keys.ArrowLeft=!keys.ArrowRight&&rnd()<.3;}
      if(i%40===0)mario.jump(); if(i%90===0)mario.punch(); if(i%7===0&&rnd()<.2)mario.releaseJ();
      if(STATE==='playing'||STATE==='falling_text')update();
      if(STATE==='falling_text'){for(let k=0;k<400&&STATE==='falling_text';k++)update(); if(STATE==='menu'||STATE==='playing'&&0)break;}
      if(STATE==='cutscene'){cs&&cs.after&&cs.after();}
      if(STATE==='playing'&&i%50===0)drawPlay();
      if(STATE==='playing'&&!(Number.isFinite(mario.rect.x)&&Number.isFinite(mario.rect.y))){soakOk=false;soakMsg='NaN';break;}
      if(STATE==='menu')break;
    }
  }catch(err){soakOk=false;soakMsg=lvl+': '+err.stack.split('\n').slice(0,3).join(' | ');}
  keys.ArrowRight=keys.ArrowLeft=false;
}
T('soak: 4 levels x 4000 random frames ran without any error', soakOk, soakMsg);
T('soak: the save is still valid afterwards', hs()||!localStorage.getItem(SAVE_KEY));

}catch(err){T('CRASH while running the checks: '+String(err&&err.message).slice(0,120),false);}
const fails=results.filter(r=>!r[1]);
console.log('\n'+(results.length-fails.length)+'/'+results.length+' checks passed');
fails.forEach(f=>console.log('  FAILED: '+f[0]));
console.log('RESULT: '+(fails.length?'FAIL':'PASS'));
process.exitCode=fails.length?1:0;
})();
`;

runInGame(htmlPath, tests);
