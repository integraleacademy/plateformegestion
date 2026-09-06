import assert from 'node:assert/strict';
import {test} from 'node:test';
import {fitLayoutFrame,fitSlide} from '../static/studio_visuals/js/studio-text-fit.js';
import {bindAiComposer} from '../static/studio_visuals/js/studio-ai-panel.js';

// Small deterministic layout doubles exercise the numeric contracts without
// claiming to replace the real browser gallery in studio-browser-audit.html.
globalThis.document={};
globalThis.getComputedStyle=element=>element.computed||{
  display:'block',visibility:'visible',opacity:'1',position:'static'
};
function frame({zoom=1,overflow=0,artDirected=false}={}){
  const rect={left:0,top:0,width:900*zoom,height:600*zoom,right:900*zoom,bottom:600*zoom};
  const main={style:{},dataset:{layoutFitMode:artDirected?'art-directed':''},
    offsetWidth:900,offsetHeight:600,scrollWidth:900,scrollHeight:600+overflow,
    getBoundingClientRect:()=>rect,removeAttribute(){},children:[]};
  const child={getBoundingClientRect:()=>({...rect,bottom:(600+overflow)*zoom,height:(600+overflow)*zoom})};
  main.children=[child];
  return {main,querySelector:()=>main};
}
test('a valid layout keeps its full size at every editor zoom',()=>{
  for(const zoom of [.2,.4,.75,1,1.6])assert.equal(fitLayoutFrame(frame({zoom})),1);
});
test('the same content overflow produces the same fit in preview and export',()=>{
  for(const zoom of [.2,.75,1,1.6])assert.equal(fitLayoutFrame(frame({zoom,overflow:100})),600/700);
});
test('intentional absolute decorations do not shrink art-directed content',()=>{
  const root=frame({artDirected:true});
  root.main.children.push({computed:{display:'block',visibility:'visible',opacity:'1',position:'absolute'},
    getBoundingClientRect:()=>({left:-100,top:-200,right:1300,bottom:900,width:1400,height:1100})});
  assert.equal(fitLayoutFrame(root),1);
});

function textElement(fontSize,width,textLength,kind='title'){
  const element={dataset:{fit:kind},style:{},parentElement:{clientHeight:400},clientWidth:width,
    computed:{fontSize:String(fontSize),lineHeight:String(fontSize*1.2),paddingTop:'0',paddingBottom:'0'},
    removeAttribute(name){if(name==='data-fit-warning')delete this.dataset.fitWarning}};
  Object.defineProperties(element,{
    clientHeight:{get:()=>{const size=parseFloat(element.style.fontSize)||fontSize;return Math.ceil(size*1.2*Math.ceil(textLength*size*.5/width))}},
    scrollWidth:{get:()=>width},
    scrollHeight:{get:()=>{const size=parseFloat(element.style.fontSize)||fontSize;return Math.ceil(size*1.2*Math.ceil(textLength*size*.5/width))}}
  });
  return element;
}
function slide(...elements){return {dataset:{},clientHeight:1080,style:{},matches:()=>true,
  querySelectorAll:()=>elements,querySelector:()=>null}};
test('fitting preserves the authored small landscape type instead of inflating it',async()=>{
  const title=textElement(34,500,45),body=textElement(15,400,80,'body'),cta=textElement(13,240,26,'cta');
  await fitSlide(slide(title,body,cta));
  assert.equal(title.style.fontSize,'34px');assert.equal(body.style.fontSize,'15px');assert.equal(cta.style.fontSize,'13px');
});
test('fitting long text is stable when repeated for export',async()=>{
  const text=textElement(68,310,75),root=slide(text);
  await fitSlide(root);const first=text.style.fontSize;
  assert.ok(parseFloat(first)<68);assert.equal(text.dataset.fitWarning,undefined);
  for(let i=0;i<5;i++){await fitSlide(root);assert.equal(text.style.fontSize,first)}
});
test('an explicit manual font size is retained',async()=>{
  const text=textElement(34,400,40);text.dataset.studioManualFont='true';text.style.fontSize='51px';
  await fitSlide(slide(text));assert.equal(text.style.fontSize,'51px');
});
test('unfittable content remains flagged instead of silently passing',async()=>{
  const text=textElement(68,180,900);await fitSlide(slide(text));assert.ok(text.dataset.fitWarning);
});

class Control extends EventTarget{
  constructor(){super();this.attributes={};this.classes=new Set();this.classList={toggle:(name,on)=>on?this.classes.add(name):this.classes.delete(name)}}
  setAttribute(name,value){this.attributes[name]=value}
  focus(){this.focused=true}
}
function composer(storage){
  const panel=new Control(),toggle=new Control(),close=new Control(),workspace=new Control(),input=new Control();
  input.value='Une ambiance élégante';panel.querySelector=()=>input;panel.closest=()=>workspace;
  let resizes=0;bindAiComposer({panel,toggle,close,storage,onResize:()=>resizes++});
  return {panel,toggle,close,workspace,input,get resizes(){return resizes}};
}
test('close and reopen preserve the draft and return canvas space',()=>{
  const memory=new Map(),storage={getItem:k=>memory.get(k),setItem:(k,v)=>memory.set(k,v)};
  const c=composer(storage);c.close.dispatchEvent(new Event('click'));
  assert.equal(c.panel.hidden,true);assert.equal(c.toggle.attributes['aria-expanded'],'false');
  assert.ok(c.workspace.classes.has('is-ai-closed'));assert.equal(c.toggle.focused,true);
  assert.equal(composer(storage).panel.hidden,true);
  c.toggle.dispatchEvent(new Event('click'));
  assert.equal(c.panel.hidden,false);assert.equal(c.input.value,'Une ambiance élégante');
  assert.equal(c.input.focused,true);assert.equal(c.resizes,3);
});
test('Escape closes the focused composer even when storage is unavailable',()=>{
  const c=composer({getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}});
  const escape=new Event('keydown',{cancelable:true});Object.defineProperty(escape,'key',{value:'Escape'});
  c.panel.dispatchEvent(escape);assert.equal(c.panel.hidden,true);assert.equal(escape.defaultPrevented,true);
});
