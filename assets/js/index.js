/* 인덱스: 줄에 마우스를 올리거나 초점을 주면 미리보기를 바꾸고, 목록/표지 보기를 전환하고, 표지 보기에서 종류로 거른다. */
(function () {
  var dataEl = document.getElementById('works-data');
  if (!dataEl) return;
  var works = JSON.parse(dataEl.textContent);

  /* 미리보기 */
  var pv = document.querySelector('[data-preview]');
  var rows = Array.prototype.slice.call(document.querySelectorAll('.row[data-i]'));
  function show(i) {
    var w = works[i];
    if (!w || !pv) return;
    rows.forEach(function (r) { r.classList.toggle('is-active', r === rows[i]); });
    var img = pv.querySelector('[data-pv-img]');
    var type = pv.querySelector('[data-pv-type]');
    if (w.cover) {
      img.src = w.cover; img.alt = w.coverAlt || ''; img.hidden = false; type.hidden = true;
    } else {
      img.hidden = true; type.hidden = false;
      type.querySelector('[data-pv-no]').textContent = w.no;
      type.querySelector('[data-pv-ctitle]').textContent = w.title;
      type.querySelector('[data-pv-ctype]').textContent = w.typeShort;
    }
    pv.querySelector('[data-pv-title]').textContent = w.title;
    pv.querySelector('[data-pv-en]').textContent = w.en;
    pv.querySelector('[data-pv-meta]').textContent = w.type + ' / ' + w.role;
    pv.querySelector('[data-pv-summary]').textContent = w.summary;
    var link = pv.querySelector('[data-pv-link]');
    link.href = w.href;
  }
  rows.forEach(function (r) {
    var i = parseInt(r.getAttribute('data-i'), 10);
    r.addEventListener('mouseenter', function () { show(i); });
    r.addEventListener('focus', function () { show(i); });
  });

  /* 보기 전환 */
  var listView = document.querySelector('[data-view="list"]');
  var shelfView = document.querySelector('[data-view="shelf"]');
  var btns = Array.prototype.slice.call(document.querySelectorAll('[data-set-view]'));
  function setView(v, remember) {
    listView.hidden = v !== 'list';
    shelfView.hidden = v !== 'shelf';
    btns.forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-set-view') === v)); });
    if (remember) { try { localStorage.setItem('portfolio-view', v); } catch (e) {} }
  }
  btns.forEach(function (b) { b.addEventListener('click', function () { setView(b.getAttribute('data-set-view'), true); }); });
  var saved = null;
  try { saved = localStorage.getItem('portfolio-view'); } catch (e) {}
  if (location.hash === '#shelf') saved = 'shelf';
  setView(saved === 'shelf' ? 'shelf' : 'list', false);

  /* 표지 보기 거르기 */
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card[data-cat]'));
  var chips = Array.prototype.slice.call(document.querySelectorAll('[data-filter]'));
  var shown = document.querySelector('[data-shown]');
  chips.forEach(function (c) {
    c.addEventListener('click', function () {
      var k = c.getAttribute('data-filter');
      var n = 0;
      cards.forEach(function (card) {
        var on = k === 'all' || card.getAttribute('data-cat') === k;
        card.hidden = !on; if (on) n++;
      });
      chips.forEach(function (x) { x.setAttribute('aria-pressed', String(x === c)); });
      if (shown) shown.textContent = String(n);
    });
  });
})();
