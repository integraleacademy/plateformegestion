
function updateClock(){
  try {
    const now = new Date();
    // Convert to Europe/Paris without external libs:
    // Using Intl API to format in French with Paris time zone
    const fmt = new Intl.DateTimeFormat('fr-FR', {
      timeZone: 'Europe/Paris',
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    const txt = fmt.format(now);
    const el = document.getElementById('clock');
    if(el) el.textContent = txt.charAt(0).toUpperCase() + txt.slice(1);
  } catch(e){}
}
setInterval(updateClock, 1000);
updateClock();
