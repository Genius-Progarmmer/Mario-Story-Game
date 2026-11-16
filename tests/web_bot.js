// A bot plays EVERY level of web.html from its start to its goal (and the boss levels, and the ending),
// with the real game rules. A level that the bot cannot finish is reported with where it got stuck.
// Part 1: every level on its own (saved start, several tries). Part 2: ONE continuous game, a single New Game
// from the menu and then levels 1 to 50, the story scenes, the ending and the final menu, with lives and saves checked.
//   node tests/web_bot.js web.html [firstLevel lastLevel]
const { runInGame } = require('./web_env.js');
const htmlPath = process.argv[2] || 'web.html';
const first = +process.argv[3] || 1, last = +process.argv[4] || 50;
const debug = process.env.WEB_BOT_DEBUG ? 'true' : 'false';   // WEB_BOT_DEBUG=1 prints the cause of every death

const bot = String.raw`
;(function(){
const FIRST=${first}, LAST=${last}, BUDGET=4000, DEBUG=${debug};
const key=(code)=>docHandlers.keydown({code,preventDefault(){}});
const put=o=>localStorage.setItem(SAVE_KEY,JSON.stringify(o));
let report=[],bad=0;

const VARIANTS=[ {lo:34,hi:56}, {lo:34,hi:44}, {lo:40,hi:62}, {lo:28,hi:46}, {lo:-10,hi:-5,foot:true}, {lo:46,hi:68}, {lo:22,hi:38}, {lo:52,hi:72}, {lo:34,hi:56,stomp:true}, {lo:-10,hi:-5,foot:true,stomp:true}, {lo:40,hi:62,stomp:true},
  {rand:.05}, {rand:.08}, {rand:.03}, {rand:.12}, {rand:.06}, {rand:.04}, {rand:.1} ];   // the last ones jump at random (repeatable seeds): finds routes over platforms
let seed=1; const R=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
let V=VARIANTS[0];
function botThink(){
  const m=mario.rect, front=m.x+m.w, onPlatform=m.y+m.h<GY-20;
  keys.ArrowLeft=false; keys.ArrowRight=true;
  const boss=level.boss&&level.boss.alive?level.boss:null;

  // PIPES. A single jump clears a pipe only if it starts in the right window before the lip (V.lo..V.hi px):
  // later and Mario hits the shaft / a low platform above him, earlier and he comes down on the far end of the
  // lip (which kills). Several windows are tried (see VARIANTS), plus "jump right at the foot of the pipe".
  if(V.rand){
    if(mario.onGround&&R()<V.rand) mario.jump();
    else if(!mario.onGround&&mario.jl>0&&mario.vy>2&&R()<V.rand/2) mario.jump();
  }
  else for(const p of level.pipes){
    const dx=p.lip.x-front;
    if(!V.foot&&mario.onGround&&dx>-14&&dx<V.lo){ keys.ArrowRight=false; keys.ArrowLeft=true; }   // too close: back off
    else if(mario.onGround&&dx>=V.lo&&dx<=V.hi){ mario.jump(); }
    const over=front>p.lip.x-4&&m.x<p.lip.x+p.lip.w;                                            // really above this pipe's lip
    if(over&&!mario.onGround&&mario.vy>1&&m.y+m.h<p.lip.y-2&&m.y+m.h>p.lip.y-46&&mario.jl>0) mario.jump();
  }
  // ENEMIES: punch the ones in front of us (no jumping: a jump near a pipe or a platform is how bots die)
  for(const e of level.enemies){
    if(!e.alive||e.squish>0)continue;
    if(e.rect.y+e.rect.h<m.y+8)continue;                                  // on a platform above us
    const dx=e.rect.x-front, dxl=m.x-(e.rect.x+e.rect.w);
    if(V.stomp&&mario.onGround&&Math.abs((e.rect.y+e.rect.h)-(m.y+m.h))<40&&dx>20&&dx<70&&!level.pipes.some(p=>p.lip.x-front>-20&&p.lip.x-front<200)) mario.jump();
    if(Math.abs((e.rect.y+e.rect.h)-(m.y+m.h))<40&&dx>-6&&dx<44&&mario.punchT===0&&!mario.punching){ mario.facing=1; mario.punch(); }
    if(Math.abs((e.rect.y+e.rect.h)-(m.y+m.h))<40&&dx<=-6&&dxl>-6&&dxl<44&&mario.punchT===0&&!mario.punching){ mario.facing=-1; mario.punch(); }
  }
  // BOSS: walk to it, then stand and punch (it keeps ~14px away and hits back about every 85 frames)
  if(boss){
    const d=(boss.rect.x+40)-(m.x+16);
    if(Math.abs(d)>75||onPlatform){ keys.ArrowRight=d>0; keys.ArrowLeft=d<0; }
    else { keys.ArrowRight=keys.ArrowLeft=false; mario.facing=d>0?1:-1; }
    if(mario.punchT===0&&!mario.punching&&Math.abs(d)<110) mario.punch();
  }
}

function playOnce(n){
  put({lv:n,lives:3,cp:null,um:n,pw:null,pt:0}); contGame(lg());
  keys.ArrowLeft=keys.ArrowRight=keys.Space=false;
  let frames=0,lost=0,livesNow=mario.lives,lastX=mario.rect.x,still=0,maxX=0,note='';
  while(frames<BUDGET){
    frames++;
    if(STATE==='playing'){
      botThink();
      // stuck? (nothing moved for 1.5 s while no boss is in the way)
      if(Math.abs(mario.rect.x-lastX)<0.5)still++; else still=0; lastX=mario.rect.x;
      if(still>90&&!(level.boss&&level.boss.alive)){mario.jump();still=60;}
      const pre={x:mario.rect.x,y:mario.rect.y,vy:mario.vy,og:mario.onGround,jl:mario.jl,dying:pipeDying,
                 en:DEBUG?level.enemies.filter(e=>e.alive).map(e=>({x:e.rect.x,yb:e.rect.y+e.rect.h})):0};
      update();
      if(DEBUG&&((mario.lives<livesNow)||(pipeDying&&!pre.dying))&&!(mario.lives<livesNow&&pre.dying)){
        const near=pre.en.filter(e=>Math.abs(e.x-pre.x)<130).map(e=>'enemy dx='+~~(e.x-pre.x)+(e.yb<500?'(platform)':''));
        const pip=level.pipes.filter(p=>Math.abs(p.wx-pre.x)<150).map(p=>'pipe lip.x-front='+~~(p.lip.x-(pre.x+32)));
        console.log('     frame '+frames+': '+(pipeDying?'PIPE KILL':'hit')+' x='+~~pre.x+' y='+~~pre.y+' vy='+pre.vy.toFixed(1)+' og='+pre.og+' jl='+pre.jl+' | '+near.concat(pip).join('; ')+(level.boss&&level.boss.alive?' | boss hp='+level.boss.hp+' hits='+mario.bossHits:''));
      }
      if(mario.lives<livesNow){lost+=livesNow-mario.lives;livesNow=mario.lives;}
      maxX=Math.max(maxX,mario.rect.x);
    } else if(STATE==='falling_text'){
      if(fa&&faNext==='menu'){note='GAME OVER'; break;}         // lost all lives
      if(curLv!==n)break;                                        // next level reached
      update();
    } else if(STATE==='cutscene'){
      if(n===50&&cs&&cs.id==='final'){note='ENDING'; break;}
      if(curLv!==n)break;
      update();
    } else break;
    if(curLv!==n)break;
    if(n===50&&STATE==='cutscene'&&cs&&cs.id==='final'){note='ENDING';break;}
  }
  const ok=(curLv!==n)||note==='ENDING';
  return {n,ok,frames,lost,x:~~maxX,goal:level?level.goal.x:0,note:ok?'':(note||('stuck at x='+~~mario.rect.x+' STATE='+STATE)),boss:!!(level&&level.boss)};
}

const bestV={};            // level -> index of the jump timing that finished it in part 1 (used again in the continuous game)
function playLevel(n){
  let r,tried=0;
  for(const v of VARIANTS.slice(0,+process.env.WEB_BOT_VARIANTS||VARIANTS.length)){ V=v; seed=n*7919+tried*104729+1; tried++; r=playOnce(n); if(r.ok)break; if(DEBUG)console.log('   attempt '+tried+' failed: '+r.note); }
  r.attempts=tried; bestV[n]=r.ok?tried-1:0; return r;
}
for(let n=FIRST;n<=LAST;n++){
  let r; try{r=playLevel(n);}catch(err){r={n,ok:false,frames:0,lost:0,note:'CRASH '+String(err&&err.stack||err).split('\n').slice(0,3).join(' | ')};}
  report.push(r); if(!r.ok)bad++;
  console.log((r.ok?'ok   ':'FAIL ')+'level '+String(n).padStart(2)+(r.boss?' (boss)':'       ')+'  frames='+String(r.frames).padStart(5)+'  lives lost='+r.lost+'  attempts='+(r.attempts||'-')+(r.ok?'':'   '+r.note));
}
// ---- ONE continuous game: a single New Game, then level 1 ... level 50, the final cutscene and the end screen ----
// Nothing is restarted in between (no newGame / contGame / put): this is the way a real player goes through the game.
function continuousRun(){
  const problems=[]; const P=(cond,msg)=>{if(!cond&&problems.length<12)problems.push(msg);};
  let newGames=0,contGames=0; const realNew=newGame,realCont=contGame;
  newGame=function(){newGames++;return realNew.apply(this,arguments);};
  contGame=function(){contGames++;return realCont.apply(this,arguments);};
  localStorage.removeItem(SAVE_KEY); STATE='menu'; showMenu();
  docHandlers.keydown({code:'Enter',preventDefault(){}}); docHandlers.keyup({code:'Enter',preventDefault(){}});   // the real menu: ENTER = New Game
  P(newGames===1&&STATE==='playing'&&curLv===1&&mario.lives===3,'New Game from the menu did not start level 1 with 3 lives');
  const csSeen=[], livesAtStart=[], levelsEntered=[1], deaths=[];
  let lastLv=1, frames=0, lvFrames=0, lost=0, vIdx=0, maxX=0, noProg=0, lastCp=cpX, awaitStart=true, livesNow=mario.lives, ended=false, drawn=0, retreat=0;
  const setV=(i)=>{V=VARIANTS[i%VARIANTS.length]; seed=curLv*7919+i*104729+1;};
  setV(bestV[1]||0); vIdx=bestV[1]||0;
  const MAXF=500000, LVBUDGET=9000;
  while(frames<MAXF){
    frames++; lvFrames++;
    if(lvFrames>LVBUDGET){P(false,'level '+curLv+': stuck for '+LVBUDGET+' frames (x='+~~mario.rect.x+')'); break;}
    if(STATE==='playing'){
      if(awaitStart){                                   // the first frame of a new level
        awaitStart=false; livesAtStart.push(mario.lives); livesNow=mario.lives; lastCp=cpX; maxX=0; noProg=0;
        P(mario.lives===3,'level '+curLv+': Mario starts with '+mario.lives+' lives, not 3');
        P(level&&level.goal&&cpX===null,'level '+curLv+': a new level starts without a checkpoint');
      }
      if(retreat>0){retreat--;keys.ArrowRight=false;keys.ArrowLeft=true;if(retreat===0)maxX=mario.rect.x;}   // a player who is stuck walks back to get a run-up
      else botThink();
      update();
      if(frames%150===0){drawPlay();drawn++;}
      if(mario.lives<livesNow){lost+=livesNow-mario.lives; deaths.push(curLv); livesNow=mario.lives; vIdx++; setV(vIdx); noProg=0;}
      if(retreat===0){if(mario.rect.x>maxX+1){maxX=mario.rect.x;noProg=0;} else noProg++;}
      if(noProg>240&&retreat===0&&!(level.boss&&level.boss.alive&&mario.rect.x>level.boss.arenaL-500)){vIdx++;setV(vIdx);noProg=0;retreat=70;}   // blocked: walk back, then try another jump timing
      P(mario.lives>=1&&mario.lives<=3,'level '+curLv+': impossible number of lives '+mario.lives);
      if(cpX!==null&&cpX!==lastCp){const d=lg(); P(d&&d.lv===curLv&&d.cp===cpX&&d.lives===mario.lives,'level '+curLv+': the checkpoint autosave is wrong: '+JSON.stringify(d));}
      lastCp=cpX;
    }else if(STATE==='falling_text'){
      if(faNext==='menu'){P(false,'GAME OVER on level '+curLv+' (all lives lost)'); break;}
      update(); if(frames%40===0){drawFalling();drawn++;}
    }else if(STATE==='cutscene'){
      if(cs&&csSeen[csSeen.length-1]!==cs.id)csSeen.push(cs.id);
      update(); if(frames%40===0){drawCS();drawn++;}
    }else if(STATE==='menu'){ended=true;break;}
    else{P(false,'unexpected state '+STATE);break;}
    if(curLv!==lastLv){                                 // the level counter changed (goal reached)
      P(curLv===lastLv+1,'the level jumped from '+lastLv+' to '+curLv);
      const d=lg();
      P(d&&d.lv===curLv&&d.lives===3&&d.cp===null&&d.um>=curLv,'level '+curLv+': the save after the level change is wrong: '+JSON.stringify(d));
      lastLv=curLv; levelsEntered.push(curLv); lvFrames=0; vIdx=bestV[curLv]||0; setV(vIdx); awaitStart=true;
    }
  }
  // ---- the end of the game ----
  P(ended,'the game never got back to the menu after level 50 (state '+STATE+', level '+curLv+')');
  P(curLv===50,'the game ended on level '+curLv+' (a "level 51" must not exist)');
  P(levelsEntered.length===50&&levelsEntered.every((v,i)=>v===i+1),'levels entered: '+levelsEntered.join(','));
  P(csSeen.join()==='ch1_end,ch2_start,ch2_end,ch3_end,ch4_end,final','story scenes seen: '+csSeen.join(',')+' (expected ch1_end,ch2_start,ch2_end,ch3_end,ch4_end,final)');
  P(livesAtStart.length===50&&livesAtStart.every(v=>v===3),'lives at the start of each level: '+livesAtStart.join(','));
  P(newGames===1&&contGames===0,'the game was started '+newGames+' times with New Game and '+contGames+' with Continue (must be 1 and 0)');
  const endSave=lg(); P(endSave&&endSave.lv===50&&endSave.lives===3,'the save at the end of the game is wrong: '+JSON.stringify(endSave));
  P(typeof els!=='undefined'?els.overlay.style.display==='flex':true,'the menu is not shown after the ending');
  P(typeof els!=='undefined'?els.btnCont.style.display==='block':true,'the menu after the ending does not offer Continue');
  newGame=realNew; contGame=realCont;
  return {ok:problems.length===0,problems,frames,lost,deaths,drawn,csSeen};
}
if(FIRST===1&&LAST===50){
  let c; try{c=continuousRun();}catch(err){c={ok:false,problems:['CRASH '+String(err&&err.stack||err).split('\\n').slice(0,3).join(' | ')],frames:0,lost:0,deaths:[],csSeen:[]};}
  console.log('\n--- one continuous game: ONE New Game, then level 1 -> level 50 -> ending screen ---');
  console.log((c.ok?'ok   ':'FAIL ')+'continuous run  frames='+c.frames+'  lives lost in total='+c.lost+(c.deaths.length?' (on levels '+c.deaths.join(',')+')':'')+'  story scenes: '+c.csSeen.join(' > '));
  for(const p of c.problems)console.log('     problem: '+p);
  if(!c.ok)bad++;
}

console.log('\nlevels the bot could not finish: '+bad+' of '+report.length+'   (lives lost in total: '+report.reduce((a,r)=>a+r.lost,0)+')');
console.log('RESULT: '+(bad?'FAIL':'PASS'));
process.exitCode=bad?1:0;
})();
`;
runInGame(htmlPath, bot);
