const STORAGE_KEY='studio.aiComposerClosed';

export function bindAiComposer({panel,toggle,close,storage,onResize=()=>{}}){
  if(!panel||!toggle||!close)return;
  let closed=false;
  try{closed=storage?.getItem(STORAGE_KEY)==='true'}catch{}
  function setClosed(value,{focus=false}={}){
    closed=Boolean(value);
    panel.hidden=closed;
    panel.closest('.social-studio__workspace')?.classList.toggle('is-ai-closed',closed);
    toggle.setAttribute('aria-expanded',String(!closed));
    toggle.classList.toggle('is-active',!closed);
    try{storage?.setItem(STORAGE_KEY,String(closed))}catch{}
    if(focus)(closed?toggle:panel.querySelector('textarea'))?.focus();
    onResize();
  }
  close.addEventListener('click',()=>setClosed(true,{focus:true}));
  toggle.addEventListener('click',()=>setClosed(!closed,{focus:true}));
  panel.addEventListener('keydown',event=>{
    if(event.key==='Escape'){
      event.preventDefault();event.stopPropagation();setClosed(true,{focus:true});
    }
  });
  setClosed(closed);
}
