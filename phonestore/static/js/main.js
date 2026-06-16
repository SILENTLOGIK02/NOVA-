// Loader
window.addEventListener('load',()=>{
  const l=document.getElementById('loader');
  if(l){setTimeout(()=>l.classList.add('hide'),400)}
});

// Burger menu
document.addEventListener('click',e=>{
  if(e.target.closest('.burger')){
    document.querySelector('.nav-links')?.classList.toggle('open');
  }
});

// Instant search on home
const liveSearch=document.getElementById('liveSearch');
if(liveSearch){
  liveSearch.addEventListener('input',e=>{
    const q=e.target.value.trim().toLowerCase();
    document.querySelectorAll('[data-product]').forEach(el=>{
      const t=el.dataset.product.toLowerCase();
      el.style.display=t.includes(q)?'':'none';
    });
  });
}

// Smooth reveal on scroll
const io=new IntersectionObserver(es=>{
  es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('fade-up');io.unobserve(e.target)}});
},{threshold:.1});
document.querySelectorAll('.section, .feat-card').forEach(el=>io.observe(el));
