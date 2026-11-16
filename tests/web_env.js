// Fake browser (DOM, canvas, localStorage) so the REAL game script of web.html can run in Node.
//   const { runInGame } = require('./web_env.js');  runInGame('web.html', code => ...)
const fs = require('fs'), vm = require('vm');

function runInGame(htmlPath, makeTestCode) {
  const html = fs.readFileSync(htmlPath, 'utf8');
  const script = html.match(/<script>\n([\s\S]*)<\/script>/)[1];
  const noopFn = () => proxy;
  const proxy = new Proxy(function(){}, { get:(t,k)=> k==='measureText'?()=>({width:10}):(k in t&&k!=='name'&&k!=='length'?t[k]:noopFn), set:(t,k,v)=>{t[k]=v;return true;}, apply:()=>proxy });
  const els = {}; const docHandlers = {};
  function makeEl(id){ const o={id,style:{},handlers:{},textContent:'',width:0,height:0,className:'',
    addEventListener(t,f){this.handlers[t]=f;}, blur(){}, setPointerCapture(){}, releasePointerCapture(){}, getBoundingClientRect(){return{left:0,top:0,width:150,height:150};}, getContext:()=>proxy,
    classList:(()=>{const set=new Set();return{add:c=>{set.add(c);},remove:c=>{set.delete(c);},toggle:(c,on)=>{(on===undefined?!set.has(c):on)?set.add(c):set.delete(c);},contains:c=>set.has(c)};})()}; return o; }
  const store = {}; const ls = { getItem:k=>(k in store?store[k]:null), setItem:(k,v)=>{store[k]=String(v);}, removeItem:k=>{delete store[k];} };
  const sandbox = {
    console, Math, JSON, Number, Array, Object, String, Promise, Map, Set, Date, Symbol, isFinite, parseInt, parseFloat, Error,
    els, docHandlers, localStorage: ls, html, process,
    document:{ getElementById:id=>els[id]||(els[id]=makeEl(id)), createElement:()=>makeEl('canvas'),
      addEventListener(t,f){docHandlers[t]=f;}, activeElement:null, body:{className:''}, hidden:false,
      documentElement:{requestFullscreen:()=>Promise.resolve(), classList:{toggle(){},add(){},remove(){}}}, fullscreenElement:null, exitFullscreen(){} },
    window:{ innerWidth:1000, innerHeight:700, addEventListener(){} },
    navigator:{maxTouchPoints:0}, requestAnimationFrame:()=>{}, setTimeout, performance:{now:()=>0},
  };

  vm.createContext(sandbox);
  vm.runInContext(script + makeTestCode, sandbox, { filename: 'web.html' });
}
module.exports = { runInGame };
